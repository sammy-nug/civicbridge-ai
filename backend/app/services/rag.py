"""The RAG workflow for chat and for claim checking. Each numbered step is in the code below."""
from __future__ import annotations

import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from datetime import date
from threading import Lock

from app.models.database import record_response
from app.schemas.api import ChatResponse, Citation, VerifyResponse
from app.services import citations as citation_tools
from app.services.guardrails import classify_policy, scrub_sensitive
from app.services.language import LANGUAGES, message, translate_texts
from app.services.llm import LLMError, LLMUnavailableError, generate_json, get_llm, start_request_deadline
from app.services.prompts import ANSWER_SYSTEM, REWRITE_SYSTEM, VERIFY_SYSTEM
from app.services.retrieval import TIME_CRITICAL_DOCUMENTS, Evidence, retrieve

SESSION_TTL_SECONDS = 30 * 60
MAX_SESSIONS = 500
MAX_HISTORY_TURNS = 3
MAX_UNCITED_RATIO = 1 / 3
MAX_CACHED_ANSWERS = 500
POLICY_BY_CATEGORY = {"partisan_request": "partisan", "prediction_request": "prediction", "off_topic": "off_topic"}
PASSAGES_ONLY_ANSWER = (
    "Our AI service is unavailable right now, so this is not a written answer. These official passages look "
    "most related to your question. Please read them directly, and check with INEC for anything important."
)
UNREVIEWED_NOTICE = "This translation was machine-generated and has not been reviewed by a human. Please check important details against the English version and the sources."


class _SessionStore:
    """Short-lived, in-memory conversation history. Never written to disk."""

    def __init__(self) -> None:
        self._sessions: OrderedDict[str, tuple[float, list[tuple[str, str]]]] = OrderedDict()
        self._lock = Lock()

    def history(self, session_id: str) -> list[tuple[str, str]]:
        with self._lock:
            entry = self._sessions.get(session_id)
            if entry is None or time.time() - entry[0] > SESSION_TTL_SECONDS:
                self._sessions.pop(session_id, None)
                return []
            return list(entry[1])

    def append(self, session_id: str, question: str, answer: str) -> None:
        with self._lock:
            turns = self._sessions.pop(session_id, (0.0, []))[1]
            turns = (turns + [(question, answer)])[-MAX_HISTORY_TURNS:]
            self._sessions[session_id] = (time.time(), turns)
            while len(self._sessions) > MAX_SESSIONS:
                self._sessions.popitem(last=False)


sessions = _SessionStore()


class _AnswerCache:
    """Repeat first questions reuse today's answer, which saves AI quota. In memory only.

    Today's date is part of the key because answers can depend on it.
    """

    def __init__(self) -> None:
        self._answers: OrderedDict[tuple[str, str, str], tuple[str, str, ChatResponse]] = OrderedDict()
        self._lock = Lock()

    @staticmethod
    def key(text: str, language: str) -> tuple[str, str, str]:
        return " ".join(text.lower().split()), language, date.today().isoformat()

    def get(self, key: tuple[str, str, str]) -> tuple[str, str, ChatResponse] | None:
        with self._lock:
            if key in self._answers:
                self._answers.move_to_end(key)
            return self._answers.get(key)

    def put(self, key: tuple[str, str, str], english_query: str, english_answer: str, response: ChatResponse) -> None:
        with self._lock:
            self._answers[key] = (english_query, english_answer, response)
            while len(self._answers) > MAX_CACHED_ANSWERS:
                self._answers.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._answers.clear()


answer_cache = _AnswerCache()


@dataclass
class PreparedQuery:
    english_query: str
    category: str


def _new_id() -> str:
    return str(uuid.uuid4())


def prepare_query(text: str, language: str, history: list[tuple[str, str]]) -> PreparedQuery:
    """Step 3: get a standalone English query. English with no history needs no LLM call."""
    if language == "en" and not history:
        return PreparedQuery(text, "electoral_question")
    conversation = "\n".join(f"User: {q}\nAssistant: {a}" for q, a in history) or "(none)"
    result = generate_json(REWRITE_SYSTEM, f"Conversation so far:\n{conversation}\n\nUser's message:\n{text}")
    query = str(result.get("english_query") or "").strip()
    if not query:
        raise LLMError("Query rewrite returned nothing.")
    return PreparedQuery(query, str(result.get("category") or "electoral_question"))


def format_evidence(evidence: list[Evidence]) -> str:
    blocks = []
    for number, item in enumerate(evidence, start=1):
        location = f"page {item.page}" if item.page else item.section or "web page"
        blocks.append(
            f"[{number}] STATUS: {item.status} | DATE: {item.publication_date or 'not stated'} | "
            f"RETRIEVED: {item.retrieved_date} | SOURCE: {item.title}, {location}\n"
            f"<passage>\n{item.text}\n</passage>"
        )
    return "\n\n".join(blocks)


def _invented_numbers(text: str, cited_evidence: list[Evidence]) -> list[str]:
    return citation_tools.unsupported_numbers(citation_tools.remove_today_mentions(text, date.today()), cited_evidence)


def _fallback_citations(evidence: list[Evidence], query: str) -> list[Citation]:
    """The best-matching passages first, then any time-critical notices. Old documents are left out,
    because here no AI or validation step is there to explain that they are old."""
    usable = [item for item in evidence if item.status in ("current", "needs_verification")]
    notices = [item for item in usable if item.document_id in TIME_CRITICAL_DOCUMENTS]
    others = [item for item in usable if item.document_id not in TIME_CRITICAL_DOCUMENTS]
    shown = others + notices
    markers = " ".join(f"[{number}]" for number in range(1, len(shown) + 1))
    return citation_tools.build_citations([markers], shown, query)[1]


def _factual_sources(cited: list[Citation]) -> list[Citation]:
    """The citations a result rests on. Notices are always current and get added for many topics,
    so citing one must not make an answer from old documents look current. A notice still counts
    when it is the only source, as with "is registration still open?"."""
    return [c for c in cited if c.document_id not in TIME_CRITICAL_DOCUMENTS] or cited


def _result_status(cited: list[Citation]) -> str:
    return "supported" if any(c.status == "current" for c in _factual_sources(cited)) else "outdated_only"


def _source_notices(cited: list[Citation], conflict: bool = False) -> list[str]:
    notices = []
    if conflict:
        notices.append("The sources do not fully agree on this. The answer follows the most recent one; please check with INEC.")
    if cited and not any(c.status == "current" for c in _factual_sources(cited)):
        notices.append("This answer relies only on older documents. The rules may have changed, so please confirm with INEC.")
    elif any(c.status in ("historical", "superseded") for c in cited):
        notices.append("Some sources are older documents and are included only for background.")
    return notices


def _translate_chat_answer(answer: str, language: str) -> tuple[str, str, list[str]]:
    """Translate and check. Falls back to clearly labelled English if the check fails."""
    if language == "en":
        return answer, "en", []
    translated = translate_texts([answer], language)
    if translated is None:
        return answer, "en", [message("language_fallback", language)]
    return translated[0], language, [UNREVIEWED_NOTICE]


def answer_question(text: str, language: str, session_id: str | None, allow_passages_fallback: bool = True) -> ChatResponse:
    """`allow_passages_fallback=False` lets evaluation runs see service failures instead of scoring them as answers."""
    started = time.perf_counter()
    start_request_deadline()
    session_id = session_id or _new_id()
    response_id = _new_id()

    def finish(answer, status, citations=(), notices=(), answered_in=None, english=None) -> ChatResponse:
        answered_in = answered_in or language
        record_response(response_id, "chat", language, status, int((time.perf_counter() - started) * 1000))
        return ChatResponse(
            response_id=response_id,
            answer=answer,
            language=language,
            answered_in=answered_in,
            english_answer=english,
            citations=list(citations),
            evidence_status=status,
            notices=list(notices),
            translation_reviewed=LANGUAGES[answered_in].human_reviewed,
            session_id=session_id,
        )

    # Identity details are removed first, so they reach neither the LLM nor the logs.
    clean_text, removed = scrub_sensitive(text)
    privacy_notices = [message("sensitive_removed", language)] if removed else []

    # Neutrality rules on the raw text. These need no LLM and cannot be talked around by it.
    policy = classify_policy(clean_text)
    if policy:
        return finish(message(policy, language), "declined", notices=privacy_notices)

    get_llm()  # Raises a clear configuration error before doing any work.

    # Steps 1 to 3: question, language, standalone English query.
    history = sessions.history(session_id)
    cache_key = answer_cache.key(clean_text, language) if not history and not removed else None
    cached = answer_cache.get(cache_key) if cache_key else None
    if cached:
        english_query, english_answer, response = cached
        sessions.append(session_id, english_query, english_answer)
        record_response(response_id, "chat", language, response.evidence_status, int((time.perf_counter() - started) * 1000))
        return response.model_copy(update={"response_id": response_id, "session_id": session_id})

    try:
        prepared = prepare_query(clean_text, language, history)
    except LLMUnavailableError:
        if language != "en":
            raise  # A service failure, not a message we failed to understand.
        prepared = PreparedQuery(clean_text, "electoral_question")  # The follow-up may lose some context.
    except LLMError:
        if language == "en":
            raise
        return finish(message("language_unavailable", language), "insufficient", notices=privacy_notices)

    policy = classify_policy(prepared.english_query) or POLICY_BY_CATEGORY.get(prepared.category)
    if policy:
        return finish(message(policy, language), "declined", notices=privacy_notices)

    # Steps 4 to 6: search, threshold, rank. Nothing relevant means no LLM call at all.
    evidence = retrieve(prepared.english_query)
    if not evidence:
        return finish(message("abstain", language), "insufficient", notices=privacy_notices)

    # Steps 7 and 8: generate only from evidence.
    prompt = (
        f"TODAY'S DATE: {date.today().isoformat()}\n\nEVIDENCE:\n{format_evidence(evidence)}\n\n"
        f"QUESTION:\n{prepared.english_query}"
    )
    try:
        result = generate_json(ANSWER_SYSTEM, prompt)
    except LLMUnavailableError:
        citations = _fallback_citations(evidence, prepared.english_query) if allow_passages_fallback else []
        if not citations:
            raise
        fallback_notices = [message("language_fallback", language)] if language != "en" else []
        return finish(PASSAGES_ONLY_ANSWER, "passages_only", citations, privacy_notices + fallback_notices, answered_in="en")

    # English first questions skip the rewrite step, so this is where the model's judgement applies.
    policy = POLICY_BY_CATEGORY.get(result.get("category"))
    if policy:
        return finish(message(policy, language), "declined", notices=privacy_notices)
    if result.get("status") != "answered" or not str(result.get("answer") or "").strip():
        return finish(message("abstain", language), "insufficient", notices=privacy_notices)

    # Step 9: validate. Any failure means abstaining rather than showing a weak answer.
    answer = citation_tools.strip_links(str(result["answer"]))
    (answer,), cited = citation_tools.build_citations([answer], evidence, prepared.english_query)
    cited_evidence = citation_tools.cited_passages(evidence, cited)
    if (
        not cited
        or _invented_numbers(answer, cited_evidence)
        or citation_tools.uncited_ratio(answer) > MAX_UNCITED_RATIO
    ):
        return finish(message("abstain", language), "insufficient", notices=privacy_notices)

    sessions.append(session_id, prepared.english_query, answer)

    # Translation happens last, and is checked, so grounding was validated on the English text.
    final_answer, answered_in, language_notices = _translate_chat_answer(answer, language)
    response = finish(
        final_answer,
        _result_status(cited),
        cited,
        privacy_notices + _source_notices(cited, bool(result.get("conflict"))) + language_notices,
        answered_in,
        english=answer if answered_in != "en" else None,
    )
    if cache_key and answered_in == language:  # A failed translation may work next time.
        answer_cache.put(cache_key, prepared.english_query, answer, response)
    return response


STANDARD_LIMITATIONS = [
    "This check only uses the official documents in our library. It does not cover every INEC statement or very recent announcements.",
    "This is an automated comparison, not an official ruling or a judgement about anyone's honesty. Please confirm important details with INEC.",
]
INSUFFICIENT_EXPLANATION = (
    "We could not find official information in our library that confirms or contradicts this statement. "
    "This does not mean the statement is false."
)


def _as_text_list(value) -> list[str]:
    return [str(item).strip() for item in value if str(item).strip()] if isinstance(value, list) else []


def verify_claim(claim: str, language: str) -> VerifyResponse:
    started = time.perf_counter()
    start_request_deadline()
    response_id = _new_id()
    clean_claim, removed = scrub_sensitive(claim)
    limitations = list(STANDARD_LIMITATIONS)

    def declined(policy: str) -> VerifyResponse:
        """Partisan claims, forecasts and unrelated text get the same fixed reply as in chat, and no verdict."""
        record_response(response_id, "verify", language, "declined", int((time.perf_counter() - started) * 1000))
        return VerifyResponse(
            response_id=response_id,
            assessment="insufficient_evidence",
            explanation=message(policy, language),
            supporting_sources=[],
            limitations=[message("sensitive_removed", language)] if removed else [],
            language=language,
            answered_in=language,
            translation_reviewed=LANGUAGES[language].human_reviewed,
        )

    policy = classify_policy(clean_claim)
    if policy:
        return declined(policy)

    get_llm()
    prepared = prepare_query(clean_claim, language, [])
    policy = classify_policy(prepared.english_query) or POLICY_BY_CATEGORY.get(prepared.category)
    if policy:
        return declined(policy)
    evidence = retrieve(prepared.english_query)

    assessment, explanation = "insufficient_evidence", INSUFFICIENT_EXPLANATION
    supports: list[str] = []
    contradicts: list[str] = []
    cannot_establish: list[str] = []
    cited: list[Citation] = []

    if evidence:
        prompt = (
            f"TODAY'S DATE: {date.today().isoformat()}\n\nEVIDENCE:\n{format_evidence(evidence)}\n\n"
            f"CLAIM:\n{prepared.english_query}"
        )
        result = generate_json(VERIFY_SYSTEM, prompt)
        policy = POLICY_BY_CATEGORY.get(result.get("category"))
        if policy:
            return declined(policy)
        raw_assessment = result.get("assessment")
        supports = _as_text_list(result.get("supports"))
        contradicts = _as_text_list(result.get("contradicts"))
        cannot_establish = _as_text_list(result.get("cannot_establish"))
        raw_explanation = citation_tools.strip_links(str(result.get("explanation") or ""))

        all_texts = [raw_explanation, *supports, *contradicts, *cannot_establish]
        rewritten, cited = citation_tools.build_citations(all_texts, evidence, prepared.english_query)
        explanation_text = rewritten[0]
        supports = rewritten[1:1 + len(supports)]
        contradicts = rewritten[1 + len(supports):1 + len(supports) + len(contradicts)]
        cannot_establish = rewritten[1 + len(supports) + len(contradicts):]

        cited_evidence = citation_tools.cited_passages(evidence, cited)
        decisive = {"supported", "contradicted"}
        usable_sources = any(c.status in ("current", "needs_verification") for c in _factual_sources(cited))
        numbers_ok = not _invented_numbers(" ".join(rewritten), cited_evidence)

        # A verdict needs real, current-enough citations. Otherwise it is downgraded, never kept.
        if raw_assessment in decisive and usable_sources and numbers_ok and raw_explanation:
            assessment, explanation = raw_assessment, explanation_text
        else:
            supports, contradicts = [], []
            if raw_assessment == "insufficient_evidence" and explanation_text and numbers_ok:
                explanation = explanation_text
            else:
                explanation, cited, cannot_establish = INSUFFICIENT_EXPLANATION, [], []
                limitations.append("A possible match was found, but it did not pass our citation or recency checks.")

    if assessment == "insufficient_evidence" and not cannot_establish:
        cannot_establish = ["Whether this statement is accurate, based on the documents we hold."]
    if any(c.status in ("needs_verification", "historical", "superseded") for c in cited):
        limitations.append("Some sources predate or may not reflect the Electoral Act 2026, so details may have changed.")

    answered_in = language
    if language != "en":
        blocks = [explanation, *supports, *contradicts, *cannot_establish, *limitations]
        translated = translate_texts(blocks, language)
        if translated is None:
            answered_in = "en"
            limitations = [message("language_fallback", language), *limitations]
        else:
            explanation = translated[0]
            offset = 1
            supports = translated[offset:offset + len(supports)]; offset += len(supports)
            contradicts = translated[offset:offset + len(contradicts)]; offset += len(contradicts)
            cannot_establish = translated[offset:offset + len(cannot_establish)]; offset += len(cannot_establish)
            limitations = translated[offset:] + [UNREVIEWED_NOTICE]

    # This fixed message already exists in each language, so it joins after translation.
    if removed:
        limitations.append(message("sensitive_removed", language))

    record_response(response_id, "verify", language, assessment, int((time.perf_counter() - started) * 1000))
    return VerifyResponse(
        response_id=response_id,
        assessment=assessment,
        explanation=explanation,
        supports=supports,
        contradicts=contradicts,
        cannot_establish=cannot_establish,
        supporting_sources=cited,
        limitations=limitations,
        language=language,
        answered_in=answered_in,
        translation_reviewed=LANGUAGES[answered_in].human_reviewed,
    )

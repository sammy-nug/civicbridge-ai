"""API behaviour with the LLM and retrieval replaced, to force failures a real model rarely shows.

The fakes exist only in this test file. Real-model behaviour is measured in evaluation/.
"""
import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from app.config import get_settings
from app.services import llm as llm_module
from app.services import rag
from app.services.llm import LLMCapacityError, LLMError, LLMNotConfiguredError, LLMUnavailableError
from app.utils import rate_limit
from tests.test_citations import evidence


@pytest.fixture
def fake_pipeline(monkeypatch):
    """Returns a dict the test fills with what each LLM task should return."""
    replies = {"answer": {"status": "answered", "answer": "Apply 90 days before polling day [1].", "conflict": False}}
    calls = {"llm": 0, "prompts": []}

    def fake_generate_json(system, prompt):
        calls["llm"] += 1
        calls["prompts"].append(prompt)
        if "preparing" in system or "document library" in system:
            return replies.get("rewrite", {"english_query": "How do I replace a PVC?", "category": "electoral_question"})
        if "compare a CLAIM" in system:
            return replies["verify"]
        return replies["answer"]

    monkeypatch.setattr(rag, "generate_json", fake_generate_json)
    monkeypatch.setattr(rag, "get_llm", lambda: object())
    monkeypatch.setattr(rag, "retrieve", lambda query, **_: replies.get("evidence", [evidence()]))
    replies["calls"] = calls
    return replies


def test_supported_answer_has_real_citation(client, fake_pipeline):
    body = client.post("/api/chat", json={"message": "How do I replace a PVC?"}).json()
    assert body["evidence_status"] == "supported"
    assert body["citations"][0]["url"] == "https://example.org/doc-a.pdf"
    assert body["session_id"] and body["response_id"]


def test_no_evidence_abstains_without_calling_the_llm(client, fake_pipeline):
    fake_pipeline["evidence"] = []
    body = client.post("/api/chat", json={"message": "What colour is the moon?"}).json()
    assert body["evidence_status"] == "insufficient"
    assert body["citations"] == []
    assert fake_pipeline["calls"]["llm"] == 0


def test_invented_citation_causes_abstention(client, fake_pipeline):
    fake_pipeline["answer"] = {"status": "answered", "answer": "Apply 90 days before [7].", "conflict": False}
    body = client.post("/api/chat", json={"message": "How do I replace a PVC?"}).json()
    assert body["evidence_status"] == "insufficient"
    assert body["citations"] == []


def test_invented_number_causes_abstention(client, fake_pipeline):
    fake_pipeline["answer"] = {"status": "answered", "answer": "Apply 45 days before polling day [1].", "conflict": False}
    body = client.post("/api/chat", json={"message": "How do I replace a PVC?"}).json()
    assert body["evidence_status"] == "insufficient"


def test_answer_without_citations_is_not_shown(client, fake_pipeline):
    fake_pipeline["answer"] = {"status": "answered", "answer": "Just go to the office and ask them.", "conflict": False}
    body = client.post("/api/chat", json={"message": "How do I replace a PVC?"}).json()
    assert body["evidence_status"] == "insufficient"
    assert "Just go" not in body["answer"]


def test_model_can_abstain(client, fake_pipeline):
    fake_pipeline["answer"] = {"status": "insufficient", "answer": "", "conflict": False}
    assert client.post("/api/chat", json={"message": "Something"}).json()["evidence_status"] == "insufficient"


def test_only_old_sources_are_flagged(client, fake_pipeline):
    fake_pipeline["evidence"] = [evidence(status="superseded")]
    body = client.post("/api/chat", json={"message": "How do I replace a PVC?"}).json()
    assert body["evidence_status"] == "outdated_only"
    assert any("older documents" in notice for notice in body["notices"])


def test_partisan_question_is_declined_without_llm(client, fake_pipeline):
    body = client.post("/api/chat", json={"message": "Who should I vote for?"}).json()
    assert body["evidence_status"] == "declined"
    assert fake_pipeline["calls"]["llm"] == 0


def test_partisan_question_in_another_language_is_declined(client, fake_pipeline):
    fake_pipeline["rewrite"] = {"english_query": "Who should I vote for?", "category": "partisan_request"}
    body = client.post("/api/chat", json={"message": "Wa zan zaɓa?", "language": "ha"}).json()
    assert body["evidence_status"] == "declined"
    assert "Ba zan iya" in body["answer"]


def test_personal_details_never_reach_the_llm(client, fake_pipeline):
    body = client.post("/api/chat", json={"message": "My NIN is 12345678901. How do I replace my PVC?", "language": "en"}).json()
    assert any("removed" in notice for notice in body["notices"])
    assert all("12345678901" not in prompt for prompt in fake_pipeline["calls"]["prompts"])


def test_failed_translation_falls_back_to_labelled_english(client, fake_pipeline, monkeypatch):
    monkeypatch.setattr(rag, "translate_texts", lambda texts, language: None)
    body = client.post("/api/chat", json={"message": "Ta yaya zan maye gurbin PVC?", "language": "ha"}).json()
    assert body["language"] == "ha"
    assert body["answered_in"] == "en"
    assert body["translation_reviewed"] is True  # English is the reviewed language.
    assert body["answer"].startswith("Apply 90 days")


def test_successful_translation_is_labelled_unreviewed(client, fake_pipeline, monkeypatch):
    monkeypatch.setattr(rag, "translate_texts", lambda texts, language: ["Ka nema kwanaki 90 kafin ranar zaɓe [1]."])
    body = client.post("/api/chat", json={"message": "Ta yaya zan maye gurbin PVC?", "language": "ha"}).json()
    assert body["answered_in"] == "ha"
    assert body["translation_reviewed"] is False
    assert body["english_answer"].startswith("Apply 90 days")
    assert any("not been reviewed" in notice for notice in body["notices"])


def test_follow_up_uses_conversation_history(client, fake_pipeline):
    first = client.post("/api/chat", json={"message": "How do I replace a PVC?"}).json()
    client.post("/api/chat", json={"message": "How long does it take?", "session_id": first["session_id"]})
    assert any("Conversation so far" in p and "Apply 90 days" in p for p in fake_pipeline["calls"]["prompts"])


def test_missing_key_gives_503_not_a_fake_answer(client, monkeypatch):
    def not_configured():
        raise LLMNotConfiguredError("GEMINI_API_KEY is not set")
    monkeypatch.setattr(rag, "get_llm", not_configured)
    response = client.post("/api/chat", json={"message": "How do I vote?"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "llm_not_configured"


def test_llm_failure_gives_502(client, fake_pipeline, monkeypatch):
    def broken(system, prompt):
        raise LLMError("gemini: HTTP 500")
    monkeypatch.setattr(rag, "generate_json", broken)
    response = client.post("/api/chat", json={"message": "How do I vote?"})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "llm_unavailable"
    assert "gemini" not in response.text  # Internal details stay in the logs.


def test_service_failure_in_nigerian_language_gives_502(client, fake_pipeline, monkeypatch):
    def broken(system, prompt):
        raise LLMUnavailableError("gemini: HTTP 429")
    monkeypatch.setattr(rag, "generate_json", broken)
    response = client.post("/api/chat", json={"message": "Ta yaya zan maye gurbin PVC?", "language": "ha"})
    assert response.status_code == 502  # Not "we could not understand your message".
    assert response.json()["error"]["code"] == "llm_unavailable"


def test_unusable_rewrite_in_nigerian_language_still_asks_to_retry(client, fake_pipeline, monkeypatch):
    def unusable(system, prompt):
        raise LLMError("The model did not return valid JSON.")
    monkeypatch.setattr(rag, "generate_json", unusable)
    response = client.post("/api/chat", json={"message": "Ta yaya zan maye gurbin PVC?", "language": "ha"})
    assert response.status_code == 200
    assert response.json()["evidence_status"] == "insufficient"


@pytest.mark.parametrize("status, expected_calls", [(429, 1), (503, llm_module.MAX_ATTEMPTS)])
def test_used_up_quota_is_not_retried_but_overload_is(monkeypatch, status, expected_calls):
    calls = []

    def fake_post(*args, **kwargs):
        calls.append(1)
        return llm_module.httpx.Response(status)
    monkeypatch.setattr(llm_module.httpx, "post", fake_post)
    monkeypatch.setattr(llm_module.time, "sleep", lambda _: None)
    with pytest.raises(LLMUnavailableError):
        llm_module._post_with_retries("https://example.test", {}, {}, "gemini")
    assert len(calls) == expected_calls


@pytest.mark.parametrize("payload", [
    {},
    {"message": ""},
    {"message": "   "},
    {"message": "x" * 1001},
    {"message": "hello", "language": "fr"},
    {"message": "hello", "session_id": "bad id!"},
])
def test_invalid_chat_requests_get_422(client, payload):
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


def test_validation_errors_do_not_echo_input(client):
    response = client.post("/api/chat", json={"message": "hello 12345678901", "language": "fr"})
    assert "12345678901" not in response.text


def test_rate_limit_returns_429(client, fake_pipeline, monkeypatch):
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "rate_limit_per_minute", 2)
    rate_limit._requests.clear()
    codes = [client.post("/api/chat", json={"message": "How do I vote?"}).status_code for _ in range(3)]
    rate_limit._requests.clear()
    assert codes == [200, 200, 429]


# --- Verification -------------------------------------------------------------------------

def test_claim_supported(client, fake_pipeline):
    fake_pipeline["verify"] = {"assessment": "supported", "explanation": "The Act says 90 days [1].", "supports": ["90 days [1]"], "contradicts": [], "cannot_establish": []}
    body = client.post("/api/verify", json={"claim": "You must apply 90 days before polling day"}).json()
    assert body["assessment"] == "supported"
    assert body["supporting_sources"][0]["url"].startswith("https://example.org")
    assert body["limitations"]


def test_no_evidence_is_insufficient_not_false(client, fake_pipeline):
    fake_pipeline["evidence"] = []
    body = client.post("/api/verify", json={"claim": "INEC will give every voter a free phone"}).json()
    assert body["assessment"] == "insufficient_evidence"
    assert "does not mean the statement is false" in body["explanation"]
    assert fake_pipeline["calls"]["llm"] == 0


def test_verdict_without_valid_citation_is_downgraded(client, fake_pipeline):
    fake_pipeline["verify"] = {"assessment": "contradicted", "explanation": "This is wrong [9].", "supports": [], "contradicts": ["wrong [9]"], "cannot_establish": []}
    body = client.post("/api/verify", json={"claim": "You can vote without a PVC"}).json()
    assert body["assessment"] == "insufficient_evidence"
    assert body["contradicts"] == []


def test_superseded_evidence_cannot_decide_a_claim(client, fake_pipeline):
    fake_pipeline["evidence"] = [evidence(status="superseded")]
    fake_pipeline["verify"] = {"assessment": "contradicted", "explanation": "Old rules disagree, 90 days [1].", "supports": [], "contradicts": [], "cannot_establish": []}
    body = client.post("/api/verify", json={"claim": "You can apply at any time"}).json()
    assert body["assessment"] == "insufficient_evidence"


# --- Feedback, resources and health -------------------------------------------------------

def test_feedback_recorded_and_scrubbed(client, fake_pipeline, tmp_path):
    import sqlite3
    response_id = client.post("/api/chat", json={"message": "How do I vote?"}).json()["response_id"]
    response = client.post("/api/feedback", json={"response_id": response_id, "rating": "not_helpful", "feedback": "Wrong. My NIN is 12345678901"})
    assert response.status_code == 201
    stored = sqlite3.connect(tmp_path / "civicbridge.sqlite3").execute("SELECT comment FROM feedback").fetchone()[0]
    assert "12345678901" not in stored


def test_questions_are_not_written_to_the_database(client, fake_pipeline, tmp_path):
    client.post("/api/chat", json={"message": "UNIQUEMARKERQUESTION how do I vote?"})
    assert b"UNIQUEMARKERQUESTION" not in (tmp_path / "civicbridge.sqlite3").read_bytes()


def test_feedback_for_unknown_response_gets_404(client):
    response = client.post("/api/feedback", json={"response_id": "00000000-0000", "rating": "helpful"})
    assert response.status_code == 404


def test_invalid_rating_gets_422(client):
    assert client.post("/api/feedback", json={"response_id": "abcdefgh", "rating": "bad"}).status_code == 422


def test_resources_lists_documents_with_real_metadata(client):
    body = client.get("/api/resources").json()
    assert body["total"] >= 1
    for document in body["documents"]:
        assert document["url"].startswith("https://")
        assert document["retrieved_date"]


def test_resources_search_filters(client):
    all_documents = client.get("/api/resources").json()["total"]
    assert client.get("/api/resources", params={"q": "zzzznotthere"}).json()["total"] == 0
    assert all_documents >= client.get("/api/resources", params={"q": "electoral"}).json()["total"] >= 1


def test_health_reports_language_review_status(client):
    body = client.get("/api/health").json()
    reviewed = {language["code"]: language["human_reviewed"] for language in body["languages"]}
    assert reviewed == {"en": True, "ha": False, "yo": False, "ig": False}


def _limited_app(limit_dependency):
    app = FastAPI()

    @app.get("/limited", dependencies=[Depends(limit_dependency)])
    def limited():
        return {}
    return TestClient(app)


def test_spoofed_forwarded_header_cannot_dodge_the_rate_limit(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "trust_proxy_headers", True)
    monkeypatch.setattr(settings, "rate_limit_per_minute", 3)
    rate_limit._requests.clear()
    client = _limited_app(rate_limit.enforce_rate_limit)
    codes = [client.get("/limited", headers={"X-Forwarded-For": f"10.0.0.{i}, 1.2.3.4"}).status_code for i in range(5)]
    rate_limit._requests.clear()
    assert codes == [200, 200, 200, 429, 429]


def test_proxy_hops_pick_the_right_address(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "trust_proxy_headers", True)
    monkeypatch.setattr(settings, "trusted_proxy_hops", 2)
    request = Request({"type": "http", "headers": [(b"x-forwarded-for", b"6.6.6.6, 1.2.3.4, 9.9.9.9")], "client": ("8.8.8.8", 1)})
    assert rate_limit._client_key(request) == "1.2.3.4"


def test_daily_limit_per_client(monkeypatch):
    monkeypatch.setattr(get_settings(), "rate_limit_per_day", 2)
    client = _limited_app(rate_limit.enforce_daily_limit)
    assert [client.get("/limited").status_code for _ in range(3)] == [200, 200, 429]


def test_daily_cap_stops_calls_before_they_are_sent(monkeypatch):
    calls = []

    def fake_post(*args, **kwargs):
        calls.append(1)
        return llm_module.httpx.Response(200, json={})
    monkeypatch.setattr(get_settings(), "llm_daily_request_limit", 2)
    monkeypatch.setattr(llm_module.httpx, "post", fake_post)
    monkeypatch.setitem(llm_module._daily_calls, "date", None)
    llm_module._post_with_retries("https://example.test", {}, {}, "gemini")
    llm_module._post_with_retries("https://example.test", {}, {}, "gemini")
    with pytest.raises(LLMCapacityError):
        llm_module._post_with_retries("https://example.test", {}, {}, "gemini")
    assert len(calls) == 2


def test_passed_deadline_stops_further_calls(monkeypatch):
    calls = []
    monkeypatch.setattr(llm_module.httpx, "post", lambda *a, **k: calls.append(1))
    monkeypatch.setattr(get_settings(), "request_deadline_seconds", -1)
    llm_module.start_request_deadline()
    try:
        with pytest.raises(LLMUnavailableError):
            llm_module._post_with_retries("https://example.test", {}, {}, "gemini")
    finally:
        llm_module._deadline.set(None)
    assert calls == []


def test_busy_slots_fail_fast_and_are_released(monkeypatch):
    monkeypatch.setattr(llm_module, "SLOT_WAIT_SECONDS", 0.01)
    monkeypatch.setattr(llm_module.httpx, "post", lambda *a, **k: llm_module.httpx.Response(400))
    slots = llm_module._call_slots()
    taken = 0
    while slots.acquire(blocking=False):
        taken += 1
    try:
        with pytest.raises(LLMUnavailableError, match="too many"):
            llm_module._post_with_retries("https://example.test", {}, {}, "gemini")
    finally:
        for _ in range(taken):
            slots.release()
    with pytest.raises(LLMUnavailableError, match="HTTP 400"):
        llm_module._post_with_retries("https://example.test", {}, {}, "gemini")
    assert slots.acquire(blocking=False)
    slots.release()


def test_capacity_error_gets_a_clear_message(client, fake_pipeline, monkeypatch):
    def full(system, prompt):
        raise LLMCapacityError("gemini: HTTP 429")
    monkeypatch.setattr(rag, "generate_json", full)
    fake_pipeline["evidence"] = [evidence(status="superseded")]  # Nothing safe to show instead.
    response = client.post("/api/chat", json={"message": "How do I replace a PVC?"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "at_capacity"


def _ai_down(monkeypatch):
    def down(system, prompt):
        raise LLMUnavailableError("gemini: HTTP 503")
    monkeypatch.setattr(rag, "generate_json", down)


def test_ai_outage_shows_official_passages(client, fake_pipeline, monkeypatch):
    _ai_down(monkeypatch)
    fake_pipeline["evidence"] = [
        evidence(chunk="old", doc="old-doc", status="superseded"),
        evidence(chunk="a", doc="doc-a"), evidence(chunk="b", doc="doc-b"), evidence(chunk="c", doc="doc-c"),
        evidence(chunk="n", doc="cvr-portal-notice", page=None), evidence(chunk="d", doc="doc-d"),
    ]
    body = client.post("/api/chat", json={"message": "How do I replace a PVC?"}).json()
    assert body["evidence_status"] == "passages_only"
    assert "not a written answer" in body["answer"]
    documents = [c["document_id"] for c in body["citations"]]
    assert documents == ["doc-a", "doc-b", "doc-c", "doc-d", "cvr-portal-notice"]  # Old document left out.


def test_ai_outage_with_only_old_documents_is_an_error(client, fake_pipeline, monkeypatch):
    _ai_down(monkeypatch)
    fake_pipeline["evidence"] = [evidence(status="historical")]
    assert client.post("/api/chat", json={"message": "How do I replace a PVC?"}).status_code == 502


def test_ai_outage_passages_are_labelled_english_for_other_languages(client, fake_pipeline, monkeypatch):
    outcomes = iter([{"english_query": "How do I replace a PVC?", "category": "electoral_question"}, LLMUnavailableError("gemini: HTTP 503")])

    def rewrite_then_down(system, prompt):
        outcome = next(outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
    monkeypatch.setattr(rag, "generate_json", rewrite_then_down)
    body = client.post("/api/chat", json={"message": "Ta yaya zan maye gurbin PVC?", "language": "ha"}).json()
    assert body["evidence_status"] == "passages_only"
    assert body["answered_in"] == "en"
    assert body["notices"]


def test_evaluation_can_turn_the_passages_fallback_off(fake_pipeline, monkeypatch):
    _ai_down(monkeypatch)
    with pytest.raises(LLMUnavailableError):
        rag.answer_question("How do I replace a PVC?", "en", None, allow_passages_fallback=False)


def test_repeat_question_reuses_the_answer_without_calling_the_llm(client, fake_pipeline):
    first = client.post("/api/chat", json={"message": "How do I replace a PVC?"}).json()
    calls = fake_pipeline["calls"]["llm"]
    second = client.post("/api/chat", json={"message": "  how do I  REPLACE a pvc? "}).json()
    assert fake_pipeline["calls"]["llm"] == calls
    assert second["answer"] == first["answer"] and second["citations"] == first["citations"]
    assert second["response_id"] != first["response_id"] and second["session_id"] != first["session_id"]
    feedback = client.post("/api/feedback", json={"response_id": second["response_id"], "rating": "helpful"})
    assert feedback.status_code == 201
    assert rag.sessions.history(second["session_id"])


def test_abstentions_and_follow_ups_are_not_cached(client, fake_pipeline):
    fake_pipeline["answer"] = {"status": "insufficient", "answer": "", "conflict": False}
    client.post("/api/chat", json={"message": "How do I replace a PVC?"})
    client.post("/api/chat", json={"message": "How do I replace a PVC?"})
    assert fake_pipeline["calls"]["llm"] == 2
    fake_pipeline["answer"] = {"status": "answered", "answer": "Apply 90 days before polling day [1].", "conflict": False}
    session = client.post("/api/chat", json={"message": "First question here"}).json()["session_id"]
    calls = fake_pipeline["calls"]["llm"]
    client.post("/api/chat", json={"message": "First question here", "session_id": session})
    assert fake_pipeline["calls"]["llm"] > calls


def test_questions_with_removed_details_are_not_cached(client, fake_pipeline):
    for _ in range(2):
        client.post("/api/chat", json={"message": "My NIN is 12345678901. How do I replace my PVC?"})
    assert fake_pipeline["calls"]["llm"] == 2


@pytest.mark.parametrize("category, expected", [
    ("partisan_request", "can't recommend"), ("prediction_request", None), ("off_topic", "only help"),
])
def test_model_category_declines_english_first_questions(client, fake_pipeline, category, expected):
    fake_pipeline["answer"] = {"status": "answered", "answer": "APC should win [1].", "conflict": False, "category": category}
    body = client.post("/api/chat", json={"message": "Should APC or PDP win?"}).json()
    assert body["evidence_status"] == "declined"
    assert body["citations"] == []
    assert "APC" not in body["answer"]
    if expected:
        assert expected in body["answer"]


def test_partisan_claim_gets_no_verdict_or_llm_call(client, fake_pipeline):
    body = client.post("/api/verify", json={"claim": "APC is the best party, so who should I vote for?"}).json()
    assert body["assessment"] == "insufficient_evidence"
    assert body["supporting_sources"] == []
    assert fake_pipeline["calls"]["llm"] == 0


def test_model_category_declines_claims(client, fake_pipeline):
    fake_pipeline["verify"] = {"assessment": "supported", "explanation": "PDP is better [1].", "category": "partisan_request"}
    body = client.post("/api/verify", json={"claim": "PDP has always been far better than APC"}).json()
    assert body["assessment"] == "insufficient_evidence"
    assert "PDP" not in body["explanation"]


def test_citing_a_notice_does_not_make_old_documents_look_current(client, fake_pipeline):
    fake_pipeline["evidence"] = [
        evidence(chunk="old", doc="old-guide", status="superseded"),
        evidence(chunk="n", doc="cvr-portal-notice", page=None),
    ]
    fake_pipeline["answer"] = {"status": "answered", "answer": "Apply 90 days before polling day [1]. Check the portal [2].", "conflict": False}
    body = client.post("/api/chat", json={"message": "How do I replace a PVC?"}).json()
    assert body["evidence_status"] == "outdated_only"
    assert any("older documents" in notice for notice in body["notices"])


def test_a_notice_on_its_own_counts_as_current(client, fake_pipeline):
    fake_pipeline["evidence"] = [evidence(chunk="n", doc="cvr-portal-notice", page=None)]
    fake_pipeline["answer"] = {"status": "answered", "answer": "Apply 90 days before polling day [1].", "conflict": False}
    assert client.post("/api/chat", json={"message": "Is registration still open?"}).json()["evidence_status"] == "supported"


def test_verdict_cannot_rest_on_old_documents_plus_a_notice(client, fake_pipeline):
    fake_pipeline["evidence"] = [
        evidence(chunk="old", doc="old-guide", status="historical"),
        evidence(chunk="n", doc="inec-election-calendar", page=None),
    ]
    fake_pipeline["verify"] = {"assessment": "supported", "explanation": "This is right [1]. See also [2].", "supports": [], "contradicts": [], "cannot_establish": []}
    body = client.post("/api/verify", json={"claim": "You may apply 90 days before polling"}).json()
    assert body["assessment"] == "insufficient_evidence"

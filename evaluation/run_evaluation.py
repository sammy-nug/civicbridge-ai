"""Measure CivicBridge AI against evaluation/test_questions.json and write real results.

  retrieval     needs no LLM: retrieval quality and threshold analysis
  answers       needs an LLM: accuracy, citations, abstention, latency (English)
  claims        needs an LLM: verification accuracy
  multilingual  needs an LLM: language handling, plus a sheet for human reviewers

Usage (from the repo root):
  backend/.venv/bin/python evaluation/run_evaluation.py retrieval
  backend/.venv/bin/python evaluation/run_evaluation.py answers --limit 5

Results go to evaluation/results/. Nothing here is hand-edited: if a run fails, it says so.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
RESULTS_DIR = ROOT / "evaluation" / "results"

from app.config import get_settings  # noqa: E402
from app.services.embeddings import get_embedder  # noqa: E402
from app.services import language as language_module  # noqa: E402
from app.services.llm import LLMError, LLMUnavailableError, is_llm_configured  # noqa: E402
from app.services.rag import answer_question, verify_claim  # noqa: E402
from app.services.retrieval import get_store, retrieve  # noqa: E402

DATASET = json.loads((ROOT / "evaluation" / "test_questions.json").read_text(encoding="utf-8"))
KNOWN_URLS = {
    doc["id"]: doc["url"] for doc in json.loads((ROOT / "knowledge_base" / "sources.json").read_text(encoding="utf-8"))["documents"]
}


LABEL = ""  # Keeps runs with different models apart, e.g. answers-local.json
RESUME = False  # Keep finished rows from the saved file, for running across several days on a small quota.
PAUSE_SECONDS = 0.0  # Wait before each question, to stay under per-minute limits.


class TranslationUnavailable(Exception):
    """The service failed during translation. The app falls back to English, but a score must not count that."""


def _generate_json_for_translation(system: str, prompt: str) -> dict:
    try:
        return _original_translation_generate(system, prompt)
    except LLMUnavailableError as error:
        raise TranslationUnavailable(str(error)) from error


_original_translation_generate = language_module.generate_json


def load_finished(name: str) -> dict[str, dict]:
    """Rows that already have a result. Rows that hit an error are left out, so they run again."""
    path = RESULTS_DIR / f"{f'{name}-{LABEL}' if LABEL else name}.json"
    if not RESUME or not path.exists():
        return {}
    saved = json.loads(path.read_text(encoding="utf-8"))
    if saved["run"]["llm_model"] != get_settings().llm_model:
        sys.exit(f"{path.name} was made with {saved['run']['llm_model']}, not {get_settings().llm_model}. Refusing to mix models.")
    return {row["id"]: row for row in saved.get("questions", saved.get("claims", [])) if "error" not in row}


def quota_used_up(error: Exception) -> bool:
    if "HTTP 429" not in str(error):
        return False
    print("\nHTTP 429: quota used up. Stopping here; run again later with --resume.", flush=True)
    return True


def save(name: str, payload: dict) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{name}-{LABEL}" if LABEL else name
    settings = get_settings()
    payload["run"] = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "embedding_backend": settings.embedding_backend,
        "top_k": settings.retrieval_top_k,
        "similarity_threshold": settings.similarity_threshold,
    }
    (RESULTS_DIR / f"{name}.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved evaluation/results/{name}.json")


def percent(part: int, whole: int) -> float | None:
    return round(100 * part / whole, 1) if whole else None


def includes_all(text: str, groups: list[list[str]]) -> bool:
    lowered = text.lower()
    return all(any(option.lower() in lowered for option in group) for group in groups)


# --- Retrieval ----------------------------------------------------------------------------

def require_index() -> None:
    """An empty index would score "100% abstention", which looks good and means nothing."""
    if get_store().count() == 0:
        sys.exit("The vector store is empty. Run ingestion first. No results were written.")


def run_retrieval() -> None:
    require_index()
    answerable = [q for q in DATASET["questions"] if q["expect"] == "answer"]
    out_of_scope = [q for q in DATASET["questions"] if q["expect"] == "abstain"]
    settings = get_settings()

    rows = []
    for q in answerable:
        started = time.perf_counter()
        evidence = retrieve(q["question"])
        latency = (time.perf_counter() - started) * 1000
        documents = [e.document_id for e in evidence]
        relevant = sum(1 for d in documents if d in q["expected_documents"])
        first_rank = next((i + 1 for i, d in enumerate(documents) if d in q["expected_documents"]), None)
        # The first expected document is the one that matters most. Counting any listed
        # document as a hit once hid the Electoral Act going missing for "lost PVC".
        primary_found = q["expected_documents"][0] in documents
        rows.append({
            "id": q["id"], "hit": first_rank is not None, "primary_found": primary_found, "first_relevant_rank": first_rank,
            "precision": relevant / len(documents) if documents else 0.0, "documents": documents,
            "top_similarity": round(evidence[0].similarity, 3) if evidence else None, "latency_ms": round(latency, 1),
        })

    # Raw best score per question, before any threshold, to choose the threshold from data.
    def best_score(question: str) -> float:
        matches = get_store().query(question, 1)
        return round(matches[0].similarity, 3) if matches else 0.0

    in_scores = {q["id"]: best_score(q["question"]) for q in answerable}
    out_scores = {q["id"]: best_score(q["question"]) for q in out_of_scope}
    sweep = []
    for threshold in [round(0.2 + 0.05 * i, 2) for i in range(11)]:
        sweep.append({
            "threshold": threshold,
            "answerable_kept_pct": percent(sum(s >= threshold for s in in_scores.values()), len(in_scores)),
            "out_of_scope_rejected_pct": percent(sum(s < threshold for s in out_scores.values()), len(out_scores)),
        })

    hits = sum(r["hit"] for r in rows)
    summary = {
        "questions": len(rows),
        "hit_rate_at_k_pct": percent(hits, len(rows)),
        "primary_source_found_pct": percent(sum(r["primary_found"] for r in rows), len(rows)),
        "mean_reciprocal_rank": round(statistics.mean(1 / r["first_relevant_rank"] if r["first_relevant_rank"] else 0 for r in rows), 3),
        "mean_precision_at_k_pct": round(100 * statistics.mean(r["precision"] for r in rows), 1),
        "median_latency_ms": round(statistics.median(r["latency_ms"] for r in rows), 1),
        "out_of_scope_with_no_evidence_pct": percent(sum(s < settings.similarity_threshold for s in out_scores.values()), len(out_scores)),
    }
    print(json.dumps(summary, indent=1))
    print("\nThreshold sweep:")
    for row in sweep:
        print(f"  {row['threshold']:.2f}  answerable kept {row['answerable_kept_pct']:5.1f}%   out-of-scope rejected {row['out_of_scope_rejected_pct']:5.1f}%")
    print("\nMisses:", [r["id"] for r in rows if not r["hit"]])
    print("Primary source missing:", [r["id"] for r in rows if not r["primary_found"]])
    print("Out-of-scope scores:", out_scores)
    print("Lowest answerable scores:", sorted(in_scores.items(), key=lambda kv: kv[1])[:6])
    save("retrieval", {"summary": summary, "threshold_sweep": sweep, "questions": rows, "in_scope_scores": in_scores, "out_of_scope_scores": out_scores})


# --- End-to-end answers --------------------------------------------------------------------

def citations_are_valid(citations: list) -> bool:
    return all(KNOWN_URLS.get(c.document_id) == c.url for c in citations)


def faithfulness_proxy(answer: str, citations: list) -> float | None:
    """Embedding similarity of each cited sentence to its cited passage. A proxy, not a proof."""
    by_number = {c.number: c for c in citations}
    scores = []
    for sentence in re.split(r"(?<=[.!?\]])\s+", answer):
        numbers = [int(n) for n in re.findall(r"\[(\d+)\]", sentence)]
        plain = re.sub(r"\[\d+\]", "", sentence).strip()
        passages = [by_number[n].excerpt for n in numbers if n in by_number]
        if len(plain) < 15 or not passages:
            continue
        sentence_vector, *passage_vectors = get_embedder().embed([plain, *passages])
        scores.append(max(sum(a * b for a, b in zip(sentence_vector, v)) for v in passage_vectors))
    return round(statistics.mean(scores), 3) if scores else None


def run_answers(limit: int | None, ids: set[str] | None) -> None:
    require_llm()
    questions = [q for q in DATASET["questions"] if not ids or q["id"] in ids][:limit]
    rows = []
    finished = load_finished("answers")
    for index, q in enumerate(questions, 1):
        if q["id"] in finished:
            rows.append(finished[q["id"]])
            continue
        time.sleep(PAUSE_SECONDS)
        started = time.perf_counter()
        row = {"id": q["id"], "category": q["category"], "expect": q["expect"], "question": q["question"]}
        try:
            response = answer_question(q["question"], "en", None, allow_passages_fallback=False)
        except LLMError as error:
            if quota_used_up(error):
                break
            row.update(error=str(error), passed=False, latency_s=round(time.perf_counter() - started, 1))
            rows.append(row)
            print(f"[{index}/{len(questions)}] {q['id']} LLM ERROR: {error}", flush=True)
            continue
        status = response.evidence_status
        answered = status in ("supported", "outdated_only")
        cited_docs = sorted({c.document_id for c in response.citations})
        row.update(
            status=status, answer=response.answer, cited_documents=cited_docs,
            notices=response.notices, latency_s=round(time.perf_counter() - started, 1),
            citation_urls_valid=citations_are_valid(response.citations),
        )
        if q["expect"] == "answer":
            row["answered"] = answered
            row["cited_expected_document"] = bool(set(cited_docs) & set(q["expected_documents"]))
            row["contains_expected_facts"] = answered and includes_all(response.answer, q.get("must_include", []))
            row["faithfulness_proxy"] = faithfulness_proxy(response.answer, response.citations) if answered else None
            row["passed"] = row["contains_expected_facts"] and row["cited_expected_document"]
        elif q["expect"] == "abstain":
            row["passed"] = status in ("insufficient", "declined")
        elif q["expect"] == "decline":
            row["passed"] = status == "declined"
        else:  # not_comply: refusing, or answering without repeating the false premise.
            row["passed"] = not any(bad in response.answer.lower() for bad in q.get("must_not_include", []))
        rows.append(row)
        print(f"[{index}/{len(questions)}] {q['id']} {'PASS' if row['passed'] else 'FAIL'} {status} {row['latency_s']}s", flush=True)

    answer_rows = [r for r in rows if r["expect"] == "answer"]
    answered_rows = [r for r in answer_rows if r.get("answered")]
    abstain_rows = [r for r in rows if r["expect"] == "abstain"]
    policy_rows = [r for r in rows if r["expect"] == "decline"]
    all_cited = [r for r in rows if r.get("cited_documents")]
    faithfulness = [r["faithfulness_proxy"] for r in answered_rows if r.get("faithfulness_proxy") is not None]
    latencies = [r["latency_s"] for r in rows if "latency_s" in r]
    summary = {
        "questions": len(rows),
        "not_yet_run": len(questions) - len(rows),
        "llm_errors": sum(1 for r in rows if "error" in r),
        "overall_pass_pct": percent(sum(r["passed"] for r in rows), len(rows)),
        "answer_rate_on_answerable_pct": percent(len(answered_rows), len(answer_rows)),
        "accuracy_expected_facts_pct_of_answerable": percent(sum(bool(r.get("contains_expected_facts")) for r in answer_rows), len(answer_rows)),
        "accuracy_expected_facts_pct_of_answered": percent(sum(bool(r.get("contains_expected_facts")) for r in answered_rows), len(answered_rows)),
        "citation_urls_valid_pct": percent(sum(r["citation_urls_valid"] for r in all_cited), len(all_cited)),
        "cited_expected_document_pct_of_answered": percent(sum(bool(r.get("cited_expected_document")) for r in answered_rows), len(answered_rows)),
        "faithfulness_proxy_mean": round(statistics.mean(faithfulness), 3) if faithfulness else None,
        "correct_abstention_pct": percent(sum(r["passed"] for r in abstain_rows), len(abstain_rows)),
        "correct_decline_pct": percent(sum(r["passed"] for r in policy_rows), len(policy_rows)),
        "latency_s_median": round(statistics.median(latencies), 1) if latencies else None,
        "latency_s_p95": round(sorted(latencies)[int(0.95 * (len(latencies) - 1))], 1) if latencies else None,
    }
    print(json.dumps(summary, indent=1))
    save("answers", {"summary": summary, "questions": rows})


def run_claims(limit: int | None) -> None:
    require_llm()
    rows = []
    claims = DATASET["claims"][:limit]
    finished = load_finished("claims")
    for index, item in enumerate(claims, 1):
        if item["id"] in finished:
            rows.append(finished[item["id"]])
            continue
        time.sleep(PAUSE_SECONDS)
        started = time.perf_counter()
        row = {"id": item["id"], "claim": item["claim"], "expect": item["expect"]}
        try:
            result = verify_claim(item["claim"], "en")
        except LLMError as error:
            if quota_used_up(error):
                break
            row.update(error=str(error), passed=False)
            rows.append(row)
            print(f"[{index}/{len(claims)}] {item['id']} LLM ERROR", flush=True)
            continue
        accusation = re.search(r"\b(fake news|liar|lied|propaganda|misinformation by)\b", result.explanation, re.IGNORECASE)
        row.update(
            assessment=result.assessment, explanation=result.explanation,
            cited_documents=sorted({c.document_id for c in result.supporting_sources}),
            passed=result.assessment == item["expect"], accusatory_language=bool(accusation),
            latency_s=round(time.perf_counter() - started, 1),
        )
        rows.append(row)
        print(f"[{index}/{len(claims)}] {item['id']} {'PASS' if row['passed'] else 'FAIL'} got {result.assessment}, wanted {item['expect']}", flush=True)
    wrongly_decisive = [r for r in rows if r["expect"] == "insufficient_evidence" and r.get("assessment") in ("supported", "contradicted")]
    summary = {
        "claims": len(rows),
        "not_yet_run": len(claims) - len(rows),
        "llm_errors": sum(1 for r in rows if "error" in r),
        "correct_assessment_pct": percent(sum(r["passed"] for r in rows), len(rows)),
        "unverifiable_claims_given_a_verdict": len(wrongly_decisive),
        "responses_with_accusatory_language": sum(bool(r.get("accusatory_language")) for r in rows),
    }
    print(json.dumps(summary, indent=1))
    save("claims", {"summary": summary, "claims": rows})


def run_multilingual(limit: int | None) -> None:
    """Automated checks only. Meaning must be judged by a fluent human, using the exported sheet."""
    require_llm()
    rows = []
    items = DATASET["multilingual"][:limit]
    language_module.generate_json = _generate_json_for_translation
    finished = load_finished("multilingual")
    for index, item in enumerate(items, 1):
        if item["id"] in finished:
            rows.append(finished[item["id"]])
            continue
        time.sleep(PAUSE_SECONDS)
        started = time.perf_counter()
        row = {"id": item["id"], "language": item["language"], "question": item["question"], "english_reference": item["english_reference"]}
        try:
            response = answer_question(item["question"], item["language"], None, allow_passages_fallback=False)
        except (LLMError, TranslationUnavailable) as error:
            if quota_used_up(error):
                break
            row.update(error=str(error), passed=False)
            rows.append(row)
            print(f"[{index}/{len(items)}] {item['id']} LLM ERROR", flush=True)
            continue
        cited = {c.document_id for c in response.citations}
        row.update(
            status=response.evidence_status, answered_in=response.answered_in, answer=response.answer,
            english_answer=response.english_answer or (response.answer if response.answered_in == "en" else None),
            cited_documents=sorted(cited), latency_s=round(time.perf_counter() - started, 1),
            cited_expected_document=bool(cited & set(item["expected_documents"])),
            translation_delivered=response.answered_in == item["language"] and response.evidence_status in ("supported", "outdated_only"),
        )
        row["passed"] = row["cited_expected_document"] and row["translation_delivered"]
        rows.append(row)
        print(f"[{index}/{len(items)}] {item['id']} status={response.evidence_status} answered_in={response.answered_in} {row['latency_s']}s", flush=True)

    by_language = {}
    for code in ("ha", "yo", "ig"):
        subset = [r for r in rows if r["language"] == code]
        if subset:
            by_language[code] = {
                "questions": len(subset),
                "found_expected_source_pct": percent(sum(bool(r.get("cited_expected_document")) for r in subset), len(subset)),
                "translation_passed_automatic_checks_pct": percent(sum(bool(r.get("translation_delivered")) for r in subset), len(subset)),
                "honest_fallback_or_abstain_pct": percent(sum(not r.get("translation_delivered") and not r.get("error") for r in subset), len(subset)),
                "llm_errors": sum(bool(r.get("error")) for r in subset),
            }
    summary = {
        "not_yet_run": len(items) - len(rows),
        "by_language": by_language,
        "human_meaning_review": "NOT DONE. Send evaluation/results/multilingual_review.csv to fluent reviewers.",
    }
    print(json.dumps(summary, indent=1, ensure_ascii=False))
    save("multilingual", {"summary": summary, "questions": rows})
    with (RESULTS_DIR / f"multilingual_review{'-' + LABEL if LABEL else ''}.csv").open("w", newline="", encoding="utf-8-sig") as sheet:
        writer = csv.writer(sheet)
        writer.writerow(["id", "language", "question", "english_answer", "translated_answer", "reviewer_meaning_score_1_to_5", "reviewer_notes"])
        for r in rows:
            writer.writerow([r["id"], r["language"], r["question"], r.get("english_answer", ""), r.get("answer", ""), "", ""])


def require_llm() -> None:
    require_index()
    if not is_llm_configured():
        sys.exit("No LLM configured. Set LLM_PROVIDER and its key in backend/.env. No results were written.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("suite", choices=["retrieval", "answers", "claims", "multilingual"])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--label", default="", help="Suffix for result files, e.g. the model used")
    parser.add_argument("--ids", help="Comma-separated question ids")
    parser.add_argument("--resume", action="store_true", help="Keep finished rows from the saved file and run the rest")
    parser.add_argument("--pause", type=float, default=0.0, help="Seconds to wait before each question")
    args = parser.parse_args()
    LABEL = args.label
    RESUME = args.resume
    PAUSE_SECONDS = args.pause
    if args.suite == "retrieval":
        run_retrieval()
    elif args.suite == "answers":
        run_answers(args.limit, set(args.ids.split(",")) if args.ids else None)
    elif args.suite == "claims":
        run_claims(args.limit)
    else:
        run_multilingual(args.limit)

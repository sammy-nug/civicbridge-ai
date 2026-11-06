"""Retrieval quality gates against the real index. These need no LLM.

Run: cd backend && .venv/bin/python -m pytest ../evaluation/test_rag.py -v
Full measured runs, including LLM-based ones, use evaluation/run_evaluation.py.
"""
import json
from pathlib import Path

import pytest

from app.services.retrieval import expand_query, get_store, retrieve

DATASET = json.loads((Path(__file__).parent / "test_questions.json").read_text(encoding="utf-8"))
ANSWERABLE = [q for q in DATASET["questions"] if q["expect"] == "answer"]

pytestmark = pytest.mark.skipif(get_store().count() == 0, reason="Run ingestion first")


def test_dataset_is_large_enough():
    assert len(DATASET["questions"]) >= 30


@pytest.mark.parametrize("question", ANSWERABLE, ids=lambda q: q["id"])
def test_expected_source_is_retrieved(question):
    documents = {item.document_id for item in retrieve(question["question"])}
    assert documents & set(question["expected_documents"])


def test_lost_pvc_finds_the_law_even_though_it_says_voters_card():
    assert "electoral-act-2026" in {item.document_id for item in retrieve("How can I replace a lost PVC?")}


def test_registration_question_always_sees_the_portal_notice():
    assert "cvr-portal-notice" in {item.document_id for item in retrieve("How do I register to vote?")}


def test_current_law_outranks_stale_penalty_pages():
    evidence = retrieve("What is the penalty for buying votes?")
    assert evidence[0].document_id == "electoral-act-2026"


def test_unrelated_questions_retrieve_nothing():
    for question in ("What is the capital of France?", "What is the price of a bag of rice in Kano?"):
        assert retrieve(question) == []


def test_results_never_exceed_context_budget_before_notices():
    assert sum(len(item.text) for item in retrieve("How do I vote?")) <= 6000 + 2500


def test_every_chunk_keeps_its_source_metadata():
    for item in retrieve("voter registration"):
        assert item.url.startswith("https://") and item.retrieved_date and item.title and item.organisation


def test_query_expansion_is_for_search_only():
    assert "voter's card" in expand_query("Lost PVC")
    assert expand_query("How do I vote?") == "How do I vote?"


@pytest.mark.parametrize("question, notice", [
    ("How do I register to vote?", "cvr-portal-notice"),
    ("How can I replace a lost PVC?", "cvr-portal-notice"),
    ("My voter's card was stolen. What now?", "cvr-portal-notice"),
    ("How can I find out where to collect my PVC?", "cvr-portal-notice"),
    ("When is the 2027 presidential election?", "inec-election-calendar"),
    ("What time do polling units open and close on election day?", "inec-election-calendar"),
    ("When do polling units close?", "inec-election-calendar"),
    ("What is the deadline for applying to transfer my voter registration?", "inec-election-calendar"),
])
def test_relevant_notices_are_added(question, notice):
    assert notice in {item.document_id for item in retrieve(question)}


@pytest.mark.parametrize("question, notice", [
    ("What is the date of birth requirement for candidates?", "inec-election-calendar"),
    ("Is the ballot box open to inspection?", "inec-election-calendar"),
    ("How can I replace a lost PVC?", "inec-election-calendar"),
    ("What principles must election observers follow?", "cvr-portal-notice"),
    ("Can I vote with a temporary voter's card?", "cvr-portal-notice"),
    ("Who moved the observers' accreditation centre?", "cvr-portal-notice"),
])
def test_irrelevant_notices_are_not_added(question, notice):
    from app.services.retrieval import NOTICE_TRIGGERS
    assert not NOTICE_TRIGGERS[notice].search(question)

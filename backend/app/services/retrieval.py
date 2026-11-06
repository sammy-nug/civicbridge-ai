"""Vector store and evidence retrieval.

Retrieval does more than nearest-neighbour search: it drops weak matches, slightly prefers
current documents over old ones, limits repetition from one document, and caps context size.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from functools import lru_cache

import chromadb

from app.config import get_settings
from app.services.embeddings import get_embedder

# Telemetry is switched off below. This hides a harmless log error from Chroma's unused client.
logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.CRITICAL)

COLLECTION_NAME = "electoral_documents"

# Old rules should only surface when nothing current answers the question. Scores are
# multiplied by these factors for ranking; the threshold still applies to the raw score.
STATUS_RANK_WEIGHT = {"current": 1.0, "needs_verification": 0.93, "historical": 0.8, "superseded": 0.75}
MAX_CHUNKS_PER_DOCUMENT = 3
CANDIDATE_MULTIPLIER = 4
NEAR_DUPLICATE_OVERLAP = 0.8


# Whether an exercise is open or a date has passed decides whether older how-to steps still
# apply, yet such notices are short and rarely the top semantic match. For these topics the
# relevant notice is always added to the evidence, whatever its similarity score. Each notice
# has its own trigger, because an irrelevant one distracts the model and looks like a conflict.
NOTICE_TRIGGERS = {
    "cvr-portal-notice": re.compile(
        r"\b(?:regist\w*|enrol\w*|cvr|transfer\w*|relocat\w*|replac\w*|collect\w*|i(?: have|'ve)? moved|moving to)\b"
        r"|\b(?:lost|stolen|damaged|defaced|torn)\b.*\b(?:pvcs?|cards?)\b|\b(?:pvcs?|cards?)\b.*\b(?:lost|stolen|damaged|defaced|torn)\b",
        re.IGNORECASE,
    ),
    "inec-election-calendar": re.compile(
        r"\b(?:deadlines?|timetable|calendar|schedul\w*|what time|opening hours)\b"
        r"|\bpolling units?\s+(?:open|close)|\b(?:election|polling|voting)\s+(?:days?|dates?)\b"
        r"|\bdate\s+of\s+the\s+(?:election|poll|vote)|\bwhen\b.*\b(?:elections?|vot(?:e|es|ing)|polls?)\b"
        r"|\belections?\s+(?:will\s+)?(?:holds?|take\s+place)\b",
        re.IGNORECASE,
    ),
}
TIME_CRITICAL_DOCUMENTS = tuple(NOTICE_TRIGGERS)


# Citizens say "PVC"; the law says "voter's card". Embeddings alone miss this, so common
# terms are expanded with the wording the official documents use, for searching only.
QUERY_EXPANSIONS = [
    (re.compile(r"\bPVCs?\b", re.IGNORECASE), "permanent voter's card, voter's card"),
    (re.compile(r"\bCVR\b", re.IGNORECASE), "continuous voter registration"),
    (re.compile(r"\bBVAS\b", re.IGNORECASE), "Bimodal Voter Accreditation System"),
    (re.compile(r"\bIReV\b", re.IGNORECASE), "INEC Result Viewing portal"),
    (re.compile(r"\bIDPs?\b", re.IGNORECASE), "internally displaced persons"),
    (re.compile(r"\bvote[- ]buying|buying votes|sell(?:ing)? votes\b", re.IGNORECASE), "buys or offers to buy, sells or offers to sell votes"),
]


def expand_query(query: str) -> str:
    additions = [expansion for pattern, expansion in QUERY_EXPANSIONS if pattern.search(query)]
    return f"{query} ({'; '.join(additions)})" if additions else query


@dataclass
class Evidence:
    chunk_id: str
    text: str
    similarity: float
    rank_score: float
    document_id: str
    title: str
    organisation: str
    url: str
    status: str
    publication_date: str | None
    publication_date_basis: str
    retrieved_date: str
    page: int | None
    section: str
    extraction: str
    superseded_by: str | None

    @property
    def is_current(self) -> bool:
        return self.status == "current"


def _chroma_safe(value):
    """Chroma metadata cannot hold None, so absent values are stored as empty strings."""
    return "" if value is None else value


class VectorStore:
    def __init__(self, path: str) -> None:
        self._client = chromadb.PersistentClient(
            path=path, settings=chromadb.Settings(anonymized_telemetry=False)
        )
        self._collection = self._client.get_or_create_collection(
            COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
        )

    def reset(self) -> None:
        self._client.delete_collection(COLLECTION_NAME)
        self._collection = self._client.get_or_create_collection(
            COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
        )

    def count(self) -> int:
        return self._collection.count()

    def add_document(self, document: dict, chunks: list[dict], batch_size: int = 64) -> int:
        embedder = get_embedder()
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start:start + batch_size]
            self._collection.add(
                ids=[chunk["chunk_id"] for chunk in batch],
                documents=[chunk["text"] for chunk in batch],
                embeddings=embedder.embed([chunk["text"] for chunk in batch]),
                metadatas=[
                    {
                        "document_id": document["id"],
                        "title": document["title"],
                        "organisation": document["organisation"],
                        "url": document["url"],
                        "status": document["status"],
                        "publication_date": _chroma_safe(document.get("publication_date")),
                        "publication_date_basis": _chroma_safe(document.get("publication_date_basis")),
                        "retrieved_date": document["retrieved_date"],
                        "page": _chroma_safe(chunk.get("page")),
                        "section": _chroma_safe(chunk.get("section")),
                        "extraction": document["extraction"],
                        "superseded_by": _chroma_safe(document.get("superseded_by")),
                    }
                    for chunk in batch
                ],
            )
        return len(chunks)

    def query(self, text: str, limit: int, document_id: str | None = None) -> list[Evidence]:
        if self.count() == 0:
            return []
        result = self._collection.query(
            query_embeddings=get_embedder().embed([text]),
            n_results=min(limit, self.count()),
            include=["documents", "metadatas", "distances"],
            where={"document_id": document_id} if document_id else None,
        )
        evidence = []
        for chunk_id, body, meta, distance in zip(
            result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0]
        ):
            similarity = 1.0 - distance  # Chroma returns cosine distance.
            evidence.append(
                Evidence(
                    chunk_id=chunk_id,
                    text=body,
                    similarity=similarity,
                    rank_score=similarity * STATUS_RANK_WEIGHT.get(meta["status"], 0.75),
                    document_id=meta["document_id"],
                    title=meta["title"],
                    organisation=meta["organisation"],
                    url=meta["url"],
                    status=meta["status"],
                    publication_date=meta["publication_date"] or None,
                    publication_date_basis=meta["publication_date_basis"],
                    retrieved_date=meta["retrieved_date"],
                    page=meta["page"] if meta["page"] != "" else None,
                    section=meta["section"],
                    extraction=meta["extraction"],
                    superseded_by=meta["superseded_by"] or None,
                )
            )
        return evidence


@lru_cache
def get_store() -> VectorStore:
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return VectorStore(str(settings.data_dir / "chroma"))


def _word_overlap(first: str, second: str) -> float:
    a, b = set(first.lower().split()), set(second.lower().split())
    return len(a & b) / max(1, min(len(a), len(b)))


def retrieve(query: str, top_k: int | None = None, threshold: float | None = None) -> list[Evidence]:
    """Return the best evidence for a query, or an empty list if nothing is relevant enough."""
    settings = get_settings()
    top_k = top_k or settings.retrieval_top_k
    threshold = settings.similarity_threshold if threshold is None else threshold

    candidates = get_store().query(expand_query(query), top_k * CANDIDATE_MULTIPLIER)
    relevant = [item for item in candidates if item.similarity >= threshold]
    relevant.sort(key=lambda item: item.rank_score, reverse=True)

    selected: list[Evidence] = []
    per_document: dict[str, int] = {}
    context_chars = 0
    for item in relevant:
        if per_document.get(item.document_id, 0) >= MAX_CHUNKS_PER_DOCUMENT:
            continue
        if any(_word_overlap(item.text, kept.text) > NEAR_DUPLICATE_OVERLAP for kept in selected):
            continue
        if context_chars + len(item.text) > settings.max_context_chars:
            break
        selected.append(item)
        per_document[item.document_id] = per_document.get(item.document_id, 0) + 1
        context_chars += len(item.text)
        if len(selected) == top_k:
            break

    # Only add notices when the question found real evidence. Otherwise an unrelated question
    # that happens to say "when" would never abstain.
    if selected:
        chosen_ids = {item.chunk_id for item in selected}
        for document_id, trigger in NOTICE_TRIGGERS.items():
            if trigger.search(query):
                for item in get_store().query(query, 1, document_id=document_id):
                    if item.chunk_id not in chosen_ids:
                        selected.append(item)
    return selected

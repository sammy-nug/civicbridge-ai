"""Request and response models. Length limits and enums here are the first input validation."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

LanguageCode = Literal["en", "ha", "yo", "ig"]
EvidenceStatus = Literal[
    "supported",        # Answer cites at least one current source.
    "outdated_only",    # Answer rests only on older sources; shown with a warning.
    "insufficient",     # The system abstained.
    "declined",         # Neutrality rules or topic limits.
    "passages_only",    # The AI was unavailable, so official passages are shown with no written answer.
]
Assessment = Literal["supported", "contradicted", "insufficient_evidence"]


def _not_blank(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("must not be blank")
    return value


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    language: LanguageCode = "en"
    session_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9-]{8,64}$")
    _strip = field_validator("message")(_not_blank)


class VerifyRequest(BaseModel):
    claim: str = Field(min_length=5, max_length=1000)
    language: LanguageCode = "en"
    _strip = field_validator("claim")(_not_blank)


class FeedbackRequest(BaseModel):
    response_id: str = Field(pattern=r"^[A-Za-z0-9-]{8,64}$")
    rating: Literal["helpful", "not_helpful"]
    feedback: str | None = Field(default=None, max_length=1000)


class Citation(BaseModel):
    """Every field comes from stored document metadata, never from model output."""
    number: int
    document_id: str
    title: str
    organisation: str
    url: str
    page: int | None = None
    section: str | None = None
    publication_date: str | None = None
    publication_date_basis: str | None = None
    retrieved_date: str
    status: str
    notes: list[str] = []
    excerpt: str
    similarity: float


class ChatResponse(BaseModel):
    response_id: str
    answer: str
    language: LanguageCode
    answered_in: LanguageCode
    english_answer: str | None = None
    citations: list[Citation]
    evidence_status: EvidenceStatus
    notices: list[str] = []
    translation_reviewed: bool
    session_id: str


class VerifyResponse(BaseModel):
    response_id: str
    assessment: Assessment
    explanation: str
    supports: list[str] = []
    contradicts: list[str] = []
    cannot_establish: list[str] = []
    supporting_sources: list[Citation]
    limitations: list[str]
    language: LanguageCode
    answered_in: LanguageCode
    translation_reviewed: bool


class FeedbackResponse(BaseModel):
    status: Literal["recorded"]


class ResourceDocument(BaseModel):
    id: str
    title: str
    organisation: str
    url: str
    category: str | None = None
    description: str | None = None
    publication_date: str | None = None
    publication_date_basis: str | None = None
    retrieved_date: str
    status: str
    extraction: str
    superseded_by: str | None = None
    chunks: int


class ResourcesResponse(BaseModel):
    documents: list[ResourceDocument]
    total: int


class LanguageInfo(BaseModel):
    code: LanguageCode
    english_name: str
    native_name: str
    human_reviewed: bool


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    llm_configured: bool
    llm_provider: str
    embedding_backend: str
    indexed_chunks: int
    languages: list[LanguageInfo]
    problems: list[str] = []

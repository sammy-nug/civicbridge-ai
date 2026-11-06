# API

Interactive docs are at `/docs` when the backend runs. All errors have the form:

```json
{"error": {"code": "invalid_request", "message": "Readable explanation"}}
```

| Status | Code | Meaning |
|---|---|---|
| 404 | `not_found` | Unknown response id |
| 422 | `invalid_request` | Validation failed. The input is not echoed back |
| 429 | `rate_limited` | Too many requests. See the `Retry-After` header, which is absent when the daily limit is reached |
| 502 | `llm_unavailable` | The AI provider failed |
| 503 | `llm_not_configured` | No provider or key is set up on the server |
| 503 | `at_capacity` | The AI quota or the daily request cap is used up |

## POST /api/chat

Request: `message` (1 to 1000 characters), `language` (`en`, `ha`, `yo`, `ig`; default `en`), `session_id` (optional).

```json
{
  "response_id": "uuid",
  "answer": "Text with citation markers [1].",
  "language": "ha",
  "answered_in": "ha",
  "english_answer": "The checked English text, when translated [1].",
  "citations": [{
    "number": 1, "document_id": "electoral-act-2026", "title": "Electoral Act, 2026",
    "organisation": "...", "url": "https://...", "page": 15, "section": "Section/clause 18",
    "publication_date": "2026", "publication_date_basis": "Year in document title",
    "retrieved_date": "2026-11-05", "status": "current", "notes": [], "excerpt": "...", "similarity": 0.58
  }],
  "evidence_status": "supported",
  "notices": [],
  "translation_reviewed": false,
  "session_id": "uuid"
}
```

`evidence_status`: `supported` (cites at least one current source), `outdated_only` (only older sources, with a warning), `insufficient` (abstained), `declined` (neutrality or topic limits), `passages_only` (the AI was unavailable, so `answer` is a fixed explanation in English and `citations` holds official passages).

`answered_in` differs from `language` when a translation failed its checks and the answer is in English.

## POST /api/verify

Request: `claim` (5 to 1000 characters), `language`.

Response: `response_id`, `assessment` (`supported`, `contradicted`, `insufficient_evidence`), `explanation`, `supports`, `contradicts`, `cannot_establish`, `supporting_sources` (citations), `limitations`, `language`, `answered_in`, `translation_reviewed`. A partisan, forecasting or unrelated claim gets `insufficient_evidence` with a fixed explanation and no sources.

## GET /api/resources

Optional `q` filters by title, organisation, description and category. Returns `documents` and `total`.

## POST /api/feedback

Request: `response_id`, `rating` (`helpful`, `not_helpful`), `feedback` (optional, up to 1000 characters; identity details are removed before storage). Returns 201 and `{"status": "recorded"}`.

## GET /api/health

Returns `status` (`ok`, `degraded`), `llm_configured`, `llm_provider`, `embedding_backend`, `indexed_chunks`, `languages` (each with `human_reviewed`) and `problems`.

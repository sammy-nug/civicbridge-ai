import json
from functools import lru_cache

from fastapi import APIRouter, Query

from app.config import get_settings
from app.schemas.api import ResourceDocument, ResourcesResponse

router = APIRouter(prefix="/api", tags=["resources"])
STATUS_ORDER = {"current": 0, "needs_verification": 1, "historical": 2, "superseded": 3}


@lru_cache
def _load_documents() -> tuple[ResourceDocument, ...]:
    documents = []
    for path in sorted(get_settings().processed_dir.glob("*.json")):
        if path.name == "fetch_log.json":
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        documents.append(ResourceDocument(**data["document"], chunks=len(data["chunks"])))
    documents.sort(key=lambda d: (STATUS_ORDER.get(d.status, 9), d.title))
    return tuple(documents)


@router.get("/resources", response_model=ResourcesResponse)
def resources(q: str | None = Query(default=None, max_length=100)) -> ResourcesResponse:
    documents = list(_load_documents())
    if q and q.strip():
        needle = q.strip().lower()
        documents = [
            d for d in documents
            if needle in f"{d.title} {d.organisation} {d.description or ''} {d.category or ''}".lower()
        ]
    return ResourcesResponse(documents=documents, total=len(documents))

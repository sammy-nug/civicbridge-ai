"""CivicBridge AI API entry point."""
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routes import chat, feedback, resources, verify
from app.schemas.api import HealthResponse, LanguageInfo
from app.services.language import LANGUAGES
from app.services.llm import LLMCapacityError, LLMError, LLMNotConfiguredError, is_llm_configured
from app.services.retrieval import get_store

logger = logging.getLogger("civicbridge")
settings = get_settings()

app = FastAPI(
    title="CivicBridge AI API",
    description="Evidence-grounded, nonpartisan electoral information for Nigerians. Not affiliated with INEC.",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
for module in (chat, verify, resources, feedback):
    app.include_router(module.router)


def _error(status: int, code: str, message: str, headers: dict | None = None) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}}, headers=headers)


@app.exception_handler(RequestValidationError)
async def handle_validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
    # Only field names and reasons are returned. FastAPI's default echoes the input back,
    # which we avoid because it may contain personal details.
    problems = [f"{'.'.join(str(p) for p in item['loc'] if p != 'body')}: {item['msg']}" for item in error.errors()]
    return _error(422, "invalid_request", "; ".join(problems))


@app.exception_handler(HTTPException)
async def handle_http_error(_: Request, error: HTTPException) -> JSONResponse:
    codes = {404: "not_found", 429: "rate_limited"}
    return _error(error.status_code, codes.get(error.status_code, "error"), str(error.detail), error.headers)


@app.exception_handler(LLMNotConfiguredError)
async def handle_not_configured(_: Request, error: LLMNotConfiguredError) -> JSONResponse:
    logger.error("LLM not configured: %s", error)
    return _error(503, "llm_not_configured", "The AI service has not been set up on this server, so we can't answer questions yet.")


@app.exception_handler(LLMCapacityError)
async def handle_capacity(_: Request, error: LLMCapacityError) -> JSONResponse:
    logger.error("LLM capacity reached: %s", error)
    return _error(503, "at_capacity", "CivicBridge AI has reached its limit of AI requests for now. Please try again later.")


@app.exception_handler(LLMError)
async def handle_llm_error(_: Request, error: LLMError) -> JSONResponse:
    logger.error("LLM failure: %s", error)
    return _error(502, "llm_unavailable", "The AI service is not responding right now. Please try again in a moment.")


@app.get("/api/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    problems = []
    llm_configured = is_llm_configured()
    if not llm_configured:
        problems.append("LLM is not configured")
    chunks = get_store().count()
    if chunks == 0:
        problems.append("Knowledge base is empty; run ingestion")
    return HealthResponse(
        status="degraded" if problems else "ok",
        llm_configured=llm_configured,
        llm_provider=settings.llm_provider,
        embedding_backend=settings.embedding_backend,
        indexed_chunks=chunks,
        languages=[
            LanguageInfo(code=l.code, english_name=l.english_name, native_name=l.native_name, human_reviewed=l.human_reviewed)
            for l in LANGUAGES.values()
        ],
        problems=problems,
    )

"""LLM providers behind one small interface, so switching models needs no code changes."""
from __future__ import annotations

import json
import re
import time
from contextvars import ContextVar
from datetime import date
from functools import lru_cache
from threading import BoundedSemaphore, Lock
from typing import Protocol

import httpx

from app.config import get_settings

# 429 is left out: a used-up quota will not recover within these short retries.
RETRYABLE_STATUS = {500, 502, 503, 504}
MAX_ATTEMPTS = 3
SLOT_WAIT_SECONDS = 10.0  # When this many calls are busy, answer quickly instead of queueing.


class LLMNotConfiguredError(RuntimeError):
    """A required setting (usually the API key) is missing."""


class LLMError(RuntimeError):
    """The provider failed or returned something unusable. Messages never include secrets."""


class LLMUnavailableError(LLMError):
    """The provider could not be reached or refused the request (outage, overload, used-up quota)."""


class LLMCapacityError(LLMUnavailableError):
    """The AI quota or our own daily cap is used up, so retrying soon will not help."""


class LLMProvider(Protocol):
    name: str

    def generate(self, system: str, prompt: str, temperature: float = 0.1) -> str: ...


_deadline: ContextVar[float | None] = ContextVar("llm_deadline", default=None)
_daily_calls = {"date": None, "count": 0}
_daily_lock = Lock()


def start_request_deadline() -> None:
    """Limit the total AI time for this request, across every step and retry."""
    _deadline.set(time.monotonic() + get_settings().request_deadline_seconds)


def _seconds_left() -> float:
    deadline = _deadline.get()
    return float("inf") if deadline is None else deadline - time.monotonic()


@lru_cache
def _call_slots() -> BoundedSemaphore:
    return BoundedSemaphore(get_settings().max_concurrent_llm_calls)


def _count_daily_call(provider: str) -> None:
    limit = get_settings().llm_daily_request_limit
    if limit <= 0:
        return
    with _daily_lock:
        today = date.today()
        if _daily_calls["date"] != today:
            _daily_calls.update(date=today, count=0)
        if _daily_calls["count"] >= limit:
            raise LLMCapacityError(f"{provider}: daily request cap of {limit} reached")
        _daily_calls["count"] += 1


def _post_with_retries(url: str, headers: dict, payload: dict, provider: str) -> dict:
    timeout = get_settings().llm_timeout_seconds
    last_problem = "unknown error"
    for attempt in range(MAX_ATTEMPTS):
        left = _seconds_left()
        if left <= 0:
            last_problem = "the request deadline passed"
            break
        if not _call_slots().acquire(timeout=min(SLOT_WAIT_SECONDS, left)):
            last_problem = "too many AI calls in progress"
            break
        try:
            _count_daily_call(provider)
            response = httpx.post(url, headers=headers, json=payload, timeout=min(timeout, left))
        except httpx.TimeoutException:
            last_problem = "the request timed out"
        except httpx.HTTPError as error:
            last_problem = f"connection failed ({type(error).__name__})"
        else:
            if response.status_code == 200:
                return response.json()
            if response.status_code == 429:
                raise LLMCapacityError(f"{provider}: HTTP 429")
            last_problem = f"HTTP {response.status_code}"
            if response.status_code not in RETRYABLE_STATUS:
                break
        finally:
            _call_slots().release()
        if attempt < MAX_ATTEMPTS - 1:
            time.sleep(1.5 * (attempt + 1))
    raise LLMUnavailableError(f"{provider}: {last_problem}")


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    def generate(self, system: str, prompt: str, temperature: float = 0.1) -> str:
        data = _post_with_retries(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self._model}:generateContent",
            headers={"x-goog-api-key": self._api_key, "Content-Type": "application/json"},
            payload={
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": temperature, "responseMimeType": "application/json"},
            },
            provider=self.name,
        )
        try:
            return "".join(part.get("text", "") for part in data["candidates"][0]["content"]["parts"])
        except (KeyError, IndexError) as error:
            raise LLMError("gemini: response had no text (possibly blocked)") from error


class OpenAICompatibleProvider:
    """Works with Ollama, Groq, OpenRouter, Together, OpenAI and similar services."""

    name = "openai_compatible"

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._api_key = api_key
        self._model = model

    def generate(self, system: str, prompt: str, temperature: float = 0.1) -> str:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        data = _post_with_retries(
            self._url,
            headers=headers,
            payload={
                "model": self._model,
                "temperature": temperature,
                "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            },
            provider=self.name,
        )
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise LLMError("openai_compatible: response had no text") from error


def _build_provider() -> LLMProvider:
    settings = get_settings()
    provider = settings.llm_provider
    if provider == "gemini":
        if not settings.gemini_api_key:
            raise LLMNotConfiguredError("GEMINI_API_KEY is not set. See backend/.env.example.")
        return GeminiProvider(settings.gemini_api_key, settings.llm_model or "gemini-3.6-flash")
    if provider == "openai_compatible":
        if not settings.openai_compatible_base_url or not settings.llm_model:
            raise LLMNotConfiguredError("Set OPENAI_COMPATIBLE_BASE_URL and LLM_MODEL. See backend/.env.example.")
        return OpenAICompatibleProvider(
            settings.openai_compatible_base_url, settings.openai_compatible_api_key, settings.llm_model
        )
    raise LLMNotConfiguredError("No LLM provider is configured. Set LLM_PROVIDER in backend/.env.")


@lru_cache
def get_llm() -> LLMProvider:
    return _build_provider()


def is_llm_configured() -> bool:
    try:
        get_llm()
    except LLMNotConfiguredError:
        get_llm.cache_clear()
        return False
    return True


def generate_json(system: str, prompt: str) -> dict:
    """Generate and parse a JSON object, retrying once if the model returns invalid JSON."""
    llm = get_llm()
    for attempt in range(2):
        raw = llm.generate(system, prompt, temperature=0.1 if attempt == 0 else 0.0)
        cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip()).strip()
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise LLMError("The model did not return valid JSON.")

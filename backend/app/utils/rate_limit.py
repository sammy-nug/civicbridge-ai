"""A small per-client sliding-window rate limiter, held in memory (single-process deployments)."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from datetime import date
from threading import Lock

from fastapi import HTTPException, Request

from app.config import get_settings

WINDOW_SECONDS = 60.0
MAX_TRACKED_CLIENTS = 10_000
_requests: dict[str, deque[float]] = defaultdict(deque)
_daily_counts: dict[str, tuple[date, int]] = {}
_lock = Lock()


def _client_key(request: Request) -> str:
    if get_settings().trust_proxy_headers:
        # Clients can send any X-Forwarded-For they like, and proxies add to the end of it.
        # So only the entries our own proxies added can be trusted, counting from the right.
        entries = [entry.strip() for entry in request.headers.get("x-forwarded-for", "").split(",") if entry.strip()]
        if entries:
            return entries[-min(max(get_settings().trusted_proxy_hops, 1), len(entries))]
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(request: Request) -> None:
    limit = get_settings().rate_limit_per_minute
    key = _client_key(request)
    now = time.monotonic()
    with _lock:
        window = _requests[key]
        while window and now - window[0] > WINDOW_SECONDS:
            window.popleft()
        if len(window) >= limit:
            retry_after = int(WINDOW_SECONDS - (now - window[0])) + 1
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please wait a moment and try again.",
                headers={"Retry-After": str(retry_after)},
            )
        window.append(now)
        if len(_requests) > MAX_TRACKED_CLIENTS:
            # Forget clients with no recent requests so this table cannot grow without limit.
            for stale in [k for k, w in _requests.items() if not w or now - w[-1] > WINDOW_SECONDS]:
                del _requests[stale]


def enforce_daily_limit(request: Request) -> None:
    """Stops one client from using most of the shared AI quota. Applied to chat and verify only."""
    limit = get_settings().rate_limit_per_day
    if limit <= 0:
        return
    key = _client_key(request)
    today = date.today()
    with _lock:
        day, count = _daily_counts.get(key, (today, 0))
        count = count if day == today else 0
        if count >= limit:
            raise HTTPException(status_code=429, detail="You have reached today's limit for questions. Please try again tomorrow.")
        _daily_counts[key] = (today, count + 1)
        if len(_daily_counts) > MAX_TRACKED_CLIENTS:
            for stale in [k for k, (d, _) in _daily_counts.items() if d != today]:
                del _daily_counts[stale]

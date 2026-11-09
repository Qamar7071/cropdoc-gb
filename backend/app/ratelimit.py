"""Tiny in-memory rate limiter (token bucket per client IP), no extra dependency.

Intuition: each IP gets a bucket of N tokens that refills continuously over one minute. Every
request to a protected path takes a token; an empty bucket means HTTP 429. This stops a buggy
script from flooding the model, which is all a local app needs.
"""

from __future__ import annotations

import threading
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class TokenBucket:
    """Thread-safe token buckets keyed by client id."""

    def __init__(self, capacity: int, refill_per_second: float):
        self.capacity = capacity
        self.refill_per_second = refill_per_second
        self._buckets: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        """Take one token for ``key``; return False if none are left."""
        now = time.monotonic() if now is None else now
        with self._lock:
            tokens, last = self._buckets.get(key, (float(self.capacity), now))
            tokens = min(self.capacity, tokens + (now - last) * self.refill_per_second)
            if tokens < 1:
                self._buckets[key] = (tokens, now)
                return False
            self._buckets[key] = (tokens - 1, now)
            return True


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Apply a per-IP token bucket to POST requests on the given path prefixes."""

    def __init__(self, app, per_minute: int = 30, paths: tuple[str, ...] = ("/api/predict",)):
        super().__init__(app)
        self.paths = paths
        self.enabled = per_minute > 0
        self.bucket = TokenBucket(capacity=max(per_minute, 1), refill_per_second=max(per_minute, 1) / 60.0)

    async def dispatch(self, request: Request, call_next) -> Response:
        if self.enabled and request.method == "POST" and request.url.path.startswith(self.paths):
            client = request.client.host if request.client else "unknown"
            if not self.bucket.allow(client):
                return JSONResponse(
                    {"detail": "Too many requests. Please wait a minute and try again."}, status_code=429
                )
        return await call_next(request)

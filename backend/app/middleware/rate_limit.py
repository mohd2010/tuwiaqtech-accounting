"""Reusable in-memory rate limiter.

Extracted from ``api/v1/endpoints/auth.py`` so other endpoints can
reuse the same logic. For multi-replica deployments, swap to Redis.
"""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import HTTPException, status


class InMemoryRateLimiter:
    """Sliding-window in-memory rate limiter keyed by an arbitrary string."""

    def __init__(self, window_seconds: int = 60, max_attempts: int = 5) -> None:
        self._window = window_seconds
        self._max = max_attempts
        self._attempts: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str) -> None:
        """Raise HTTP 429 if *key* has exceeded *max_attempts* in the window."""
        now = time.time()
        attempts = self._attempts[key]
        self._attempts[key] = [t for t in attempts if now - t < self._window]
        if len(self._attempts[key]) >= self._max:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many attempts. Try again in {self._window} seconds.",
            )
        self._attempts[key].append(now)

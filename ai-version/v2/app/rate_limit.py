"""In-memory limiter for failed logins, keyed by (email, client IP).

After `max_failures` failed attempts inside `window_seconds`, further attempts
are refused until the oldest of those failures falls out of the window.
State lives in this process only: restart = reset, and several workers each
keep their own counts (use Redis or similar if you run more than one).
"""

import math
import threading
import time
from collections import deque


class LoginRateLimiter:
    def __init__(self, max_failures: int, window_seconds: int, clock=time.monotonic) -> None:
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self._clock = clock
        self._failures: dict[tuple[str, str], deque[float]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def key(email: str, ip: str) -> tuple[str, str]:
        return (email.strip().lower(), ip)

    def _prune(self, key: tuple[str, str], now: float) -> deque[float] | None:
        attempts = self._failures.get(key)
        if attempts is None:
            return None
        while attempts and attempts[0] <= now - self.window_seconds:
            attempts.popleft()
        if not attempts:
            del self._failures[key]
            return None
        return attempts

    def retry_after(self, key: tuple[str, str]) -> int | None:
        """Seconds until another attempt is allowed, or None if allowed now."""
        with self._lock:
            now = self._clock()
            attempts = self._prune(key, now)
            if attempts is None or len(attempts) < self.max_failures:
                return None
            # The attempt that must expire before we drop below the limit.
            blocking = attempts[len(attempts) - self.max_failures]
            return max(1, math.ceil(blocking + self.window_seconds - now))

    def record_failure(self, key: tuple[str, str]) -> None:
        with self._lock:
            now = self._clock()
            self._prune(key, now)
            self._failures.setdefault(key, deque()).append(now)

    def reset(self, key: tuple[str, str]) -> None:
        with self._lock:
            self._failures.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._failures.clear()

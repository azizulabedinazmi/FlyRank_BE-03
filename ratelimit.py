"""Stretch: brute-force protection for POST /auth/login.

After MAX_FAILURES wrong passwords for the same email from the same IP inside WINDOW seconds, further attempts get
429 until the window passes. A successful login clears the counter. In-memory, so it resets on restart and is per
process; a multi-server deployment would keep these counters in Redis instead.
"""
import os
import threading
import time
from collections import defaultdict, deque

MAX_FAILURES = int(os.environ.get("LOGIN_MAX_FAILURES", 5))
WINDOW = int(os.environ.get("LOGIN_WINDOW_SECONDS", 15 * 60))

_failures: dict[tuple[str, str], deque] = defaultdict(deque)
_lock = threading.Lock()


def _key(ip: str, email: str) -> tuple[str, str]:
    return ip, email.strip().lower()


def retry_after(ip: str, email: str) -> int:
    """Seconds until another attempt is allowed, or 0 if allowed now."""
    now = time.monotonic()
    with _lock:
        q = _failures[_key(ip, email)]
        while q and now - q[0] > WINDOW:
            q.popleft()
        if len(q) >= MAX_FAILURES:
            return int(WINDOW - (now - q[0])) + 1
    return 0


def record_failure(ip: str, email: str) -> None:
    with _lock:
        _failures[_key(ip, email)].append(time.monotonic())


def reset(ip: str, email: str) -> None:
    with _lock:
        _failures.pop(_key(ip, email), None)

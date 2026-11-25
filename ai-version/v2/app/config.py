"""Settings loaded from the environment (and a local .env file)."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _parse_admin_emails(raw: str) -> frozenset[str]:
    return frozenset(e.strip().lower() for e in raw.split(",") if e.strip())


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_key: str
    admin_emails: frozenset[str]
    host: str
    port: int
    # Seconds to wait for Supabase before answering 503.
    supabase_timeout: float
    # Login rate limiting.
    login_max_failures: int
    login_window_seconds: int

    def missing(self) -> list[str]:
        return [
            name
            for name, value in (
                ("SUPABASE_URL", self.supabase_url),
                ("SUPABASE_KEY", self.supabase_key),
            )
            if not value
        ]


def load_settings() -> Settings:
    return Settings(
        supabase_url=os.getenv("SUPABASE_URL", "").strip(),
        supabase_key=os.getenv("SUPABASE_KEY", "").strip(),
        admin_emails=_parse_admin_emails(os.getenv("ADMIN_EMAILS", "")),
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        supabase_timeout=float(os.getenv("SUPABASE_TIMEOUT", "10")),
        login_max_failures=5,
        login_window_seconds=15 * 60,
    )


settings = load_settings()

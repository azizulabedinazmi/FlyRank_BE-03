"""Everything that knows how to reach Supabase lives here."""
import os

import httpx
from dotenv import load_dotenv
from supabase import Client, ClientOptions, create_client

load_dotenv()  # real environment variables win over .env

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set. Copy .env.example to .env and fill them in.")


def new_client() -> Client:
    """A fresh client for every request.

    A Supabase client remembers the last session it signed in. On a server shared by many users, one shared
    client would mix their sessions up (and get_user("") would fall back to whoever logged in last). So each
    request gets its own client, and it never stores or refreshes a session in the background.
    """
    return create_client(
        SUPABASE_URL,
        SUPABASE_KEY,
        options=ClientOptions(persist_session=False, auto_refresh_token=False),
    )


def check_connection() -> None:
    """Fail fast at startup if the URL is wrong or the key is rejected."""
    r = httpx.get(f"{SUPABASE_URL}/auth/v1/settings", headers={"apikey": SUPABASE_KEY}, timeout=10)
    if r.status_code != 200:
        raise RuntimeError(f"Supabase rejected the connection ({r.status_code}): check SUPABASE_URL and SUPABASE_KEY")

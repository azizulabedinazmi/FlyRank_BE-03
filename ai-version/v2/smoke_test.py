"""Live end-to-end check against a running server and your real Supabase project.

    python main.py                 # terminal 1
    python smoke_test.py           # terminal 2

Uses SMOKE_EMAIL / SMOKE_PASSWORD if set (an existing, confirmed user);
otherwise signs up a fresh random user, which only works if "Confirm email"
is turned off in Supabase (Authentication > Providers > Email).
Set BASE_URL if the server is not on http://localhost:8000.
"""

import os
import sys
import uuid

import httpx

BASE = os.getenv("BASE_URL", f"http://localhost:{os.getenv('PORT', '8000')}")
failures = 0


def check(label, cond, detail=""):
    global failures
    print(("PASS " if cond else "FAIL ") + label + ("" if cond else f"  -> {detail}"))
    if not cond:
        failures += 1


def main() -> int:
    c = httpx.Client(base_url=BASE, timeout=20)
    email = os.getenv("SMOKE_EMAIL") or f"smoke-{uuid.uuid4().hex[:10]}@example.com"
    password = os.getenv("SMOKE_PASSWORD") or f"Pw-{uuid.uuid4().hex}"

    r = c.get("/public/info")
    check("public info 200", r.status_code == 200, r.text)

    if not os.getenv("SMOKE_EMAIL"):
        r = c.post("/auth/signup", json={"email": email, "password": password})
        check("signup 201 with exactly id/email/created_at",
              r.status_code == 201 and set(r.json()) == {"id", "email", "created_at"}, r.text)
        r = c.post("/auth/signup", json={"email": email, "password": password})
        check("duplicate signup 409", r.status_code == 409, r.text)

    r = c.post("/auth/signup", json={"email": email})
    check("signup missing password 400", r.status_code == 400, r.text)

    r = c.post("/auth/login", json={"email": email, "password": password})
    check("login 200", r.status_code == 200, r.text)
    if r.status_code != 200:
        print("Cannot continue without a session (is email confirmation on?).")
        return 1
    tokens = r.json()
    auth = {"Authorization": f"Bearer {tokens['access_token']}"}

    r = c.get("/protected/profile", headers=auth)
    check("profile 200", r.status_code == 200 and r.json().get("email") == email, r.text)
    r = c.get("/protected/profile")
    check("no token 401 + WWW-Authenticate",
          r.status_code == 401 and r.headers.get("www-authenticate") == "Bearer", r.text)
    r = c.get("/protected/admin", headers=auth)
    check("admin route 200 or 403", r.status_code in (200, 403), r.text)

    r = c.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    check("refresh 200", r.status_code == 200, r.text)
    if r.status_code == 200:
        tokens = r.json()
        auth = {"Authorization": f"Bearer {tokens['access_token']}"}

    r = c.post("/auth/logout", headers=auth)
    check("logout 204", r.status_code == 204, r.text)
    r = c.get("/protected/profile", headers=auth)
    check("same token rejected after logout", r.status_code == 401, r.text)

    # Also verify Supabase itself revoked it (not just this server's local list):
    # ask Supabase directly with the logged-out token.
    try:
        from dotenv import load_dotenv
        load_dotenv()
        url, key = os.environ["SUPABASE_URL"].rstrip("/"), os.environ["SUPABASE_KEY"]
        r = httpx.get(f"{url}/auth/v1/user", headers={"apikey": key, **auth}, timeout=20)
        check("Supabase itself rejects the logged-out token", r.status_code in (401, 403), r.text)
    except KeyError:
        print("SKIP direct Supabase check (SUPABASE_URL/SUPABASE_KEY not set)")

    bad_email = f"ratelimit-{uuid.uuid4().hex[:8]}@example.com"
    codes = [c.post("/auth/login", json={"email": bad_email, "password": "wrong"}).status_code
             for _ in range(5)]
    check("5 bad logins -> 401", codes == [401] * 5, codes)
    r = c.post("/auth/login", json={"email": bad_email, "password": "wrong"})
    check("6th bad login -> 429 with Retry-After",
          r.status_code == 429 and r.headers.get("retry-after", "").isdigit(), r.text)

    print(f"\n{failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

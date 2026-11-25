# Auth API (FastAPI + Supabase Auth)

A small auth API: signup, login, refresh, logout, and protected routes, backed by Supabase Auth.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env          # macOS/Linux: cp .env.example .env
# edit .env: SUPABASE_URL, SUPABASE_KEY (anon key), ADMIN_EMAILS
python main.py
```

The server listens on `PORT` (default 8000). Swagger UI is at http://localhost:8000/docs. Click **Authorize** and paste an `access_token` from `/auth/login`.

## Routes

| Method | Path | Auth | Success | Errors |
|---|---|---|---|---|
| POST | `/auth/signup` `{email, password}` | - | 201 `{id, email, created_at}` | 400 missing field / Supabase validation (message passed through), 409 already registered |
| POST | `/auth/login` `{email, password}` | - | 200 `{access_token, refresh_token}` | 400, 401 `Invalid login credentials`, 429 + `Retry-After` |
| POST | `/auth/refresh` `{refresh_token}` | - | 200 `{access_token, refresh_token}` | 400, 401 |
| POST | `/auth/logout` | Bearer | 204 | 401 |
| GET | `/public/info` | - | 200 | - |
| GET | `/protected/profile` | Bearer | 200 `{id, email, created_at}` | 401 |
| GET | `/protected/dashboard` | Bearer | 200 | 401 |
| GET | `/protected/admin` | Bearer | 200 (email in `ADMIN_EMAILS`) | 401, 403 `Admins only` |

Any route that talks to Supabase returns **503** if Supabase can't be reached. Protected routes fail closed: if the token can't be verified, the request is refused.

All errors are JSON `{"error": "..."}`. The API never returns 422; malformed bodies get a 400. Every 401 carries `WWW-Authenticate: Bearer`. Token errors are `Access token required` (no or malformed header) and `Invalid or expired token`.

## How it works

- **Fresh client per request.** `app/supabase_client.py:get_supabase` is a FastAPI dependency. It builds a new Supabase client (`persist_session=False`, `auto_refresh_token=False`, its own `httpx.Client` with a timeout) for each request and closes it afterwards. No client is shared between requests.
- **One token check.** `app/auth.py:get_current_user` uses `HTTPBearer(auto_error=False)` and verifies the token with `supabase.auth.get_user(token)`. Every protected route depends on it.
- **Logout.** This calls Supabase's `/logout` for that token's session (`auth.admin.sign_out(token, "local")`), which revokes the session and its refresh token. Current Supabase Auth versions then reject the access token on `GET /user`. As a second safeguard, the API keeps a hash of the logged-out token in memory until the token's `exp`, so the token is rejected even if Supabase still accepted it.
- **Login rate limit.** After 5 failed attempts for the same email (case-insensitive) from the same IP within 15 minutes, `/auth/login` returns 429 with `Retry-After` (seconds) and does not call Supabase. A successful login clears the counter. Missing-field requests and Supabase outages don't count as failures.
- **Duplicate signup.** Supabase's `user_already_exists`/`email_exists` maps to 409. When "Confirm email" is on, Supabase doesn't raise an error for a duplicate. It returns a placeholder user with no identities instead, and the API detects that and also returns 409.

## Tests

Offline tests run the real app against an in-memory fake of Supabase Auth, so no network is needed:

```bash
python -m unittest discover -s tests -v
```

They cover every status code above, including "same token is rejected after logout" and "503 when Supabase is down".

Live check against your real project (start the server first):

```bash
python smoke_test.py
```

This signs up a random user, so turn off "Confirm email" in Supabase. Or set `SMOKE_EMAIL`/`SMOKE_PASSWORD` to an existing confirmed user. Besides the round trip, it asks Supabase directly whether the logged-out token is still accepted. That shows whether your Supabase instance revokes it, separately from the API's local safeguard.

## Limitations

- The rate-limit counters and the logged-out-token list are in process memory. They reset on restart and are not shared between multiple workers or instances. Use Redis or similar if you scale out.
- The rate limiter keys on the direct client IP. Behind a reverse proxy, run uvicorn with `--proxy-headers` and `--forwarded-allow-ips` so the real client IP is used.
- Access tokens from *other* sessions of the same user (other devices) stay valid after a `local` logout. That is expected.

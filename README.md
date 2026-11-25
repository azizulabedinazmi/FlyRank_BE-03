<a name="readme-top"></a>

[![LinkedIn](https://custom-icon-badges.demolab.com/badge/LinkedIn-0A66C2?logo=linkedin-white&logoColor=fff)](https://www.linkedin.com/in/azizulabedin/)
[![GitHub](https://img.shields.io/badge/GitHub-181717?logo=github&logoColor=white)](https://github.com/azizulabedinazmi)
[![Portfolio](https://img.shields.io/badge/Portfolio-00C7B7?logo=netlify&logoColor=white)](https://azizulabedinazmi.netlify.app/)
[![FlyRank verified](https://img.shields.io/badge/FlyRank_verified-FR--D1--A84A9--AB526-1A7A4A)](https://internship.flyrank.ai/verify?id=FR-D1-A84A9-AB526&first_name=Azizul)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Supabase](https://img.shields.io/badge/Supabase_Auth-3FCF8E?logo=supabase&logoColor=white)](https://supabase.com/docs/guides/auth)

<div align="center">
  <h3>Auth API: Login &amp; Protect</h3>
  <p>
    A FastAPI service that signs users up, logs them in and out with <b>Supabase Auth</b>, and guards private routes
    with a <b>JWT bearer token</b> checked by one reusable dependency. Documented in Swagger UI with a working Authorize padlock.
    <br /><br />
    FlyRank AI Internship · Backend AI Engineering · BE-03 / A4 (Auth: Login &amp; protect) · Python lane
  </p>
</div>

<details>
  <summary>Table of Contents</summary>
  <ol>
    <li><a href="#how-it-works">How It Works</a></li>
    <li><a href="#getting-started">Getting Started</a></li>
    <li><a href="#api-reference">API Reference</a></li>
    <li><a href="#swagger">Swagger UI</a></li>
    <li><a href="#curl">The Full Flow with curl -i</a></li>
    <li><a href="#guard">The Guard (reusable dependency)</a></li>
    <li><a href="#testing">Testing: 29 live checks</a></li>
    <li><a href="#extras">Extras: 403, refresh, rate limit, logout, JWT</a></li>
    <li><a href="#security">Security Decisions</a></li>
    <li><a href="#ai-vs-me">AI vs Me (Stage 7)</a></li>
    <li><a href="#structure">Repository Structure</a></li>
    <li><a href="#about">About</a></li>
  </ol>
</details>

## 🔐 How It Works <a name="how-it-works"></a>

A trust triangle between the **client**, this **API**, and **Supabase** (the Identity Provider):

```text
 1. POST /auth/signup or /auth/login  ──►  this API  ──►  Supabase Auth  (checks the password, hashes, stores users)
 2.                    access_token  ◄──  this API  ◄──  Supabase signs a JWT
 3. GET /protected/profile + "Authorization: Bearer <access_token>"  ──►  this API
 4.                    this API asks Supabase: "is this token real?"  (supabase.auth.get_user(token))
 5.                    yes → 200 + the user        no → 401 {"error": "Invalid or expired token"}
```

This API **never stores a password and never hashes anything itself**. It forwards credentials to Supabase and
verifies the tokens Supabase hands back.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## 🎯 Getting Started <a name="getting-started"></a>

You need Python 3.10+ and a free [Supabase](https://supabase.com) project (no card).

**1. Supabase (one time, ~3 min)**

- Create a project. In **Authentication → Sign In / Providers → Email**, turn **Confirm email off**, so a new signup
  can log in immediately. (Leave it on in production: email confirmation is a real security feature.)
- In **Project Settings → API Keys**, copy the **Project URL** and the **publishable** key (`sb_publishable_...`) or
  the legacy **anon** key (`eyJ...`). **Never** use the `service_role` / `sb_secret_` key here: it bypasses all security.

**2. Run it**

```bash
git clone https://github.com/azizulabedinazmi/FlyRank_BE-03.git
cd FlyRank_BE-03
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # Windows PowerShell: Copy-Item .env.example .env   — then fill in your values
python main.py
```

```text
Server running and connected to Supabase (https://<your-project>.supabase.co)
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

`python main.py` is the one command. On startup the app calls Supabase's `/auth/v1/settings` with your key, so a
wrong URL or key stops it immediately with a clear message instead of failing on the first request.
Swagger UI: http://127.0.0.1:8000/docs

### Environment variables (`.env`)

| Variable | Required | What it is |
|---|---|---|
| `SUPABASE_URL` | yes | `https://<project-ref>.supabase.co` |
| `SUPABASE_KEY` | yes | The **public** key: publishable (`sb_publishable_...`) or anon (`eyJ...`) |
| `PORT` | no | Default `8000` |
| `ADMIN_EMAILS` | no | Comma-separated emails allowed into `GET /protected/admin` |

`.env` is in `.gitignore` and has never been committed. `.env.example` (placeholders only) is the committed template.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## 🔌 API Reference <a name="api-reference"></a>

| Method | Path | Auth | Body | Success | Errors |
|---|---|---|---|---|---|
| POST | `/auth/signup` | – | `{"email", "password"}` | **201** `{id, email, created_at}` | 400 missing/invalid input · 409 email taken · 429 |
| POST | `/auth/login` | – | `{"email", "password"}` | **200** `{access_token, refresh_token, token_type, expires_in, expires_at, user}` | 400 missing · 401 `Invalid login credentials` · 429 too many failures |
| POST | `/auth/logout` | 🔒 Bearer | – | **204** (empty) | 401 |
| GET | `/public/info` | – | – | **200** `{"message": "Welcome stranger! This info is public."}` | – |
| GET | `/protected/profile` | 🔒 Bearer | – | **200** `{id, email, created_at}` | 401 |
| GET | `/protected/dashboard` | 🔒 Bearer | – | **200** a second route on the same guard | 401 |
| POST | `/auth/refresh` *(extra)* | – | `{"refresh_token"}` | **200** new token pair | 400 · 401 |
| GET | `/protected/admin` *(extra)* | 🔒 Bearer | – | **200** for `ADMIN_EMAILS` | 401 · **403** `Admins only` |

Every error is JSON: `{"error": "..."}`. The two 401 messages tell the client what went wrong:

| Situation | Status | Body |
|---|---|---|
| No `Authorization` header, `Bearer` with nothing after it, `Basic ...`, a token without the `Bearer ` prefix, `Bearer a b` | 401 | `{"error": "Access token required"}` |
| A token Supabase rejects: tampered, expired, made up, or from a logged-out session | 401 | `{"error": "Invalid or expired token"}` |
| Supabase itself unreachable | 503 | `{"error": "Could not reach Supabase: ..."}` (fails **closed**, never lets the request through) |

Every 401 also carries `WWW-Authenticate: Bearer`, the standard hint telling a client which credentials to send.
FastAPI's default 422 for bad input is replaced with 400, and removed from the docs since it's never sent.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## 📖 Swagger UI <a name="swagger"></a>

http://127.0.0.1:8000/docs. The **Authorize** button and the padlocks on the four protected routes come from
FastAPI's `HTTPBearer` security scheme.

![Swagger UI: auth, public and protected routes, with padlocks on /auth/logout and the /protected routes](docs/swagger-endpoints.png)

Click **Authorize**, paste the `access_token` from `POST /auth/login` (without the word `Bearer`), then
**Try it out → Execute** on `GET /protected/profile`:

![Swagger UI: GET /protected/profile executed with the bearer token, server response 200 with id, email and created_at](docs/swagger-profile-200.png)

(Both screenshots were taken by a script driving Swagger in Edge against the live server. The token visible in the
curl box belonged to a throwaway user whose session was logged out right after, so it no longer works.)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## 💻 The Full Flow with `curl -i` <a name="curl"></a>

A real session against Supabase (tokens truncated; full output in [`docs/curl-session.txt`](docs/curl-session.txt)):

```text
$ curl -i -X POST http://127.0.0.1:8000/auth/signup -H "Content-Type: application/json" -d '{"email":"demo-qrzwuy@mailinator.com","password":"password123"}'
HTTP/1.1 201 Created
content-type: application/json

{"id":"fa73e2d8-850c-4259-89e6-e08c231e28a4","email":"demo-qrzwuy@mailinator.com","created_at":"2026-11-25T09:24:43.922557+00:00"}

$ curl -i -X POST http://127.0.0.1:8000/auth/signup -H "Content-Type: application/json" -d '{"email":"demo-qrzwuy@mailinator.com"}'
HTTP/1.1 400 Bad Request

{"error":"email and password are required"}

$ curl -i -X POST http://127.0.0.1:8000/auth/login -H "Content-Type: application/json" -d '{"email":"demo-qrzwuy@mailinator.com","password":"password123"}'
HTTP/1.1 200 OK

{"access_token":"eyJhbGciOiJFUzI1NiIs...<truncated>","refresh_token":"<truncated>","token_type":"bearer","expires_in":3600,"expires_at":1795602284,"user":{"id":"fa73e2d8-...","email":"demo-qrzwuy@mailinator.com","created_at":"2026-11-25T09:24:43.922557+00:00"}}

$ curl -i http://127.0.0.1:8000/public/info
HTTP/1.1 200 OK

{"message":"Welcome stranger! This info is public."}

$ curl -i http://127.0.0.1:8000/protected/profile
HTTP/1.1 401 Unauthorized
www-authenticate: Bearer

{"error":"Access token required"}

$ curl -i http://127.0.0.1:8000/protected/profile -H "Authorization: Bearer <access_token>"
HTTP/1.1 200 OK

{"id":"fa73e2d8-850c-4259-89e6-e08c231e28a4","email":"demo-qrzwuy@mailinator.com","created_at":"2026-11-25T09:24:43.922557+00:00"}

$ curl -i http://127.0.0.1:8000/protected/profile -H "Authorization: Bearer <access_token with one character changed>"
HTTP/1.1 401 Unauthorized
www-authenticate: Bearer

{"error":"Invalid or expired token"}

$ curl -i -X POST http://127.0.0.1:8000/auth/logout -H "Authorization: Bearer <access_token>"
HTTP/1.1 204 No Content

$ curl -i http://127.0.0.1:8000/protected/profile -H "Authorization: Bearer <the same access_token, after logout>"
HTTP/1.1 401 Unauthorized

{"error":"Invalid or expired token"}
```

> Windows PowerShell: use `curl.exe`, and pass JSON from a file (`--data-binary "@body.json"`) because PowerShell
> mangles the quotes in `-d '{...}'`.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## 🛡️ The Guard (reusable dependency) <a name="guard"></a>

All token logic lives in [`auth.py`](auth.py). A protected route only has to ask for it:

```python
@app.get("/protected/dashboard")
def dashboard(user: CurrentUser = Depends(current_user)):   # the route body runs only for a verified user
    return {"message": f"Welcome to your dashboard, {user.email}!", "user_id": user.id}
```

`current_user` does two things, in order:

1. **Extract.** `HTTPBearer(auto_error=False)` splits `Authorization: Bearer <token>` and returns `None` for a missing
   or non-Bearer header. It's `auto_error=False` because FastAPI's built-in error is a 403 `{"detail": ...}`; we raise
   our own 401 `{"error": "Access token required"}` instead. An empty token or one containing a space is also rejected.
2. **Verify.** `supabase.auth.get_user(token)` is a network call to Supabase, so it catches tampered, expired,
   made-up **and logged-out** tokens. Any rejection → 401 `Invalid or expired token`. If Supabase can't be reached → 503.

`/protected/profile`, `/protected/dashboard`, `/protected/admin` and `POST /auth/logout` all use it, and none of them
contains a line of token-checking code. `require_admin` builds on it: it first gets the verified user from
`current_user`, then checks the email.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## 🧪 Testing: 29 live checks <a name="testing"></a>

[`checkpoint.py`](checkpoint.py) runs every stage's checkpoint against a running server and a real Supabase project.
It creates a fresh throwaway user each run (`@mailinator.com`: Supabase rejects domains that can't receive mail).

```bash
python main.py                                   # terminal 1
python checkpoint.py http://127.0.0.1:8000 --extras   # terminal 2
```

Result: **29/29 passed** ([full table](docs/checkpoint-results.md)). It covers:

- **Stage 1:** signup → 201; signup without a password, and with an empty body → 400; login with an empty password → 400;
  wrong password → 401 `Invalid login credentials`; login → 200 with an `access_token`
- **Stage 2:** `/public/info` → 200; profile with no header, `Bearer`, `Bearer ` (empty), the raw token without
  `Bearer `, `Basic ...` and `Bearer a b` → each 401 `Access token required`
- **Stage 3:** a valid token → 200 + user (and no token echoed back); **one character changed** → 401; garbage → 401
- **Stage 4:** dashboard valid → 200, tampered → 401, none → 401; logout with no token → 401; logout → **204**;
  **the same token after logout → 401**
- **Extras:** admin route as a normal user → 403; refresh with nothing → 400, bogus → 401, real → 200 + a new token
  that works; 5 wrong passwords → 401 ×5, then **429**

The admin 200 path was checked separately: I started a second server with a test account in `ADMIN_EMAILS`, and it
got `200 {"message": "Hello admin ..."}` while a normal user gets 403.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## ⭐ Extras: 403, refresh, rate limit, logout, JWT <a name="extras"></a>

- **401 vs 403** (`GET /protected/admin`): **401** means "I don't know who you are": no token, or a bad one.
  **403** means "I know exactly who you are, and no". A normal logged-in user gets 403 `Admins only`. Authentication
  answers *who*; authorization answers *what you may do*.
- **Refresh tokens** (`POST /auth/refresh`): access tokens are short-lived (Supabase: 1 hour) so a stolen one stops
  working soon. The long-lived refresh token gets a new access token without asking for the password again, and
  Supabase rotates it on every use.
- **Rate-limited login** ([`ratelimit.py`](ratelimit.py)): 5 failed logins for the same email from the same IP inside
  15 minutes → **429** with a `Retry-After` header, checked *before* Supabase is called. Brute-force protection lives at
  the login door because that's the one place an attacker can guess passwords at full speed. (It's in memory, so it's
  per process; several servers would share the counters in Redis.)
- **Real logout:** after `POST /auth/logout` the same, unexpired access token gets **401**. A JWT is "stateless" (its
  signature stays valid until `exp`), so a server that only checks the signature locally *can't* log anyone out early.
  This works because `get_user` asks Supabase, which checks that the token's `session_id` still exists. The price is one
  network call per request; that trade-off is why instant logout is genuinely hard with JWTs.
- **Reading the token myself.** I decoded a real access token. The header is `{"alg": "ES256", "kid": "...", "typ": "JWT"}`,
  and the payload is plain base64, readable by anyone:

  ```json
  { "iss": "https://<project-ref>.supabase.co/auth/v1", "sub": "0f467320-...", "aud": "authenticated",
    "exp": 1795602374, "iat": 1795598774, "email": "jwt-f4b6d0@mailinator.com", "role": "authenticated",
    "aal": "aal1", "amr": [{"method": "password", "timestamp": 1795598774}],
    "session_id": "a2b71d2d-...", "is_anonymous": false, "app_metadata": {"provider": "email"}, "user_metadata": {...} }
  ```

  It holds *who* (`sub`, `email`, `role`), *for how long* (`exp - iat` = 3600 s) and *which session* (`session_id`, the
  claim logout relies on). A JWT is **signed, not encrypted**: the signature stops anyone *changing* it, but anyone holding it
  can *read* it. So you never put a secret in one.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## 🔒 Security Decisions <a name="security"></a>

- **Only the public key.** The app uses the publishable/anon key, the one Supabase designs to be used by clients.
  The `service_role`/secret key bypasses every Row Level Security rule and is never used or needed.
- **A fresh Supabase client per request** (`supabase_client.new_client()`, no persisted session, no background refresh).
  A Supabase client remembers the last session it signed in. One shared client on a server would mix users' sessions,
  and `get_user()` called with an empty token **falls back to that stored session** (I read the SDK source to confirm).
  So an empty `Bearer ` header could have authenticated someone as the previous user. Two layers stop that: the guard
  rejects empty tokens before Supabase is called, and the clients never hold a session.
- **Fails closed.** If Supabase can't be reached, protected routes return 503. They never "skip" the check.
- **Nothing private leaves the server.** Profile responses contain only `id`, `email`, `created_at`, not tokens,
  identities or metadata. Tokens are never logged.
- **No secrets in git.** `.env` was in `.gitignore` before the first commit. `git log --all -- .env` is empty, and a
  scan of every commit for `sb_publishable_`/`sb_secret_` keys and the project URL finds nothing.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## 🤖 AI vs Me (Stage 7) <a name="ai-vs-me"></a>

After building the API by hand, I gave the same job to an AI (Claude, in a fresh session that saw only the prompt) and
ran its code against the same Supabase project. Its code is kept apart in [`ai-version/`](ai-version/); my code
wasn't changed by it, except for one bug fix of mine that its tests exposed (below).

- [`PROMPT-v1.md`](ai-version/PROMPT-v1.md) and [`v1/`](ai-version/v1/): the first prompt and the code it produced
- [`PROMPT-v2.md`](ai-version/PROMPT-v2.md) and [`v2/`](ai-version/v2/): the rematch
- Same tests for all three: my live [`checkpoint.py`](checkpoint.py) and [`security_probe.py`](ai-version/security_probe.py)
  (duplicate email, weak password, `WWW-Authenticate`, `BEARER` in capitals, `Bearer <tab>`, a forged `alg: none`
  token, 7 wrong passwords in a row)
- Results: `results-ai-v1.md`, `results-ai-v2.md`, `probe-mine.md`, `probe-ai-v1.md`, `probe-ai-v2.md`

### Prompt (v1)

```text
Build me a small auth API in Python with FastAPI that uses Supabase Auth (the `supabase` PyPI package).

- Read SUPABASE_URL and SUPABASE_KEY (the anon key) from a .env file with python-dotenv. Give me a .env.example.
- Routes:
  - POST /auth/signup  {email, password} -> 201 with the user. 400 if email or password is missing.
  - POST /auth/login   {email, password} -> 200 with access_token and refresh_token. 400 if a field is missing,
    401 {"error": "Invalid login credentials"} if Supabase rejects them.
  - POST /auth/logout  needs "Authorization: Bearer <token>" -> 204.
  - GET /public/info   no auth -> 200 {"message": "Welcome stranger! This info is public."}
  - GET /protected/profile  needs the bearer token -> 200 with the user's id, email and created_at.
  - GET /protected/dashboard  another protected route.
- Missing token -> 401 {"error": "Access token required"}. Invalid or expired token -> 401
  {"error": "Invalid or expired token"}. Verify tokens with supabase.auth.get_user(token).
- Put the token check in one reusable FastAPI dependency used by all protected routes.
- Use HTTPBearer so Swagger UI at /docs shows the Authorize button.
- Errors are JSON with an "error" key.
```

### Results (all live against Supabase)

| Check | Mine | AI v1 | AI v2 |
|---|---|---|---|
| Stage 1–4 checkpoints (signup, login, 6 malformed headers, valid/tampered/garbage token, dashboard, logout, token after logout) | 22/22 | **21/22** | 22/22 |
| Extras (403 admin, refresh ×4, 429 brute force) | 7/7 | not built (not asked) | 7/7 |
| Signup response | `id, email, created_at` | **the whole Supabase user: 26 fields** ❌ | `id, email, created_at` |
| Existing email | 409 | **422** ❌ | 409 |
| Weak password | 400 (after my fix, see below) | **422** ❌ | 400 |
| 401 carries `WWW-Authenticate: Bearer` | yes | **no** | yes |
| `BEARER <token>` / `Bearer <tab>` / forged `alg: none` token | 200 / 401 / 401 | 200 / 401 / 401 | 200 / 401 / 401 |
| 7 wrong passwords in a row | 401 ×5, then 429 | **401 ×7, no limit** | 401 ×5, then 429 |
| Code size (non-blank lines) | 287 in 5 modules | 201 in 1 file | 478 in 6 modules + 20 offline tests |

### 1. Token extraction: did it handle the `"Bearer "` prefix?

**Yes, both versions, safely.** Both used `HTTPBearer(auto_error=False)`, which splits the header on the first space and
compares the scheme case-insensitively. So `Authorization: <token>` without the prefix, `Basic ...` and an empty
`Bearer ` all became our own 401 `Access token required`, not a crash and not FastAPI's 403 `{"detail": ...}`.
v1 also checked `not credentials.credentials` before calling Supabase, which matters (see the next section).
The one difference: for `Bearer a b`, v1 says `Invalid or expired token` while mine says `Access token required`,
since a token with a space in it isn't a token at all.

### 2. Security: did it safely handle invalid tokens?

- **Invalid tokens: safe.** It never trusted `get_user` blindly. It caught the error and returned 401, checked for a
  `None` user, and mapped network failures to 503, so it fails **closed**. Tampered, garbage and forged `alg: none`
  tokens all got 401. It never used the `service_role` key and never logged a token.
- **The trap it stepped around:** `supabase.auth.get_user("")` falls back to the client's *stored session*. v1 used one
  **shared** client for every `get_user` call, which is exactly the setup where that trap bites. It was safe only
  because (a) it rejected empty tokens first and (b) that shared client never signed anyone in. One later "small
  refactor" that logs in with the shared client would turn an empty `Bearer ` header into "you are the last user who
  logged in". Mine and v2 use a fresh, session-less client per request, so there's no stored session to fall back to.
- **It over-shared on signup.** It returned the full Supabase user object (26 fields: `identities`, `app_metadata`,
  `confirmation_sent_at`, `role`, `action_link`...). That's not a token leak, but a public endpoint shouldn't hand
  internal account state to whoever calls it.
- **No brute-force protection.** Seven wrong passwords got seven 401s. Supabase has its own project-wide limits,
  but nothing stopped one script hammering one account through this API.
- **A wrong security comment.** v1's logout says the access token "stays valid until it expires". The live test
  shows the opposite: after logout the same token gets 401, because `get_user` asks Supabase, which checks the token's
  `session_id`. It wrote down what's true for *locally verified* JWTs without testing it.
- **It caught a bug in mine.** Running the weak-password probe against all three showed **my** API answering
  **503 "Could not reach Supabase: AuthWeakPasswordError"**. The SDK raises `AuthWeakPasswordError`, which is *not* an
  `AuthApiError`, so my code treated it as "Supabase is down". v1 had the same root mistake, hidden by passing the status
  through (422). I fixed mine (`Fix: weak password returned 503 instead of 400`): now only `AuthRetryableError`
  (a real network failure) means 503.

### 3. What my prompt missed, and what the AI assumed

- **The response shape.** "201 with the user" was all I wrote, so it returned *all* of the user.
- **Status codes beyond the happy path.** I listed 400 for *missing* fields but nothing for "already registered" or
  "weak password", so it passed Supabase's 422 straight through. That contradicts its own (correct) choice of turning
  FastAPI's 422 into 400.
- **`WWW-Authenticate`, rate limiting, refresh and the admin route.** None were asked for, so none were built.
- **Client lifetime.** I didn't say "one client per request", so it chose a shared client for verification. It was safe
  today, but only by two coincidences.
- **What it decided well on its own:** 503 instead of 401 when Supabase is unreachable, `admin.sign_out(token, "local")`
  for logout (a plain `sign_out()` on a session-less client logs nobody out), and 400 instead of 422 for malformed JSON.

### Rematch (v2)

[`PROMPT-v2.md`](ai-version/PROMPT-v2.md) added: the exact signup shape, never 422 (409 for duplicates, 400 for weak
passwords), `WWW-Authenticate`, a fresh client per request, refresh + admin + rate limit, and "after logout the same
token must be rejected: test this, don't assume". **v2 passed 29/29 live and every probe.** It went further than mine
in two places: it remembers a hash of logged-out tokens, so they're refused even if Supabase still accepted them, and it
returns 409 when "Confirm email" is on and Supabase quietly hands back a fake user for an existing email. The cost was
size: 478 lines across 6 modules against my 287.

**Lesson:** v1 handled the security-critical parts (the Bearer prefix and invalid tokens) correctly, and still failed
on everything I hadn't written down: response shape, error codes, rate limiting, and a comment that was wrong about how
logout works. Running the same probes on all three versions also found a real bug in *my* code. Building it myself is
what let me write those probes; running them on the AI's code is what pointed them back at mine.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## 🗂️ Repository Structure <a name="structure"></a>

| Path | Purpose |
|---|---|
| `main.py` | The app and all routes. `python main.py` starts it on `PORT`. |
| `auth.py` | The guard: `HTTPBearer` + `current_user` (extract → verify with Supabase) and `require_admin`. |
| `supabase_client.py` | Reads `.env`, builds a fresh session-less Supabase client per request, startup connection check. |
| `errors.py` | One error shape (`{"error": ...}`), 400 instead of 422, error docs for Swagger. |
| `ratelimit.py` | Failed-login counter for the 429 extra. |
| `checkpoint.py` | 29 live checks across Stages 1–4 and the extras. |
| `docs/` | Swagger screenshots, the curl session and the checkpoint results. |
| `ai-version/` | Stage 7: both AI versions, both prompts, the security probe and all results. |
| `.env.example` | The variables to set (placeholders only). |

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## 👋 About <a name="about"></a>

Built by **Azizul Abedin Azmi**, Machine Learning Intern at [FlyRank AI](https://www.flyrank.ai/), as assignment
**BE-03 / A4 (Auth: Login & protect)** of the Backend AI Engineering track of the
[FlyRank AI Internship](https://internship.flyrank.ai/). Earlier work in this track:
[FlyRank_BE-01](https://github.com/azizulabedinazmi/FlyRank_BE-01) (CRUD API → SQLite → Postgres in Docker).

[![FlyRank verified](https://img.shields.io/badge/FlyRank_verified-FR--D1--A84A9--AB526-1A7A4A?style=for-the-badge)](https://internship.flyrank.ai/verify?id=FR-D1-A84A9-AB526&first_name=Azizul)

[LinkedIn](https://www.linkedin.com/in/azizulabedin/) · [Portfolio](https://azizulabedinazmi.netlify.app/) · MIT License

<p align="right">(<a href="#readme-top">back to top</a>)</p>

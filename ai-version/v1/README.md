# Auth API (FastAPI + Supabase Auth)

## Setup

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then put your SUPABASE_URL and anon SUPABASE_KEY in .env
```

## Run (port 8000)

Either of these works:

```bash
python main.py
# or
uvicorn main:app --port 8000
```

Swagger UI: http://127.0.0.1:8000/docs. Log in with `/auth/login`, copy `access_token`,
click **Authorize** and paste the token (without the `Bearer ` prefix).

## Routes

| Method | Path                   | Auth   | Success                                         |
|--------|------------------------|--------|-------------------------------------------------|
| POST   | `/auth/signup`         | no     | 201 `{"user": {...}}`                           |
| POST   | `/auth/login`          | no     | 200 `{"access_token", "refresh_token", ...}`    |
| POST   | `/auth/logout`         | bearer | 204                                             |
| GET    | `/public/info`         | no     | 200 `{"message": "Welcome stranger! ..."}`      |
| GET    | `/protected/profile`   | bearer | 200 `{"id", "email", "created_at"}`             |
| GET    | `/protected/dashboard` | bearer | 200 welcome message                             |

Errors are always `{"error": "..."}`:

- 400 `Email and password are required` (missing field, or malformed body)
- 401 `Invalid login credentials` (Supabase rejected the login)
- 401 `Access token required` (no `Authorization: Bearer` header)
- 401 `Invalid or expired token` (`supabase.auth.get_user(token)` failed)

## Notes

- All protected routes use the one `get_current_user` dependency in `main.py`.
- If "Confirm email" is on in your Supabase project, signup returns the user but
  login fails with 401 until the email is confirmed.
- Logout revokes the session's refresh token. The access token is a JWT and stays
  valid until it expires; Supabase cannot revoke it early.

## Quick test (curl)

```bash
curl -X POST localhost:8000/auth/signup -H "Content-Type: application/json" -d '{"email":"a@example.com","password":"secret123"}'
curl -X POST localhost:8000/auth/login  -H "Content-Type: application/json" -d '{"email":"a@example.com","password":"secret123"}'
curl localhost:8000/protected/profile -H "Authorization: Bearer <access_token>"
curl -X POST localhost:8000/auth/logout -H "Authorization: Bearer <access_token>"
```

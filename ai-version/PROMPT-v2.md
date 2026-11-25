# Prompt v2 (Stage 7 rematch)

v1 passed 21/22 live checks and handled the Bearer prefix and invalid tokens safely, but it returned the whole
Supabase user object (26 fields) from signup, passed Supabase's 422 straight through for "already registered" and weak
passwords, had no brute-force protection, and its logout comment wrongly said the access token keeps working.
v2 = v1 + the NEW block. Sent to a fresh AI session.

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

NEW:
- Signup returns exactly {"id", "email", "created_at"}, never the full Supabase user object or any token.
- Never return 422. Email already registered -> 409. Other Supabase validation errors (weak password, bad email)
  -> 400 with Supabase's message. Supabase unreachable -> 503 on every route; a protected route must never let a
  request through when it can't verify the token.
- Every 401 includes the header "WWW-Authenticate: Bearer".
- Use a new Supabase client (no persisted session, no auto refresh) for every request, never a shared one.
- POST /auth/refresh {refresh_token} -> 200 with a new access_token and refresh_token; 400 if missing, 401 if invalid.
- GET /protected/admin -> 200 only for emails listed in an ADMIN_EMAILS env var (comma-separated), 403
  {"error": "Admins only"} for any other logged-in user, 401 without a valid token.
- Rate-limit POST /auth/login: after 5 failed attempts for the same email from the same IP within 15 minutes,
  return 429 with a Retry-After header, without calling Supabase.
- After logout, the same access token must be rejected with 401 (test this; don't assume).
- Start with `python main.py` on PORT (default 8000).
```

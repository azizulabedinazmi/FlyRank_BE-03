# Prompt v1 (Stage 7 AI rematch)

Sent to a fresh AI session (Claude) with no access to this repo.

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

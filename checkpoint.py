"""Live checkpoint for the whole assignment: run it against a server that is already running.

Usage:  python checkpoint.py [base_url] [--extras]
        python checkpoint.py http://127.0.0.1:8000 --extras

It creates a fresh throwaway user (unique email each run), then walks Stages 1-4 (plus the stretch routes with
--extras) and prints a results table. Needs "Confirm email" turned off in Supabase so the new user can log in.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

args = [a for a in sys.argv[1:] if not a.startswith("--")]
BASE = (args[0] if args else "http://127.0.0.1:8000").rstrip("/")
EXTRAS = "--extras" in sys.argv
# Supabase rejects domains that can't receive mail, so test users need a real domain. mailinator.com is a public
# throwaway inbox: even if "Confirm email" were left on, nobody's real mailbox gets the message.
EMAIL_DOMAIN = os.environ.get("CHECKPOINT_EMAIL_DOMAIN", "mailinator.com")

results = []


def call(method, path, body=None, token=None, raw_auth=None, raw=None):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(BASE + path, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if raw_auth is not None:
        req.add_header("Authorization", raw_auth)
    elif token is not None:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            status, text, headers = r.status, r.read().decode(), r.headers
    except urllib.error.HTTPError as e:
        status, text, headers = e.code, e.read().decode(), e.headers
    try:
        payload = json.loads(text) if text else None
    except json.JSONDecodeError:
        payload = text
    return status, payload, headers


def check(name, expected, got, payload=None, extra_ok=True):
    ok = bool(got == expected and extra_ok)
    short = json.dumps(payload)[:80] if payload is not None else "(empty)"
    results.append((name, expected, got, ok, short))
    return ok


def tamper(token: str) -> str:
    """Change one character in the signature part (the last segment)."""
    i = len(token) - 5
    return token[:i] + ("A" if token[i] != "A" else "B") + token[i + 1:]


if not urllib.request.urlopen(BASE + "/openapi.json", timeout=10).status == 200:
    sys.exit("server not reachable")
email = f"checkpoint-{uuid.uuid4().hex[:10]}@{EMAIL_DOMAIN}"
password = "password123"

# --- Stage 1
s, p, _ = call("POST", "/auth/signup", {"email": email, "password": password})
check("1 signup new user -> 201", 201, s, p, isinstance(p, dict) and p.get("email") == email)
s, p, _ = call("POST", "/auth/signup", {"email": email})
check("1 signup without password -> 400", 400, s, p, isinstance(p, dict) and "error" in p)
s, p, _ = call("POST", "/auth/signup", {})
check("1 signup empty body -> 400", 400, s, p)
s, p, _ = call("POST", "/auth/login", {"email": email, "password": ""})
check("1 login empty password -> 400", 400, s, p)
s, p, _ = call("POST", "/auth/login", {"email": email, "password": "wrong-password"})
check("1 login wrong password -> 401", 401, s, p, p == {"error": "Invalid login credentials"})
s, p, _ = call("POST", "/auth/login", {"email": email, "password": password})
check("1 login -> 200 with access_token", 200, s, {"keys": sorted(p) if isinstance(p, dict) else p},
      isinstance(p, dict) and isinstance(p.get("access_token"), str) and p.get("refresh_token"))
token = p.get("access_token") if isinstance(p, dict) else None
refresh_token = p.get("refresh_token") if isinstance(p, dict) else None

# --- Stage 2
s, p, _ = call("GET", "/public/info")
check("2 GET /public/info -> 200", 200, s, p, p == {"message": "Welcome stranger! This info is public."})
s, p, h = call("GET", "/protected/profile")
check("2 profile, no header -> 401", 401, s, p, p == {"error": "Access token required"})
for label, raw in [("'Bearer'", "Bearer"), ("'Bearer ' (empty)", "Bearer "), ("raw token, no 'Bearer '", token or "x"),
                   ("'Basic ...'", "Basic dXNlcjpwYXNz"), ("'Bearer a b'", "Bearer a b")]:
    s, p, _ = call("GET", "/protected/profile", raw_auth=raw)
    check(f"2 profile, header {label} -> 401", 401, s, p)

# --- Stage 3
s, p, _ = call("GET", "/protected/profile", token=token)
check("3 profile, valid token -> 200 + user", 200, s, p,
      isinstance(p, dict) and p.get("email") == email and p.get("id") and p.get("created_at")
      and "access_token" not in json.dumps(p))
s, p, _ = call("GET", "/protected/profile", token=tamper(token))
check("3 profile, one char changed -> 401", 401, s, p, isinstance(p, dict) and "error" in p)
s, p, _ = call("GET", "/protected/profile", token="not.a.jwt")
check("3 profile, garbage token -> 401", 401, s, p)

# --- Stage 4
s, p, _ = call("GET", "/protected/dashboard", token=token)
check("4 dashboard, valid token -> 200", 200, s, p)
s, p, _ = call("GET", "/protected/dashboard", token=tamper(token))
check("4 dashboard, tampered token -> 401", 401, s, p)
s, p, _ = call("GET", "/protected/dashboard")
check("4 dashboard, no token -> 401", 401, s, p)
s, p, _ = call("POST", "/auth/logout")
check("4 logout, no token -> 401", 401, s, p)

if EXTRAS:
    s, p, _ = call("GET", "/protected/admin", token=token)
    check("X admin route, normal user -> 403", 403, s, p)
    s, p, _ = call("GET", "/protected/admin")
    check("X admin route, no token -> 401", 401, s, p)
    s, p, _ = call("POST", "/auth/refresh", {})
    check("X refresh, no token -> 400", 400, s, p)
    s, p, _ = call("POST", "/auth/refresh", {"refresh_token": "bogus"})
    check("X refresh, bogus token -> 401", 401, s, p)
    s, p, _ = call("POST", "/auth/refresh", {"refresh_token": refresh_token})
    check("X refresh, real token -> 200 new access_token", 200, s, {"keys": sorted(p) if isinstance(p, dict) else p},
          isinstance(p, dict) and p.get("access_token") and p.get("access_token") != token)
    if isinstance(p, dict) and p.get("access_token"):
        s2, p2, _ = call("GET", "/protected/profile", token=p["access_token"])
        check("X refreshed token works on profile -> 200", 200, s2, p2)
        token = p["access_token"]  # the refresh rotated the session; log out with the newest token

s, p, _ = call("POST", "/auth/logout", token=token)
check("4 logout, valid token -> 204", 204, s, p, p is None)
time.sleep(1)
s, p, _ = call("GET", "/protected/profile", token=token)
check("4 same token after logout -> 401", 401, s, p)

if EXTRAS:
    victim = f"bruteforce-{uuid.uuid4().hex[:8]}@{EMAIL_DOMAIN}"
    codes = [call("POST", "/auth/login", {"email": victim, "password": f"guess{i}"})[0] for i in range(7)]
    s, p, h = call("POST", "/auth/login", {"email": victim, "password": "guess-again"})
    check(f"X brute force: 5x401 then 429 (got {codes})", 429, s, p, codes[:5] == [401] * 5 and h.get("Retry-After"))

print(f"Testing {BASE} as {email}\n")
print("| Check | Expected | Got | Body |\n|---|---|---|---|")
for name, exp, got, ok, short in results:
    print(f"| {name} | {exp} | {got} {'PASS' if ok else 'FAIL'} | `{short}` |")
print(f"\n{sum(r[3] for r in results)}/{len(results)} passed")

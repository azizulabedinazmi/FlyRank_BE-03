"""Security probes the checkpoint doesn't cover. Usage: python ai-version/security_probe.py http://127.0.0.1:8000"""
import json
import sys
import urllib.error
import urllib.request
import uuid

B = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")


def call(m, p, b=None, auth=None):
    h = {"Content-Type": "application/json"}
    if auth is not None:
        h["Authorization"] = auth
    r = urllib.request.Request(B + p, json.dumps(b).encode() if b is not None else None, h, method=m)
    try:
        with urllib.request.urlopen(r, timeout=30) as x:
            return x.status, x.read().decode(), dict(x.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(), dict(e.headers)


rows = []


def row(name, status, note=""):
    rows.append((name, status, note))


email = f"probe-{uuid.uuid4().hex[:8]}@mailinator.com"
s, d, _ = call("POST", "/auth/signup", {"email": email, "password": "password123"})
body = json.loads(d)
fields = sorted(body.get("user", body))
row("signup response fields", s, f"{len(fields)} fields: {', '.join(fields[:6])}{'...' if len(fields) > 6 else ''}")
s, d, _ = call("POST", "/auth/signup", {"email": email, "password": "password123"})
row("signup an existing email", s, d)
s, d, _ = call("POST", "/auth/signup", {"email": "x" + email, "password": "1"})
row("signup weak password", s, d)
s, d, _ = call("POST", "/auth/login", {"email": email, "password": "password123"})
token = json.loads(d)["access_token"]
s, d, h = call("GET", "/protected/profile")
row("401 carries WWW-Authenticate", s, h.get("www-authenticate") or h.get("WWW-Authenticate") or "missing")
row("'BEARER <token>' (caps scheme)", call("GET", "/protected/profile", auth="BEARER " + token)[0])
row("'Bearer <tab>'", call("GET", "/protected/profile", auth="Bearer \t")[0])
row("forged alg=none token", call("GET", "/protected/profile",
    auth="Bearer eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiIxMjMiLCJyb2xlIjoiYXV0aGVudGljYXRlZCJ9.")[0])
codes = [call("POST", "/auth/login", {"email": email, "password": f"wrong{i}"})[0] for i in range(7)]
row("7 wrong passwords in a row", codes[-1], str(codes))
call("POST", "/auth/logout", auth="Bearer " + token)

print(f"Security probes against {B}\n\n| Probe | Status | Detail |\n|---|---|---|")
for n, s, note in rows:
    print(f"| {n} | {s} | {str(note).replace('|', '/')[:110]} |")

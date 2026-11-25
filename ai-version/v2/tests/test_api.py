"""Offline tests: the real app, with Supabase replaced by an in-memory fake.

Run from the project root:   python -m unittest discover -s tests -v

The fake mimics Supabase Auth's behaviour (including rejecting an access
token whose session was logged out). For the same checks against a real
Supabase project, run smoke_test.py against a running server.
"""

import base64
import json
import os
import sys
import time
import unittest
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-anon-key")
os.environ["ADMIN_EMAILS"] = "boss@example.com, Root@Example.com"

from fastapi.testclient import TestClient  # noqa: E402
from supabase_auth.errors import (  # noqa: E402
    AuthApiError,
    AuthRetryableError,
    AuthWeakPasswordError,
)

import main  # noqa: E402
from app.auth import revoked_tokens  # noqa: E402
from app.supabase_client import get_supabase  # noqa: E402


def make_jwt(session_id: str, user_id: str, ttl: int = 3600) -> str:
    def enc(obj):
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()

    payload = {"sub": user_id, "session_id": session_id, "exp": int(time.time()) + ttl,
               "jti": uuid.uuid4().hex}
    return f"{enc({'alg': 'HS256'})}.{enc(payload)}.sig"


class FakeAuth:
    def __init__(self) -> None:
        self.users: dict[str, dict] = {}
        self.sessions: dict[str, str] = {}      # session_id -> user email
        self.access: dict[str, str] = {}        # access token -> session_id
        self.refresh: dict[str, str] = {}       # refresh token -> session_id
        self.unreachable = False
        self.server_revokes_on_logout = True
        self.sign_in_calls = 0
        self.admin = SimpleNamespace(sign_out=self._admin_sign_out)

    def _check(self):
        if self.unreachable:
            raise AuthRetryableError("[Errno 111] Connection refused", 0)

    def _user_obj(self, email, identities=True):
        u = self.users[email]
        return SimpleNamespace(
            id=u["id"], email=email, created_at=u["created_at"],
            identities=[object()] if identities else [],
            role="authenticated", app_metadata={}, user_metadata={},
        )

    def _new_session(self, email):
        sid = uuid.uuid4().hex
        self.sessions[sid] = email
        at = make_jwt(sid, self.users[email]["id"])
        rt = uuid.uuid4().hex
        self.access[at] = sid
        self.refresh[rt] = sid
        return SimpleNamespace(access_token=at, refresh_token=rt)

    def sign_up(self, creds):
        self._check()
        email, password = creds["email"], creds["password"]
        if "@" not in email:
            raise AuthApiError("Unable to validate email address: invalid format", 400,
                               "validation_failed")
        if len(password) < 6:
            raise AuthWeakPasswordError("Password should be at least 6 characters.", 422,
                                        ["length"])
        if email in self.users:
            raise AuthApiError("User already registered", 422, "user_already_exists")
        self.users[email] = {"id": str(uuid.uuid4()), "password": password,
                             "created_at": datetime.now(timezone.utc)}
        return SimpleNamespace(user=self._user_obj(email), session=self._new_session(email))

    def sign_in_with_password(self, creds):
        self.sign_in_calls += 1
        self._check()
        u = self.users.get(creds["email"])
        if not u or u["password"] != creds["password"]:
            raise AuthApiError("Invalid login credentials", 400, "invalid_credentials")
        return SimpleNamespace(user=self._user_obj(creds["email"]),
                               session=self._new_session(creds["email"]))

    def refresh_session(self, refresh_token):
        self._check()
        sid = self.refresh.pop(refresh_token, None)
        if sid is None or sid not in self.sessions:
            raise AuthApiError("Invalid Refresh Token: Refresh Token Not Found", 400,
                               "refresh_token_not_found")
        email = self.sessions[sid]
        at = make_jwt(sid, self.users[email]["id"])
        rt = uuid.uuid4().hex
        self.access[at] = sid
        self.refresh[rt] = sid
        return SimpleNamespace(user=self._user_obj(email),
                               session=SimpleNamespace(access_token=at, refresh_token=rt))

    def get_user(self, jwt=None):
        self._check()
        sid = self.access.get(jwt)
        if sid is None:
            raise AuthApiError("invalid JWT: unable to parse or verify signature", 403,
                               "bad_jwt")
        if sid not in self.sessions:
            raise AuthApiError("Session from session_id claim in JWT does not exist", 403,
                               "session_not_found")
        return SimpleNamespace(user=self._user_obj(self.sessions[sid]))

    def _admin_sign_out(self, jwt, scope="global"):
        self._check()
        sid = self.access.get(jwt)
        if sid is None or sid not in self.sessions:
            raise AuthApiError("Session not found", 403, "session_not_found")
        if self.server_revokes_on_logout:
            del self.sessions[sid]
            for rt in [k for k, v in self.refresh.items() if v == sid]:
                del self.refresh[rt]


class APITests(unittest.TestCase):
    def setUp(self):
        self.fake = FakeAuth()
        main.app.dependency_overrides[get_supabase] = lambda: SimpleNamespace(auth=self.fake)
        main.login_limiter.clear()
        revoked_tokens.clear()
        self.client = TestClient(main.app, raise_server_exceptions=False)

    def tearDown(self):
        main.app.dependency_overrides.clear()

    # helpers
    def signup(self, email="user@example.com", password="secret123"):
        return self.client.post("/auth/signup", json={"email": email, "password": password})

    def login(self, email="user@example.com", password="secret123"):
        return self.client.post("/auth/login", json={"email": email, "password": password})

    def bearer(self, token):
        return {"Authorization": f"Bearer {token}"}

    def assert_401(self, r, message):
        self.assertEqual(r.status_code, 401, r.text)
        self.assertEqual(r.json(), {"error": message})
        self.assertEqual(r.headers.get("www-authenticate"), "Bearer")

    # signup
    def test_signup_returns_exactly_id_email_created_at(self):
        r = self.signup()
        self.assertEqual(r.status_code, 201)
        self.assertEqual(set(r.json()), {"id", "email", "created_at"})
        self.assertNotIn("token", r.text)

    def test_signup_missing_fields_400(self):
        for body in ({}, {"email": "a@b.c"}, {"password": "x"}, {"email": " ", "password": "p"}):
            r = self.client.post("/auth/signup", json=body)
            self.assertEqual(r.status_code, 400, body)
            self.assertIn("error", r.json())
        self.assertEqual(self.client.post("/auth/signup").status_code, 400)

    def test_never_422(self):
        cases = [
            ("/auth/signup", {"content": b"{not json", "headers": {"Content-Type": "application/json"}}),
            ("/auth/login", {"json": {"email": 123, "password": ["x"]}}),
            ("/auth/login", {"json": ["array"]}),
            ("/auth/refresh", {"json": {"refresh_token": 5}}),
        ]
        for path, kwargs in cases:
            r = self.client.post(path, **kwargs)
            self.assertEqual(r.status_code, 400, (path, r.text))
            self.assertIn("error", r.json())

    def test_signup_duplicate_409(self):
        self.signup()
        r = self.signup()
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json(), {"error": "Email already registered"})

    def test_signup_duplicate_obfuscated_user_409(self):
        self.signup()
        self.fake.sign_up = lambda creds: SimpleNamespace(
            user=self.fake._user_obj("user@example.com", identities=False), session=None)
        self.assertEqual(self.signup().status_code, 409)

    def test_signup_weak_password_and_bad_email_400_with_message(self):
        r = self.signup(password="123")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json(), {"error": "Password should be at least 6 characters."})
        r = self.signup(email="not-an-email")
        self.assertEqual(r.status_code, 400)
        self.assertIn("invalid format", r.json()["error"])

    # login
    def test_login_ok_and_bad_credentials(self):
        self.signup()
        r = self.login()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(set(r.json()), {"access_token", "refresh_token"})
        self.assert_401(self.login(password="wrong"), "Invalid login credentials")
        self.assertEqual(self.client.post("/auth/login", json={"email": "a@b.c"}).status_code, 400)

    def test_login_rate_limit(self):
        self.signup()
        for _ in range(5):
            self.assert_401(self.login(password="wrong"), "Invalid login credentials")
        calls = self.fake.sign_in_calls
        r = self.login()  # even the right password is refused now
        self.assertEqual(r.status_code, 429)
        self.assertIn("error", r.json())
        self.assertGreater(int(r.headers["retry-after"]), 0)
        self.assertLessEqual(int(r.headers["retry-after"]), 900)
        self.assertEqual(self.fake.sign_in_calls, calls, "Supabase must not be called")
        # Same email, different case: same bucket.
        self.assertEqual(self.login(email="USER@example.com").status_code, 429)
        # A different email from the same IP is unaffected.
        self.assertEqual(self.login(email="other@example.com", password="x").status_code, 401)

    def test_rate_limit_window_expires(self):
        now = [1000.0]
        limiter = main.LoginRateLimiter(5, 900, clock=lambda: now[0])
        key = limiter.key("a@b.c", "1.2.3.4")
        for _ in range(5):
            limiter.record_failure(key)
        self.assertEqual(limiter.retry_after(key), 900)
        now[0] += 899.5
        self.assertEqual(limiter.retry_after(key), 1)
        now[0] += 1
        self.assertIsNone(limiter.retry_after(key))

    # tokens / protected routes
    def test_missing_and_invalid_token(self):
        for path in ("/protected/profile", "/protected/dashboard", "/protected/admin"):
            self.assert_401(self.client.get(path), "Access token required")
            self.assert_401(self.client.get(path, headers={"Authorization": "Basic abc"}),
                            "Access token required")
            self.assert_401(self.client.get(path, headers=self.bearer("garbage")),
                            "Invalid or expired token")
        self.assert_401(self.client.post("/auth/logout"), "Access token required")

    def test_profile_and_dashboard(self):
        self.signup()
        token = self.login().json()["access_token"]
        r = self.client.get("/protected/profile", headers=self.bearer(token))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(set(r.json()), {"id", "email", "created_at"})
        self.assertEqual(r.json()["email"], "user@example.com")
        self.assertEqual(self.client.get("/protected/dashboard", headers=self.bearer(token)).status_code, 200)

    def test_public_info(self):
        r = self.client.get("/public/info")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"message": "Welcome stranger! This info is public."})

    def test_admin(self):
        self.signup("boss@example.com")
        self.signup("root@example.com")
        self.signup("user@example.com")
        boss = self.login("boss@example.com").json()["access_token"]
        root = self.login("root@example.com").json()["access_token"]
        user = self.login("user@example.com").json()["access_token"]
        self.assertEqual(self.client.get("/protected/admin", headers=self.bearer(boss)).status_code, 200)
        self.assertEqual(self.client.get("/protected/admin", headers=self.bearer(root)).status_code, 200)
        r = self.client.get("/protected/admin", headers=self.bearer(user))
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json(), {"error": "Admins only"})

    # logout
    def test_logout_then_same_token_rejected(self):
        self.signup()
        tokens = self.login().json()
        h = self.bearer(tokens["access_token"])
        self.assertEqual(self.client.get("/protected/profile", headers=h).status_code, 200)
        r = self.client.post("/auth/logout", headers=h)
        self.assertEqual(r.status_code, 204)
        self.assertEqual(r.content, b"")
        for path in ("/protected/profile", "/protected/dashboard"):
            self.assert_401(self.client.get(path, headers=h), "Invalid or expired token")
        self.assert_401(self.client.post("/auth/logout", headers=h), "Invalid or expired token")
        # The session's refresh token is dead too.
        r = self.client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        self.assertEqual(r.status_code, 401)

    def test_logout_rejected_even_if_server_still_accepts_token(self):
        # Simulates a Supabase that keeps honouring the JWT after logout:
        # the local revocation list must still reject it.
        self.fake.server_revokes_on_logout = False
        self.signup()
        h = self.bearer(self.login().json()["access_token"])
        self.assertEqual(self.client.post("/auth/logout", headers=h).status_code, 204)
        self.assert_401(self.client.get("/protected/profile", headers=h), "Invalid or expired token")

    # refresh
    def test_refresh(self):
        self.signup()
        old = self.login().json()
        r = self.client.post("/auth/refresh", json={"refresh_token": old["refresh_token"]})
        self.assertEqual(r.status_code, 200)
        new = r.json()
        self.assertEqual(set(new), {"access_token", "refresh_token"})
        self.assertEqual(self.client.get("/protected/profile",
                                         headers=self.bearer(new["access_token"])).status_code, 200)
        self.assertEqual(self.client.post("/auth/refresh", json={}).status_code, 400)
        self.assert_401(self.client.post("/auth/refresh", json={"refresh_token": "nope"}),
                        "Invalid or expired refresh token")

    # Supabase down
    def test_supabase_unreachable_503_everywhere(self):
        self.signup()
        token = self.login().json()
        self.fake.unreachable = True
        h = self.bearer(token["access_token"])
        checks = [
            self.signup("new@example.com"),
            self.login(),
            self.client.post("/auth/refresh", json={"refresh_token": token["refresh_token"]}),
            self.client.post("/auth/logout", headers=h),
            self.client.get("/protected/profile", headers=h),
            self.client.get("/protected/dashboard", headers=h),
            self.client.get("/protected/admin", headers=h),
        ]
        for r in checks:
            self.assertEqual(r.status_code, 503, r.text)
            self.assertIn("error", r.json())
        # Unreachable logins must not count toward the rate limit.
        self.assertIsNone(main.login_limiter.retry_after(
            main.login_limiter.key("user@example.com", "testclient")))

    def test_unexpected_sdk_exception_fails_closed(self):
        def boom(jwt=None):
            raise RuntimeError("something odd")
        self.fake.get_user = boom
        r = self.client.get("/protected/profile", headers=self.bearer("whatever"))
        self.assertEqual(r.status_code, 503)

    def test_unknown_route_is_json(self):
        r = self.client.get("/nope")
        self.assertEqual(r.status_code, 404)
        self.assertIn("error", r.json())


class FreshClientTests(unittest.TestCase):
    def test_get_supabase_builds_new_isolated_client_each_time(self):
        gen1, gen2 = get_supabase(), get_supabase()
        c1, c2 = next(gen1), next(gen2)
        try:
            self.assertIsNot(c1, c2)
            self.assertIsNot(c1.auth, c2.auth)
            self.assertFalse(c1.auth._persist_session)
            self.assertFalse(c1.auth._auto_refresh_token)
        finally:
            gen1.close()
            gen2.close()


if __name__ == "__main__":
    unittest.main()

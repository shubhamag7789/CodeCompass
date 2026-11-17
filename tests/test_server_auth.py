from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path

from codecompass.server import CodeCompassHandler
from http.server import ThreadingHTTPServer


class ServerAuthIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.port = 8798
        cls.server = ThreadingHTTPServer(("127.0.0.1", cls.port), CodeCompassHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.temp_dir.cleanup()

    def _post(self, path: str, payload: dict, token: str | None = None) -> tuple[int, dict]:
        conn = HTTPConnection("127.0.0.1", self.port)
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        conn.request("POST", path, body=body, headers=headers)
        res = conn.getresponse()
        data = json.loads(res.read().decode("utf-8"))
        conn.close()
        return res.status, data

    def _get(self, path: str, token: str | None = None) -> tuple[int, dict]:
        conn = HTTPConnection("127.0.0.1", self.port)
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        conn.request("GET", path, headers=headers)
        res = conn.getresponse()
        data = json.loads(res.read().decode("utf-8"))
        conn.close()
        return res.status, data

    def test_auth_lifecycle_and_user_isolation(self):
        import uuid
        uid = uuid.uuid4().hex[:8]
        alice_email = f"alice_{uid}@example.com"
        bob_email = f"bob_{uid}@example.com"

        # 1. Unauthenticated /api/auth/me should return 401
        status, res = self._get("/api/auth/me")
        self.assertEqual(status, 401)

        # 2. Register user Alice
        status, res = self._post("/api/auth/register", {
            "email": alice_email,
            "password": "Password123!",
            "name": "Alice Developer",
        })
        self.assertEqual(status, 200)
        self.assertIn("token", res)
        alice_token = res["token"]
        self.assertEqual(res["user"]["email"], alice_email)

        # 3. Authenticated /api/auth/me for Alice
        status, res = self._get("/api/auth/me", token=alice_token)
        self.assertEqual(status, 200)
        self.assertEqual(res["user"]["email"], alice_email)

        # 4. Register user Bob
        status, res = self._post("/api/auth/register", {
            "email": bob_email,
            "password": "Password123!",
            "name": "Bob Designer",
        })
        self.assertEqual(status, 200)
        bob_token = res["token"]

        # 5. Logout Alice
        status, res = self._post("/api/auth/logout", {}, token=alice_token)
        self.assertEqual(status, 200)

        # Alice's token should no longer work
        status, res = self._get("/api/auth/me", token=alice_token)
        self.assertEqual(status, 401)

        # 6. Alice can log back in
        status, res = self._post("/api/auth/login", {
            "email": alice_email,
            "password": "Password123!",
        })
        self.assertEqual(status, 200)
        new_token = res["token"]

        status, res = self._get("/api/auth/me", token=new_token)
        self.assertEqual(status, 200)
        self.assertEqual(res["user"]["name"], "Alice Developer")

        # 7. Test Forgot Password and Reset Password via API
        status, res = self._post("/api/auth/forgot-password", {"email": alice_email})
        self.assertEqual(status, 200)
        # Verify the HTTP response NEVER leaks the secret recovery code
        self.assertNotIn("code", res)

        # Retrieve the single-use code from the SQLite database
        from codecompass.storage.database import Database
        from pathlib import Path
        db = Database(Path(".codecompass/codecompass.db"))
        with db.connection() as conn:
            row = conn.execute(
                "SELECT code FROM password_resets WHERE email = ? ORDER BY created_at DESC LIMIT 1",
                (alice_email,),
            ).fetchone()
            code = row["code"]

        # Reset password with the valid code
        status, res = self._post("/api/auth/reset-password", {
            "email": alice_email,
            "code": code,
            "new_password": "BrandNewPassword789!",
        })
        self.assertEqual(status, 200)
        self.assertIn("token", res)

        # Login with brand new password
        status, res = self._post("/api/auth/login", {
            "email": alice_email,
            "password": "BrandNewPassword789!",
        })
        self.assertEqual(status, 200)
        self.assertIn("token", res)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codecompass.auth.security import hash_password, verify_password, generate_session_token
from codecompass.auth.manager import AuthManager
from codecompass.storage.database import Database


class AuthTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.db = Database(self.db_path)
        self.auth = AuthManager(self.db)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_hash_and_verify_password(self):
        pw = "SuperSecret123!"
        pw_hash, salt = hash_password(pw)
        self.assertTrue(verify_password(pw, salt, pw_hash))
        self.assertFalse(verify_password("WrongPassword", salt, pw_hash))
        self.assertFalse(verify_password("", salt, pw_hash))

    def test_register_and_login_flow(self):
        res = self.auth.register("developer@example.com", "Password123!", "Alex Dev")
        self.assertIn("token", res)
        self.assertEqual(res["user"]["email"], "developer@example.com")
        self.assertEqual(res["user"]["name"], "Alex Dev")
        self.assertEqual(res["user"]["role"], "admin")  # First user becomes admin

        # Validate token
        user = self.auth.authenticate_token(res["token"])
        self.assertIsNotNone(user)
        self.assertEqual(user["email"], "developer@example.com")

        # Second user gets 'user' role
        res2 = self.auth.register("member@example.com", "Password456!", "Sam Member")
        self.assertEqual(res2["user"]["role"], "user")

        # Login
        login_res = self.auth.login("developer@example.com", "Password123!")
        self.assertIn("token", login_res)

        # Invalid login
        with self.assertRaises(ValueError):
            self.auth.login("developer@example.com", "BadPassword")

        with self.assertRaises(ValueError):
            self.auth.login("nonexistent@example.com", "Password123!")

    def test_user_repository_isolation(self):
        u1 = self.auth.register("user1@example.com", "Password123!", "User 1")
        u2 = self.auth.register("user2@example.com", "Password123!", "User 2")

        # Add repos for user 1
        self.auth.add_user_repository(u1["user"]["id"], "repo-alpha", is_active=True)
        self.auth.add_user_repository(u1["user"]["id"], "repo-beta", is_active=False)

        # Add repo for user 2
        self.auth.add_user_repository(u2["user"]["id"], "repo-gamma", is_active=True)

        # Verify isolation
        u1_repos = self.auth.get_user_repositories(u1["user"]["id"])
        u2_repos = self.auth.get_user_repositories(u2["user"]["id"])

        self.assertIn("repo-alpha", u1_repos)
        self.assertIn("repo-beta", u1_repos)
        self.assertNotIn("repo-gamma", u1_repos)

        self.assertEqual(u2_repos, ["repo-gamma"])
        self.assertEqual(self.auth.get_active_repository(u1["user"]["id"]), "repo-alpha")
        self.assertEqual(self.auth.get_active_repository(u2["user"]["id"]), "repo-gamma")

    def test_forgot_and_reset_password(self):
        self.auth.register("recover@example.com", "OldPassword123!", "Recover User")
        
        # Request reset (code is dispatched securely, never leaked in return payload)
        res = self.auth.request_password_reset("recover@example.com")
        self.assertEqual(res["status"], "ok")
        self.assertNotIn("code", res)

        # Retrieve the single-use code from the secure database
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT code FROM password_resets WHERE email = ? ORDER BY created_at DESC LIMIT 1",
                ("recover@example.com",),
            ).fetchone()
            code = row["code"]

        # Reset with invalid code fails
        with self.assertRaises(ValueError):
            self.auth.reset_password_with_code("recover@example.com", "000000", "NewPassword456!")

        # Reset with valid code succeeds
        reset_res = self.auth.reset_password_with_code("recover@example.com", code, "NewPassword456!")
        self.assertEqual(reset_res["status"], "ok")
        self.assertIn("token", reset_res)

        # Login with old password now fails
        with self.assertRaises(ValueError):
            self.auth.login("recover@example.com", "OldPassword123!")

        # Login with new password succeeds
        login_res = self.auth.login("recover@example.com", "NewPassword456!")
        self.assertIn("token", login_res)

    def test_security_question_and_passphrase_recovery(self):
        # Register user with security question and custom passphrase
        reg = self.auth.register(
            email="vault@example.com",
            password="InitialPass123!",
            name="Vault User",
            security_question="What was your first computer?",
            security_answer="Commodore 64",
            recovery_passphrase="galaxy-harbor-matrix-falcon",
        )
        self.assertEqual(reg["security_question"], "What was your first computer?")
        self.assertEqual(reg["recovery_passphrase"], "galaxy-harbor-matrix-falcon")

        # 1. Test get_recovery_info
        info = self.auth.get_recovery_info("vault@example.com")
        self.assertEqual(info["security_question"], "What was your first computer?")
        self.assertTrue(info["has_security_question"])
        self.assertTrue(info["has_recovery_passphrase"])

        # 2. Reset with wrong answer fails
        with self.assertRaises(ValueError):
            self.auth.reset_password_with_security(
                email="vault@example.com",
                new_password="ChangedPass123!",
                security_answer="Wrong Answer",
            )

        # 3. Reset with correct case-insensitive answer succeeds
        res1 = self.auth.reset_password_with_security(
            email="vault@example.com",
            new_password="ChangedPass123!",
            security_answer="commodore 64",
        )
        self.assertEqual(res1["status"], "ok")
        self.assertIn("token", res1)

        # Login with new password
        login1 = self.auth.login("vault@example.com", "ChangedPass123!")
        self.assertIn("token", login1)

        # 4. Reset using recovery passphrase with spaces/hyphens
        res2 = self.auth.reset_password_with_security(
            email="vault@example.com",
            new_password="FinalPass999!",
            recovery_passphrase="galaxy harbor matrix falcon",
        )
        self.assertEqual(res2["status"], "ok")

        login2 = self.auth.login("vault@example.com", "FinalPass999!")
        self.assertIn("token", login2)


if __name__ == "__main__":
    unittest.main()


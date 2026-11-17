from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from codecompass.auth.security import (
    generate_recovery_passphrase,
    generate_session_token,
    hash_password,
    verify_password,
)
from codecompass.storage.database import Database

SESSION_EXPIRY_DAYS = 30


class AuthManager:
    """Production-grade Authentication & Authorization Manager for CodeCompass."""

    def __init__(self, db: Database) -> None:
        self.db = db
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """Executes table creation and column migrations if not already present."""
        with self.db.transaction() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    security_question TEXT DEFAULT NULL,
                    security_answer_hash TEXT DEFAULT NULL,
                    security_answer_salt TEXT DEFAULT NULL,
                    recovery_passphrase_hash TEXT DEFAULT NULL,
                    recovery_passphrase_salt TEXT DEFAULT NULL,
                    created_at TEXT DEFAULT (datetime('now')),
                    last_login_at TEXT
                );
                """
            )
            # Automatic column migration for existing user databases
            cursor = conn.execute("PRAGMA table_info(users)")
            existing_cols = {row[1] for row in cursor.fetchall()}
            if "security_question" not in existing_cols:
                conn.execute("ALTER TABLE users ADD COLUMN security_question TEXT DEFAULT NULL")
            if "security_answer_hash" not in existing_cols:
                conn.execute("ALTER TABLE users ADD COLUMN security_answer_hash TEXT DEFAULT NULL")
            if "security_answer_salt" not in existing_cols:
                conn.execute("ALTER TABLE users ADD COLUMN security_answer_salt TEXT DEFAULT NULL")
            if "recovery_passphrase_hash" not in existing_cols:
                conn.execute("ALTER TABLE users ADD COLUMN recovery_passphrase_hash TEXT DEFAULT NULL")
            if "recovery_passphrase_salt" not in existing_cols:
                conn.execute("ALTER TABLE users ADD COLUMN recovery_passphrase_salt TEXT DEFAULT NULL")

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now')),
                    expires_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_repositories (
                    user_id TEXT NOT NULL,
                    repo_id TEXT NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT 0,
                    role TEXT NOT NULL DEFAULT 'owner',
                    created_at TEXT DEFAULT (datetime('now')),
                    PRIMARY KEY (user_id, repo_id),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS password_resets (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL,
                    code TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now')),
                    expires_at TEXT NOT NULL,
                    used BOOLEAN NOT NULL DEFAULT 0
                );
                """
            )

    def register(
        self,
        email: str,
        password: str,
        name: str,
        role: str = "user",
        security_question: Optional[str] = None,
        security_answer: Optional[str] = None,
        recovery_passphrase: Optional[str] = None,
    ) -> dict[str, Any]:
        """Registers a new user with optional security question and recovery passphrase."""
        email = (email or "").strip().lower()
        name = (name or "").strip()
        if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
            raise ValueError("Please provide a valid email address.")
        if len(password) < 6:
            raise ValueError("Password must be at least 6 characters long.")
        if not name:
            name = email.split("@")[0].capitalize()

        with self.db.connection() as conn:
            existing = conn.execute(
                "SELECT id FROM users WHERE LOWER(email) = LOWER(?)", (email,)
            ).fetchone()
            if existing:
                raise ValueError("An account with this email address already exists.")

        user_id = str(uuid.uuid4())
        pw_hash, salt = hash_password(password)
        now_iso = datetime.now(timezone.utc).isoformat()

        # Check total users count; if this is the first user, grant 'admin' role
        with self.db.connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            if count == 0:
                role = "admin"

        # Security question & answer hashing
        sec_q = security_question.strip() if security_question else None
        ans_hash, ans_salt = None, None
        if security_answer and security_answer.strip():
            ans_hash, ans_salt = hash_password(security_answer.strip().lower())

        # Recovery passphrase generation and hashing
        if recovery_passphrase and recovery_passphrase.strip():
            plain_passphrase = recovery_passphrase.strip().lower()
        else:
            plain_passphrase = generate_recovery_passphrase(4)
        rec_hash, rec_salt = hash_password(plain_passphrase)

        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO users (
                    id, email, password_hash, salt, name, role,
                    security_question, security_answer_hash, security_answer_salt,
                    recovery_passphrase_hash, recovery_passphrase_salt,
                    created_at, last_login_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id, email, pw_hash, salt, name, role,
                    sec_q, ans_hash, ans_salt,
                    rec_hash, rec_salt,
                    now_iso, now_iso,
                ),
            )

        token = self.create_session(user_id)
        user_info = {
            "id": user_id,
            "email": email,
            "name": name,
            "role": role,
            "created_at": now_iso,
        }
        return {
            "token": token,
            "user": user_info,
            "security_question": sec_q,
            "recovery_passphrase": plain_passphrase,
        }

    def login(self, email: str, password: str) -> dict[str, Any]:
        """Authenticates user with email and password and creates a session token."""
        email = (email or "").strip().lower()
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT id, email, password_hash, salt, name, role, created_at FROM users WHERE LOWER(email) = LOWER(?)",
                (email,),
            ).fetchone()

        if not row:
            raise ValueError("Invalid email or password.")

        if not verify_password(password, row["salt"], row["password_hash"]):
            raise ValueError("Invalid email or password.")

        user_id = row["id"]
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.db.transaction() as conn:
            conn.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (now_iso, user_id))

        token = self.create_session(user_id)
        user_info = {
            "id": user_id,
            "email": row["email"],
            "name": row["name"],
            "role": row["role"],
            "created_at": row["created_at"],
        }
        return {"token": token, "user": user_info}

    def create_session(self, user_id: str) -> str:
        """Creates a session token for the user."""
        token = generate_session_token()
        now = datetime.now(timezone.utc)
        expires_at = (now + timedelta(days=SESSION_EXPIRY_DAYS)).isoformat()
        now_iso = now.isoformat()

        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO sessions (token, user_id, created_at, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (token, user_id, now_iso, expires_at),
            )
        return token

    def authenticate_token(self, token: str | None) -> Optional[dict[str, Any]]:
        """Validates a bearer token and returns user details if valid and unexpired."""
        if not token:
            return None
        token = token.strip()
        now_iso = datetime.now(timezone.utc).isoformat()

        with self.db.connection() as conn:
            row = conn.execute(
                """
                SELECT u.id, u.email, u.name, u.role, u.created_at, s.expires_at
                FROM sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.token = ? AND s.expires_at > ?
                """,
                (token, now_iso),
            ).fetchone()

        if not row:
            return None

        return {
            "id": row["id"],
            "email": row["email"],
            "name": row["name"],
            "role": row["role"],
            "created_at": row["created_at"],
        }

    def logout(self, token: str | None) -> bool:
        """Removes a session token."""
        if not token:
            return False
        with self.db.transaction() as conn:
            cur = conn.execute("DELETE FROM sessions WHERE token = ?", (token.strip(),))
            return cur.rowcount > 0

    def get_user_repositories(self, user_id: str) -> list[str]:
        """Returns the list of repo_ids associated with a given user."""
        with self.db.connection() as conn:
            rows = conn.execute(
                "SELECT repo_id FROM user_repositories WHERE user_id = ? ORDER BY is_active DESC, created_at DESC",
                (user_id,),
            ).fetchall()
            return [r["repo_id"] for r in rows]

    def get_active_repository(self, user_id: str) -> Optional[str]:
        """Returns the user's currently selected active repo_id."""
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT repo_id FROM user_repositories WHERE user_id = ? AND is_active = 1",
                (user_id,),
            ).fetchone()
            if row:
                return row["repo_id"]
            # Fallback to first repo if none marked active
            first = conn.execute(
                "SELECT repo_id FROM user_repositories WHERE user_id = ? ORDER BY created_at ASC LIMIT 1",
                (user_id,),
            ).fetchone()
            return first["repo_id"] if first else None

    def add_user_repository(self, user_id: str, repo_id: str, is_active: bool = True) -> None:
        """Associates a repository with a user."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.db.transaction() as conn:
            if is_active:
                conn.execute(
                    "UPDATE user_repositories SET is_active = 0 WHERE user_id = ?",
                    (user_id,),
                )
            conn.execute(
                """
                INSERT INTO user_repositories (user_id, repo_id, is_active, role, created_at)
                VALUES (?, ?, ?, 'owner', ?)
                ON CONFLICT(user_id, repo_id) DO UPDATE SET
                    is_active = excluded.is_active
                """,
                (user_id, repo_id, int(is_active), now_iso),
            )

    def set_active_repository(self, user_id: str, repo_id: str) -> None:
        """Sets the active repository for a user."""
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE user_repositories SET is_active = 0 WHERE user_id = ?",
                (user_id,),
            )
            conn.execute(
                "UPDATE user_repositories SET is_active = 1 WHERE user_id = ? AND repo_id = ?",
                (user_id, repo_id),
            )

    def remove_user_repository(self, user_id: str, repo_id: str) -> None:
        """Removes the association between a user and a repository."""
        with self.db.transaction() as conn:
            conn.execute(
                "DELETE FROM user_repositories WHERE user_id = ? AND repo_id = ?",
                (user_id, repo_id),
            )
            # If the active repo was removed, make the most recent remaining one active
            active = conn.execute(
                "SELECT repo_id FROM user_repositories WHERE user_id = ? AND is_active = 1",
                (user_id,),
            ).fetchone()
            if not active:
                latest = conn.execute(
                    "SELECT repo_id FROM user_repositories WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
                    (user_id,),
                ).fetchone()
                if latest:
                    conn.execute(
                        "UPDATE user_repositories SET is_active = 1 WHERE user_id = ? AND repo_id = ?",
                        (user_id, latest["repo_id"]),
                    )

    def request_password_reset(self, email: str) -> dict[str, Any]:
        """Generates a 6-digit recovery code and dispatches via email or server console.

        Does not leak the code in the return response and returns a generic status to
        prevent user enumeration.
        """
        from codecompass.auth.notifier import send_recovery_code

        email = (email or "").strip().lower()
        with self.db.connection() as conn:
            row = conn.execute("SELECT id, name FROM users WHERE LOWER(email) = LOWER(?)", (email,)).fetchone()
            if not row:
                # Return generic message to prevent email enumeration
                return {
                    "status": "ok",
                    "message": "If an account with that email exists, a 6-digit recovery code has been sent.",
                }

        import secrets
        code = f"{secrets.randbelow(900000) + 100000}"
        reset_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        expires_at = (now + timedelta(minutes=15)).isoformat()
        now_iso = now.isoformat()

        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO password_resets (id, email, code, created_at, expires_at, used)
                VALUES (?, ?, ?, ?, ?, 0)
                """,
                (reset_id, email, code, now_iso, expires_at),
            )

        # Dispatch code securely to user's email inbox or host server console
        send_recovery_code(email, code)

        # Never return code in HTTP response!
        return {
            "status": "ok",
            "message": "If an account with that email exists, a 6-digit recovery code has been sent.",
        }

    def reset_password_with_code(self, email: str, code: str, new_password: str) -> dict[str, Any]:
        """Validates the reset code and updates the user's password."""
        email = (email or "").strip().lower()
        code = (code or "").strip()
        if len(new_password) < 6:
            raise ValueError("New password must be at least 6 characters long.")

        now_iso = datetime.now(timezone.utc).isoformat()
        with self.db.connection() as conn:
            user = conn.execute("SELECT id, name, role, email FROM users WHERE LOWER(email) = LOWER(?)", (email,)).fetchone()
            if not user:
                raise ValueError("Account not found.")

            reset_row = conn.execute(
                """
                SELECT id FROM password_resets
                WHERE LOWER(email) = LOWER(?) AND code = ? AND used = 0 AND expires_at > ?
                ORDER BY created_at DESC LIMIT 1
                """,
                (email, code, now_iso),
            ).fetchone()

            if not reset_row:
                raise ValueError("Invalid or expired recovery code. Please request a new code.")

        new_hash, new_salt = hash_password(new_password)
        with self.db.transaction() as conn:
            conn.execute("UPDATE users SET password_hash = ?, salt = ? WHERE id = ?", (new_hash, new_salt, user["id"]))
            conn.execute("UPDATE password_resets SET used = 1 WHERE id = ?", (reset_row["id"],))
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user["id"],))

        # Create new login session
        token = self.create_session(user["id"])
        return {
            "status": "ok",
            "token": token,
            "user": {
                "id": user["id"],
                "email": user["email"],
                "name": user["name"],
                "role": user["role"],
            },
        }

    def get_recovery_info(self, email: str) -> dict[str, Any]:
        """Fetches recovery configuration (security question and availability) for an email."""
        email = (email or "").strip().lower()
        with self.db.connection() as conn:
            user = conn.execute(
                """
                SELECT id, email, security_question, security_answer_hash, recovery_passphrase_hash
                FROM users WHERE LOWER(email) = LOWER(?)
                """,
                (email,),
            ).fetchone()
            if not user:
                raise ValueError("No account registered with this email address.")

            has_sq = bool(user["security_question"] and user["security_answer_hash"])
            has_rp = bool(user["recovery_passphrase_hash"])

            return {
                "status": "ok",
                "email": user["email"],
                "security_question": user["security_question"] or "What was the name of your first school or pet?",
                "has_security_question": has_sq,
                "has_recovery_passphrase": has_rp,
            }

    def update_security_settings(
        self,
        user_id: str,
        security_question: str,
        security_answer: str,
        recovery_passphrase: Optional[str] = None,
    ) -> dict[str, Any]:
        """Updates security question, answer, and optional passphrase for an authenticated user."""
        sec_q = (security_question or "").strip()
        sec_ans = (security_answer or "").strip()
        if not sec_q or not sec_ans:
            raise ValueError("Please provide both a security question and answer.")

        ans_hash, ans_salt = hash_password(sec_ans.lower())

        with self.db.transaction() as conn:
            if recovery_passphrase and recovery_passphrase.strip():
                norm_phrase = "-".join(
                    re.split(r"[\s\-]+", recovery_passphrase.strip().lower())
                )
                rec_hash, rec_salt = hash_password(norm_phrase)
                conn.execute(
                    """
                    UPDATE users
                    SET security_question = ?, security_answer_hash = ?, security_answer_salt = ?,
                        recovery_passphrase_hash = ?, recovery_passphrase_salt = ?
                    WHERE id = ?
                    """,
                    (sec_q, ans_hash, ans_salt, rec_hash, rec_salt, user_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE users
                    SET security_question = ?, security_answer_hash = ?, security_answer_salt = ?
                    WHERE id = ?
                    """,
                    (sec_q, ans_hash, ans_salt, user_id),
                )

        return {
            "status": "ok",
            "message": "Security recovery settings updated successfully.",
            "security_question": sec_q,
        }

    def get_user_security_settings(self, user_id: str) -> dict[str, Any]:
        """Returns security question configuration for an authenticated user."""
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT security_question, security_answer_hash, recovery_passphrase_hash FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            if not row:
                raise ValueError("User not found.")
            return {
                "security_question": row["security_question"] or "",
                "has_security_question": bool(row["security_question"] and row["security_answer_hash"]),
                "has_recovery_passphrase": bool(row["recovery_passphrase_hash"]),
            }

    def reset_password_with_security(
        self,
        email: str,
        new_password: str,
        security_answer: Optional[str] = None,
        recovery_passphrase: Optional[str] = None,
        security_question: Optional[str] = None,
    ) -> dict[str, Any]:
        """Resets a user's password using either their security question answer or recovery passphrase."""
        email = (email or "").strip().lower()
        if len(new_password) < 6:
            raise ValueError("New password must be at least 6 characters long.")

        with self.db.connection() as conn:
            user = conn.execute(
                """
                SELECT id, email, name, role,
                       security_question, security_answer_hash, security_answer_salt,
                       recovery_passphrase_hash, recovery_passphrase_salt
                FROM users WHERE LOWER(email) = LOWER(?)
                """,
                (email,),
            ).fetchone()

            if not user:
                raise ValueError("Account not found.")

        # Verification step
        if user["security_answer_hash"] and security_answer:
            if not verify_password(security_answer.strip().lower(), user["security_answer_salt"], user["security_answer_hash"]):
                raise ValueError("Incorrect answer to security question. Please try again.")
        elif user["recovery_passphrase_hash"] and recovery_passphrase:
            # Clean spaces/hyphens for forgiving passphrase entry
            norm_phrase = "-".join(
                re.split(r"[\s\-]+", recovery_passphrase.strip().lower())
            )
            if not verify_password(norm_phrase, user["recovery_passphrase_salt"], user["recovery_passphrase_hash"]):
                raise ValueError("Incorrect recovery passphrase. Please verify each word.")
        elif not user["security_answer_hash"] and not user["recovery_passphrase_hash"]:
            # Legacy account without security recovery set: allow setup now
            pass
        else:
            raise ValueError("Please provide either your security question answer or recovery passphrase.")

        new_hash, new_salt = hash_password(new_password)
        with self.db.transaction() as conn:
            if security_question and security_answer:
                ans_hash, ans_salt = hash_password(security_answer.strip().lower())
                conn.execute(
                    """
                    UPDATE users
                    SET password_hash = ?, salt = ?, security_question = ?, security_answer_hash = ?, security_answer_salt = ?
                    WHERE id = ?
                    """,
                    (new_hash, new_salt, security_question.strip(), ans_hash, ans_salt, user["id"]),
                )
            else:
                conn.execute(
                    "UPDATE users SET password_hash = ?, salt = ? WHERE id = ?",
                    (new_hash, new_salt, user["id"]),
                )

            # Invalidate all active sessions for security
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user["id"],))

        # Create new active session
        token = self.create_session(user["id"])
        return {
            "status": "ok",
            "token": token,
            "user": {
                "id": user["id"],
                "email": user["email"],
                "name": user["name"],
                "role": user["role"],
            },
        }


    def seed_initial_admin(self) -> None:
        """Seeds a default demo/admin user if no users exist in the database."""
        with self.db.connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            if count == 0:
                try:
                    self.register(
                        email="admin@codecompass.dev",
                        password="Password@123",
                        name="Demo Administrator",
                        role="admin",
                    )
                except Exception:
                    pass


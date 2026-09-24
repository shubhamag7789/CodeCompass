from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from codecompass.config import SQLITE_PRAGMAS


class Database:
    """SQLite Database manager with WAL mode for CodeCompass persistence."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path).resolve()
        self._ensure_dir()
        self._init_schema()

    def _ensure_dir(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=15.0,
        )
        conn.row_factory = sqlite3.Row
        for pragma in SQLITE_PRAGMAS:
            conn.execute(pragma)
        return conn

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Provides a managed connection that is guaranteed to close on exit."""
        conn = self.connect()
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Provides a managed connection with transaction commit/rollback."""
        with self.connection() as conn:
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def _init_schema(self) -> None:
        schema_file = Path(__file__).parent / "schema.sql"
        if not schema_file.exists():
            raise FileNotFoundError(f"Schema file not found at {schema_file}")
        schema_sql = schema_file.read_text(encoding="utf-8")

        with self.transaction() as conn:
            conn.executescript(schema_sql)

    def get_journal_mode(self) -> str:
        with self.connection() as conn:
            cursor = conn.execute("PRAGMA journal_mode;")
            row = cursor.fetchone()
            return str(row[0]) if row else ""

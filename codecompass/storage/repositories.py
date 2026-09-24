from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from codecompass.storage.database import Database
from codecompass.storage.models import (
    ConversationRecord,
    ConversationTurnRecord,
    EntityRecord,
    FileRecord,
    RelationshipRecord,
    RepositoryRecord,
    SearchChunkRecord,
)


class RepositoryDAL:
    def __init__(self, db: Database) -> None:
        self.db = db

    def upsert_repository(self, repo: RepositoryRecord) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO repositories (id, name, root_path, last_scanned_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(root_path) DO UPDATE SET
                    name = excluded.name,
                    last_scanned_at = excluded.last_scanned_at
                """,
                (repo.id, repo.name, repo.root_path, now),
            )

    def get_by_root(self, root_path: str) -> RepositoryRecord | None:
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT id, name, root_path, created_at, last_scanned_at FROM repositories WHERE root_path = ?",
                (root_path,),
            ).fetchone()
            if not row:
                return None
            return RepositoryRecord(
                id=row["id"],
                name=row["name"],
                root_path=row["root_path"],
                created_at=str(row["created_at"]) if row["created_at"] else None,
                last_scanned_at=str(row["last_scanned_at"]) if row["last_scanned_at"] else None,
            )


class FileDAL:
    def __init__(self, db: Database) -> None:
        self.db = db

    def upsert_files(self, files: list[FileRecord]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.db.transaction() as conn:
            conn.executemany(
                """
                INSERT INTO files (id, repo_id, path, language, size_bytes, lines, content_hash, is_test, last_scanned_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(repo_id, path) DO UPDATE SET
                    language = excluded.language,
                    size_bytes = excluded.size_bytes,
                    lines = excluded.lines,
                    content_hash = excluded.content_hash,
                    is_test = excluded.is_test,
                    last_scanned_at = excluded.last_scanned_at
                """,
                [
                    (
                        f.id,
                        f.repo_id,
                        f.path,
                        f.language,
                        f.size_bytes,
                        f.lines,
                        f.content_hash,
                        int(f.is_test),
                        now,
                    )
                    for f in files
                ],
            )

    def get_files_for_repo(self, repo_id: str) -> list[FileRecord]:
        with self.db.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, repo_id, path, language, size_bytes, lines, content_hash, is_test, last_scanned_at
                FROM files WHERE repo_id = ? ORDER BY path ASC
                """,
                (repo_id,),
            ).fetchall()
            return [
                FileRecord(
                    id=r["id"],
                    repo_id=r["repo_id"],
                    path=r["path"],
                    language=r["language"],
                    size_bytes=r["size_bytes"],
                    lines=r["lines"],
                    content_hash=r["content_hash"],
                    is_test=bool(r["is_test"]),
                    last_scanned_at=str(r["last_scanned_at"]) if r["last_scanned_at"] else None,
                )
                for r in rows
            ]

    def delete_missing_files(self, repo_id: str, valid_paths: set[str]) -> int:
        with self.db.transaction() as conn:
            rows = conn.execute("SELECT path FROM files WHERE repo_id = ?", (repo_id,)).fetchall()
            existing_paths = {r["path"] for r in rows}
            to_delete = existing_paths - valid_paths
            if not to_delete:
                return 0
            conn.executemany(
                "DELETE FROM files WHERE repo_id = ? AND path = ?",
                [(repo_id, p) for p in to_delete],
            )
            return len(to_delete)


class EntityDAL:
    def __init__(self, db: Database) -> None:
        self.db = db

    def replace_entities_for_file(self, repo_id: str, file_id: str, entities: list[EntityRecord]) -> None:
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM entities WHERE repo_id = ? AND file_id = ?", (repo_id, file_id))
            conn.executemany(
                """
                INSERT INTO entities (
                    id, repo_id, file_id, kind, name, signature,
                    start_line, end_line, start_byte, end_byte,
                    docstring, scope, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        e.id,
                        e.repo_id,
                        e.file_id,
                        e.kind,
                        e.name,
                        e.signature,
                        e.start_line,
                        e.end_line,
                        e.start_byte,
                        e.end_byte,
                        e.docstring,
                        e.scope,
                        e.metadata_json,
                    )
                    for e in entities
                ],
            )

    def get_entities_for_repo(self, repo_id: str) -> list[EntityRecord]:
        with self.db.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, repo_id, file_id, kind, name, signature,
                       start_line, end_line, start_byte, end_byte,
                       docstring, scope, metadata_json
                FROM entities WHERE repo_id = ? ORDER BY start_line ASC
                """,
                (repo_id,),
            ).fetchall()
            return [
                EntityRecord(
                    id=r["id"],
                    repo_id=r["repo_id"],
                    file_id=r["file_id"],
                    kind=r["kind"],
                    name=r["name"],
                    signature=r["signature"],
                    start_line=r["start_line"],
                    end_line=r["end_line"],
                    start_byte=r["start_byte"],
                    end_byte=r["end_byte"],
                    docstring=r["docstring"],
                    scope=r["scope"],
                    metadata_json=r["metadata_json"],
                )
                for r in rows
            ]


class RelationshipDAL:
    def __init__(self, db: Database) -> None:
        self.db = db

    def replace_relationships_for_repo(self, repo_id: str, relationships: list[RelationshipRecord]) -> None:
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM relationships WHERE repo_id = ?", (repo_id,))
            conn.executemany(
                """
                INSERT OR IGNORE INTO relationships (repo_id, source_id, target_id, type, metadata_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        rel.repo_id,
                        rel.source_id,
                        rel.target_id,
                        rel.type,
                        rel.metadata_json,
                    )
                    for rel in relationships
                ],
            )

    def get_relationships_for_repo(self, repo_id: str) -> list[RelationshipRecord]:
        with self.db.connection() as conn:
            rows = conn.execute(
                "SELECT id, repo_id, source_id, target_id, type, metadata_json FROM relationships WHERE repo_id = ?",
                (repo_id,),
            ).fetchall()
            return [
                RelationshipRecord(
                    id=r["id"],
                    repo_id=r["repo_id"],
                    source_id=r["source_id"],
                    target_id=r["target_id"],
                    type=r["type"],
                    metadata_json=r["metadata_json"],
                )
                for r in rows
            ]


class SearchChunkDAL:
    def __init__(self, db: Database) -> None:
        self.db = db

    def replace_chunks_for_file(self, repo_id: str, file_id: str, chunks: list[SearchChunkRecord]) -> None:
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM search_chunks WHERE repo_id = ? AND file_id = ?", (repo_id, file_id))
            conn.executemany(
                """
                INSERT INTO search_chunks (
                    id, repo_id, file_id, entity_id, start_line, end_line, label, content, tokens_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        c.id,
                        c.repo_id,
                        c.file_id,
                        c.entity_id,
                        c.start_line,
                        c.end_line,
                        c.label,
                        c.content,
                        c.tokens_json,
                    )
                    for c in chunks
                ],
            )

    def get_chunks_for_repo(self, repo_id: str) -> list[SearchChunkRecord]:
        with self.db.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, repo_id, file_id, entity_id, start_line, end_line, label, content, tokens_json
                FROM search_chunks WHERE repo_id = ?
                """,
                (repo_id,),
            ).fetchall()
            return [
                SearchChunkRecord(
                    id=r["id"],
                    repo_id=r["repo_id"],
                    file_id=r["file_id"],
                    entity_id=r["entity_id"],
                    start_line=r["start_line"],
                    end_line=r["end_line"],
                    label=r["label"],
                    content=r["content"],
                    tokens_json=r["tokens_json"],
                )
                for r in rows
            ]


class ConversationDAL:
    def __init__(self, db: Database) -> None:
        self.db = db

    def get_or_create_conversation(self, conversation_id: str, repo_id: str) -> ConversationRecord:
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO repositories (id, name, root_path)
                VALUES (?, ?, ?)
                """,
                (repo_id, repo_id, f"./{repo_id}"),
            )
            conn.execute(
                """
                INSERT INTO conversations (id, repo_id)
                VALUES (?, ?)
                ON CONFLICT(id) DO UPDATE SET updated_at = CURRENT_TIMESTAMP
                """,
                (conversation_id, repo_id),
            )
            row = conn.execute(
                "SELECT id, repo_id, created_at, updated_at FROM conversations WHERE id = ?",
                (conversation_id,),
            ).fetchone()
            return ConversationRecord(
                id=row["id"],
                repo_id=row["repo_id"],
                created_at=str(row["created_at"]),
                updated_at=str(row["updated_at"]),
            )

    def add_turn(self, turn: ConversationTurnRecord) -> int:
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO conversation_turns (conversation_id, turn_index, question, answer, mode, sources_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    turn.conversation_id,
                    turn.turn_index,
                    turn.question,
                    turn.answer,
                    turn.mode,
                    turn.sources_json,
                ),
            )
            conn.execute(
                "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (turn.conversation_id,),
            )
            return cursor.lastrowid or 0

    def get_turns(self, conversation_id: str, limit: int = 50) -> list[ConversationTurnRecord]:
        with self.db.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, conversation_id, turn_index, question, answer, mode, sources_json, created_at
                FROM conversation_turns
                WHERE conversation_id = ?
                ORDER BY turn_index ASC
                LIMIT ?
                """,
                (conversation_id, limit),
            ).fetchall()
            return [
                ConversationTurnRecord(
                    id=r["id"],
                    conversation_id=r["conversation_id"],
                    turn_index=r["turn_index"],
                    question=r["question"],
                    answer=r["answer"],
                    mode=r["mode"],
                    sources_json=r["sources_json"],
                    created_at=str(r["created_at"]),
                )
                for r in rows
            ]

    def reset_conversation(self, conversation_id: str) -> None:
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM conversation_turns WHERE conversation_id = ?", (conversation_id,))
            conn.execute("UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (conversation_id,))

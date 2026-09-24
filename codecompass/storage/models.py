from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class RepositoryRecord:
    id: str
    name: str
    root_path: str
    created_at: str | None = None
    last_scanned_at: str | None = None


@dataclass(slots=True)
class FileRecord:
    id: str
    repo_id: str
    path: str
    language: str
    size_bytes: int
    lines: int
    content_hash: str
    is_test: bool = False
    last_scanned_at: str | None = None


@dataclass(slots=True)
class EntityRecord:
    id: str
    repo_id: str
    file_id: str
    kind: str  # Class, Function, Method, API
    name: str
    signature: str | None = None
    start_line: int = 1
    end_line: int = 1
    start_byte: int | None = None
    end_byte: int | None = None
    docstring: str | None = None
    scope: str | None = None
    metadata_json: str | None = None


@dataclass(slots=True)
class RelationshipRecord:
    id: int | None
    repo_id: str
    source_id: str
    target_id: str
    type: str  # CONTAINS, IMPORTS, CALLS, EXTENDS, TESTS
    metadata_json: str | None = None


@dataclass(slots=True)
class SearchChunkRecord:
    id: str
    repo_id: str
    file_id: str
    entity_id: str | None
    start_line: int
    end_line: int
    label: str
    content: str
    tokens_json: str


@dataclass(slots=True)
class ConversationRecord:
    id: str
    repo_id: str
    created_at: str | None = None
    updated_at: str | None = None


@dataclass(slots=True)
class ConversationTurnRecord:
    id: int | None = None
    conversation_id: str = ""
    turn_index: int = 0
    question: str = ""
    answer: str = ""
    mode: str = "local"
    sources_json: str | None = None
    created_at: str | None = None


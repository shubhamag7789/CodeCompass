from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RawEntity:
    id: str
    kind: str  # Class, Function, Method, API
    name: str
    qualified_name: str
    start_line: int
    end_line: int
    start_byte: int
    end_byte: int
    docstring: str | None = None
    scope: str | None = None
    signature: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        rel_path: str,
        kind: str,
        name: str,
        start_line: int,
        end_line: int,
        start_byte: int,
        end_byte: int,
        scope: str | None = None,
        docstring: str | None = None,
        signature: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RawEntity:
        qualified = f"{scope}.{name}" if scope else name
        digest = hashlib.sha1(f"{kind}:{rel_path}:{qualified}:{start_line}".encode("utf-8")).hexdigest()[:12]
        entity_id = f"{kind.lower()}:{digest}"
        return cls(
            id=entity_id,
            kind=kind,
            name=name,
            qualified_name=qualified,
            start_line=start_line,
            end_line=end_line,
            start_byte=start_byte,
            end_byte=end_byte,
            docstring=docstring,
            scope=scope,
            signature=signature,
            metadata=metadata or {},
        )


@dataclass(slots=True)
class RawImport:
    module: str
    alias: str | None = None
    is_relative: bool = False
    relative_level: int = 0
    symbols: list[tuple[str, str | None]] = field(default_factory=list)  # (symbol_name, alias)
    line: int = 1


@dataclass(slots=True)
class RawCall:
    caller_scope: str  # Entity ID or scope name of the enclosing function/method
    callee_name: str  # Simple function/method name (e.g. "authenticate")
    callee_owner: str | None = None  # Base object if method call (e.g. "auth_service", "self")
    line: int = 1


@dataclass(slots=True)
class RawInheritance:
    class_name: str
    base_names: list[str] = field(default_factory=list)
    line: int = 1


@dataclass(slots=True)
class FileParseResult:
    rel_path: str
    language: str
    entities: list[RawEntity] = field(default_factory=list)
    imports: list[RawImport] = field(default_factory=list)
    calls: list[RawCall] = field(default_factory=list)
    inheritances: list[RawInheritance] = field(default_factory=list)


from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from codecompass.extractor.models import FileParseResult, RawEntity
from codecompass.storage.models import EntityRecord, RelationshipRecord


class ScopedResolver:
    """Resolves intra-repository imports, inheritance, and call sites to exact symbols."""

    def __init__(self, repo_id: str, parsed_files: list[FileParseResult]) -> None:
        self.repo_id = repo_id
        self.parsed_files = parsed_files

        # Lookups
        self.files_by_rel_path: dict[str, FileParseResult] = {f.rel_path: f for f in parsed_files}
        self.file_entities: dict[str, dict[str, RawEntity]] = defaultdict(dict)
        self.file_classes: dict[str, dict[str, RawEntity]] = defaultdict(dict)
        self.module_to_file: dict[str, str] = {}

        self._build_indices()

    def _build_indices(self) -> None:
        for parsed in self.parsed_files:
            rel = parsed.rel_path.replace("\\", "/")
            stem = rel.rsplit(".", 1)[0]

            # Python module keys
            self.module_to_file[stem.replace("/", ".")] = rel
            self.module_to_file[Path(rel).stem] = rel
            if Path(rel).name == "__init__.py":
                parent_mod = str(Path(rel).parent).replace("\\", ".").replace("/", ".")
                self.module_to_file[parent_mod] = rel

            # JS/TS module keys
            self.module_to_file[stem] = rel
            if Path(rel).name in {"index.ts", "index.js", "index.tsx"}:
                self.module_to_file[str(Path(rel).parent).replace("\\", "/")] = rel

            for entity in parsed.entities:
                self.file_entities[parsed.rel_path][entity.name] = entity
                self.file_entities[parsed.rel_path][entity.qualified_name] = entity
                if entity.kind == "Class":
                    self.file_classes[parsed.rel_path][entity.name] = entity

    def resolve_relationships(self) -> list[RelationshipRecord]:
        relationships: list[RelationshipRecord] = []
        seen: set[tuple[str, str, str]] = set()

        def add_rel(source_id: str, rel_type: str, target_id: str, meta: dict[str, Any] | None = None) -> None:
            key = (source_id, rel_type, target_id)
            if key in seen or source_id == target_id:
                return
            seen.add(key)
            meta_json = str(meta) if meta else None
            relationships.append(
                RelationshipRecord(
                    id=None,
                    repo_id=self.repo_id,
                    source_id=source_id,
                    target_id=target_id,
                    type=rel_type,
                    metadata_json=meta_json,
                )
            )

        for parsed in self.parsed_files:
            file_id = f"file:{parsed.rel_path}"

            # 1. CONTAINS relationships: File -> Entities
            for entity in parsed.entities:
                if entity.scope:
                    # Method contained in Class
                    parent_entity = self.file_entities[parsed.rel_path].get(entity.scope)
                    if parent_entity:
                        add_rel(parent_entity.id, "CONTAINS", entity.id)
                    else:
                        add_rel(file_id, "CONTAINS", entity.id)
                else:
                    add_rel(file_id, "CONTAINS", entity.id)

            # 2. IMPORTS relationships: File -> File or File -> External
            for imp in parsed.imports:
                target_file = self.resolve_import_path(parsed.rel_path, imp.module, imp.is_relative, imp.relative_level)
                if target_file and target_file in self.files_by_rel_path:
                    add_rel(file_id, "IMPORTS", f"file:{target_file}", {"module": imp.module})
                else:
                    external_name = self._external_pkg_name(imp.module)
                    if external_name:
                        add_rel(file_id, "IMPORTS", f"external:{external_name}", {"package": external_name})

            # 3. EXTENDS relationships: Class -> Base Class
            for inh in parsed.inheritances:
                sub_entity = self.file_classes[parsed.rel_path].get(inh.class_name)
                if not sub_entity:
                    continue
                for base_name in inh.base_names:
                    # Look locally first
                    base_entity = self.file_classes[parsed.rel_path].get(base_name)
                    if base_entity:
                        add_rel(sub_entity.id, "EXTENDS", base_entity.id)
                    else:
                        # Look through imports
                        target_entity = self._find_imported_symbol(parsed.rel_path, base_name)
                        if target_entity:
                            add_rel(sub_entity.id, "EXTENDS", target_entity.id)

            # 4. SCOPED CALLS relationships: Caller -> Callee
            for call in parsed.calls:
                caller_entity = self.file_entities[parsed.rel_path].get(call.caller_scope)
                source_id = caller_entity.id if caller_entity else file_id

                target_entity = self._resolve_call(parsed.rel_path, call.callee_name, call.callee_owner, call.caller_scope)
                if target_entity:
                    add_rel(source_id, "CALLS", target_entity.id, {"call": call.callee_name, "line": call.line})

        # 5. Link TESTS relationships
        self._link_tests(relationships, add_rel)

        return relationships

    def resolve_import_path(self, current_file: str, module_str: str, is_relative: bool, relative_level: int) -> str | None:
        if is_relative:
            curr_dir = Path(current_file).parent
            # Ascend based on relative level
            ascend_steps = max(0, relative_level - 1)
            target_dir = curr_dir
            for _ in range(ascend_steps):
                target_dir = target_dir.parent

            clean_mod = module_str.lstrip("./").lstrip("../").replace(".", "/")
            candidate_base = (target_dir / clean_mod).as_posix() if clean_mod else target_dir.as_posix()

            for ext in (".py", ".ts", ".tsx", ".js", ".jsx"):
                c1 = f"{candidate_base}{ext}"
                if c1 in self.files_by_rel_path:
                    return c1
                c2 = f"{candidate_base}/index{ext}"
                if c2 in self.files_by_rel_path:
                    return c2
                c3 = f"{candidate_base}/__init__{ext}"
                if c3 in self.files_by_rel_path:
                    return c3

            if candidate_base in self.files_by_rel_path:
                return candidate_base
            return None

        # Absolute / project-relative import
        normalized = module_str.replace("\\", "/").replace(".", "/")
        if normalized in self.module_to_file:
            return self.module_to_file[normalized]

        for ext in (".py", ".ts", ".tsx", ".js", ".jsx"):
            c = f"{normalized}{ext}"
            if c in self.files_by_rel_path:
                return c

        return self.module_to_file.get(module_str)

    def _resolve_call(self, current_file: str, callee_name: str, callee_owner: str | None, caller_scope: str) -> RawEntity | None:
        # Ignore common language built-ins
        if callee_name in {"print", "len", "range", "str", "int", "dict", "list", "set", "super", "console", "log", "fetch", "require"}:
            return None

        # 1. Check if callee is a method on 'self' or 'this' in the current class
        if callee_owner in {"self", "this", "cls"} and "." in caller_scope:
            class_name = caller_scope.split(".")[0]
            qual_name = f"{class_name}.{callee_name}"
            if qual_name in self.file_entities[current_file]:
                return self.file_entities[current_file][qual_name]

        # 2. Check local scope in current file
        if callee_name in self.file_entities[current_file]:
            return self.file_entities[current_file][callee_name]

        # 3. Check if callee was explicitly imported
        imported_target = self._find_imported_symbol(current_file, callee_name)
        if imported_target:
            return imported_target

        # 4. Check if owner was imported (e.g. auth_service.login())
        if callee_owner:
            owner_entity = self._find_imported_symbol(current_file, callee_owner)
            if owner_entity:
                target_file = owner_entity.metadata.get("rel_path")
                # Look for method in that owner's class
                if target_file and target_file in self.file_entities:
                    qual = f"{owner_entity.name}.{callee_name}"
                    if qual in self.file_entities[target_file]:
                        return self.file_entities[target_file][qual]

        # Not found through scope or imports: return None (DO NOT falsely link to random symbols!)
        return None

    def _find_imported_symbol(self, current_file: str, symbol_name: str) -> RawEntity | None:
        parsed = self.files_by_rel_path.get(current_file)
        if not parsed:
            return None

        for imp in parsed.imports:
            # Check named symbols: from x import symbol_name
            for sym, alias in imp.symbols:
                target_sym = alias or sym
                if target_sym == symbol_name:
                    target_file = self.resolve_import_path(current_file, imp.module, imp.is_relative, imp.relative_level)
                    if target_file and target_file in self.file_entities:
                        if sym in self.file_entities[target_file]:
                            return self.file_entities[target_file][sym]

            # Check module alias: import x as symbol_name
            if imp.alias == symbol_name or imp.module.split(".")[-1] == symbol_name:
                target_file = self.resolve_import_path(current_file, imp.module, imp.is_relative, imp.relative_level)
                if target_file and target_file in self.file_entities:
                    # Find matching entity in that module
                    if symbol_name in self.file_entities[target_file]:
                        return self.file_entities[target_file][symbol_name]

        return None

    def _link_tests(self, relationships: list[RelationshipRecord], add_rel: Any) -> None:
        module_to_file_id = {Path(f.rel_path).stem.lower(): f"file:{f.rel_path}" for f in self.parsed_files}
        for parsed in self.parsed_files:
            file_id = f"file:{parsed.rel_path}"
            lowered = parsed.rel_path.lower()
            if not ("test" in lowered or "spec" in lowered):
                continue
            for imp in parsed.imports:
                candidate = Path(imp.module).stem.lower()
                if candidate in module_to_file_id and module_to_file_id[candidate] != file_id:
                    add_rel(file_id, "TESTS", module_to_file_id[candidate])

    @staticmethod
    def _external_pkg_name(module_str: str) -> str:
        if not module_str or module_str.startswith((".", "/")):
            return ""
        if module_str.startswith("@"):
            parts = module_str.split("/")
            return "/".join(parts[:2])
        return module_str.split(".")[0].split("/")[0]


def to_entity_records(repo_id: str, parsed_files: list[FileParseResult]) -> list[EntityRecord]:
    """Converts RawEntity models to EntityRecord database models."""
    records: list[EntityRecord] = []
    for parsed in parsed_files:
        file_id = f"file:{parsed.rel_path}"
        for e in parsed.entities:
            records.append(
                EntityRecord(
                    id=e.id,
                    repo_id=repo_id,
                    file_id=file_id,
                    kind=e.kind,
                    name=e.name,
                    signature=e.signature,
                    start_line=e.start_line,
                    end_line=e.end_line,
                    start_byte=e.start_byte,
                    end_byte=e.end_byte,
                    docstring=e.docstring,
                    scope=e.scope,
                    metadata_json=str(e.metadata) if e.metadata else None,
                )
            )
    return records


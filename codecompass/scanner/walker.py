from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Counter

from codecompass.config import (
    DEFAULT_IGNORED_DIRS,
    SUPPORTED_EXTENSIONS,
    TEST_DIR_PREFIXES,
    TEST_FILE_PREFIXES,
    TEST_FILE_SUFFIXES,
)
from codecompass.scanner.ignore import IgnoreRuleSet
from codecompass.storage.models import FileRecord, RepositoryRecord


@dataclass(slots=True)
class ChangeSet:
    added: list[FileRecord] = field(default_factory=list)
    modified: list[FileRecord] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)  # relative paths
    unchanged: list[FileRecord] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.modified or self.deleted)


@dataclass(slots=True)
class ScanResult:
    repository: RepositoryRecord
    files: list[FileRecord]
    stats: dict[str, int]
    language_counts: dict[str, int]


def is_test_file(rel_path: str) -> bool:
    """Classifies whether a relative path represents a test file."""
    normalized = rel_path.lower().replace("\\", "/")
    filename = Path(normalized).name

    for prefix in TEST_DIR_PREFIXES:
        if normalized.startswith(prefix) or f"/{prefix}" in normalized:
            return True

    for prefix in TEST_FILE_PREFIXES:
        if filename.startswith(prefix):
            return True

    for suffix in TEST_FILE_SUFFIXES:
        if filename.endswith(suffix):
            return True

    return False


def compute_file_hash(content_bytes: bytes) -> str:
    """Computes SHA-256 checksum of raw file bytes."""
    return hashlib.sha256(content_bytes).hexdigest()


def scan_file(root: Path, file_path: Path, repo_id: str) -> FileRecord | None:
    """Reads a file, computes its metrics and content hash, and returns a FileRecord."""
    suffix = file_path.suffix.lower()
    language = SUPPORTED_EXTENSIONS.get(suffix)
    if not language:
        return None

    try:
        raw_bytes = file_path.read_bytes()
    except (OSError, PermissionError):
        return None

    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = raw_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            return None

    rel_path = file_path.relative_to(root).as_posix()
    lines_count = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
    content_hash = compute_file_hash(raw_bytes)
    file_id = f"file:{rel_path}"

    return FileRecord(
        id=file_id,
        repo_id=repo_id,
        path=rel_path,
        language=language,
        size_bytes=len(raw_bytes),
        lines=lines_count,
        content_hash=content_hash,
        is_test=is_test_file(rel_path),
    )


def walk_repository(root_path: str | Path, repo_id: str | None = None) -> ScanResult:
    """Walks the directory tree, applying ignore rules and collecting FileRecords."""
    root = Path(root_path).resolve()
    if not root.exists():
        raise FileNotFoundError(f"Repository directory does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Target is not a directory: {root}")

    assigned_repo_id = repo_id or f"repo:{root.name or 'root'}"
    ignore_set = IgnoreRuleSet(root)

    records: list[FileRecord] = []
    lang_counter: Counter[str] = Counter()
    total_bytes = 0
    total_lines = 0

    for dirpath_str, dirnames, filenames in os.walk(root, topdown=True):
        current_dir = Path(dirpath_str)

        # Prune ignored directories in-place to avoid descending into them
        pruned_dirnames = []
        for d in dirnames:
            sub_dir = current_dir / d
            if d in DEFAULT_IGNORED_DIRS or ignore_set.is_ignored(sub_dir, is_dir=True):
                continue
            pruned_dirnames.append(d)
        dirnames[:] = pruned_dirnames

        # Check for nested .gitignore files and register them
        if ".gitignore" in filenames:
            ignore_set.load_gitignore_file(current_dir / ".gitignore")

        for f in filenames:
            file_path = current_dir / f
            if ignore_set.is_ignored(file_path, is_dir=False):
                continue

            record = scan_file(root, file_path, assigned_repo_id)
            if record:
                records.append(record)
                lang_counter[record.language] += 1
                total_bytes += record.size_bytes
                total_lines += record.lines

    records.sort(key=lambda r: r.path)
    repo_record = RepositoryRecord(
        id=assigned_repo_id,
        name=root.name or "repository",
        root_path=str(root),
    )

    stats = {
        "total_files": len(records),
        "total_lines": total_lines,
        "total_bytes": total_bytes,
        "test_files": sum(1 for r in records if r.is_test),
    }

    return ScanResult(
        repository=repo_record,
        files=records,
        stats=stats,
        language_counts=dict(lang_counter),
    )


def detect_changes(cached_files: list[FileRecord], current_files: list[FileRecord]) -> ChangeSet:
    """Compares cached records with current scan records to find added, modified, deleted, and unchanged files."""
    cached_map = {f.path: f for f in cached_files}
    current_map = {f.path: f for f in current_files}

    changes = ChangeSet()

    for path, current in current_map.items():
        if path not in cached_map:
            changes.added.append(current)
        elif cached_map[path].content_hash != current.content_hash:
            changes.modified.append(current)
        else:
            changes.unchanged.append(current)

    for path in cached_map:
        if path not in current_map:
            changes.deleted.append(path)

    return changes


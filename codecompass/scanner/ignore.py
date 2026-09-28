from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import NamedTuple

from codecompass.config import DEFAULT_IGNORED_DIRS


class PatternRule(NamedTuple):
    pattern: str
    is_dir_only: bool
    is_negation: bool
    base_rel: str  # directory where the .gitignore is located, relative to repo root


class IgnoreRuleSet:
    """Evaluates ignore patterns against paths, respecting .gitignore rules and default exclusions."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.rules: list[PatternRule] = []
        self._load_root_gitignore()

    def _load_root_gitignore(self) -> None:
        root_gi = self.root / ".gitignore"
        if root_gi.exists():
            self.load_gitignore_file(root_gi)

    def load_gitignore_file(self, gitignore_path: Path) -> None:
        try:
            content = gitignore_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return

        base_rel = gitignore_path.parent.relative_to(self.root).as_posix()
        if base_rel == ".":
            base_rel = ""

        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            is_negation = line.startswith("!")
            if is_negation:
                line = line[1:].strip()

            is_dir_only = line.endswith("/")
            if is_dir_only:
                line = line[:-1]

            if line.startswith("/"):
                line = line[1:]

            self.rules.append(
                PatternRule(
                    pattern=line,
                    is_dir_only=is_dir_only,
                    is_negation=is_negation,
                    base_rel=base_rel,
                )
            )

    def is_ignored(self, path: Path, is_dir: bool = False) -> bool:
        """Determines if a path should be ignored."""
        try:
            rel = path.relative_to(self.root).as_posix()
        except ValueError:
            return True

        # Check default ignored directory names in any part of path
        parts = rel.split("/")
        for part in (parts if is_dir else parts[:-1]):
            if part in DEFAULT_IGNORED_DIRS:
                return True

        if is_dir and parts[-1] in DEFAULT_IGNORED_DIRS:
            return True

        # Evaluate rules in order: later rules override earlier ones
        ignored = False
        for rule in self.rules:
            if rule.is_dir_only and not is_dir:
                continue

            target_rel = rel
            if rule.base_rel:
                if not rel.startswith(rule.base_rel + "/") and rel != rule.base_rel:
                    continue
                target_rel = rel[len(rule.base_rel) :].lstrip("/")

            matches = self._match_pattern(rule.pattern, target_rel, is_dir)
            if matches:
                ignored = not rule.is_negation

        return ignored

    @staticmethod
    def _match_pattern(pattern: str, rel_path: str, is_dir: bool) -> bool:
        # Simple exact part match or glob
        if "/" not in pattern:
            # Matches against basename or any path segment
            parts = rel_path.split("/")
            return any(fnmatch.fnmatchcase(p, pattern) for p in parts)

        # Pattern contains a slash: match against relative path
        if fnmatch.fnmatchcase(rel_path, pattern):
            return True
        if fnmatch.fnmatchcase(rel_path, f"*/{pattern}"):
            return True
        return False


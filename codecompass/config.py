from __future__ import annotations

from pathlib import Path
from typing import Final

# Supported file extensions for initial phase
SUPPORTED_EXTENSIONS: Final[dict[str, str]] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
}

# Directories always excluded from scanning
DEFAULT_IGNORED_DIRS: Final[set[str]] = {
    ".git",
    ".hg",
    ".svn",
    ".codecompass",
    ".repomind",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "dist",
    "build",
    "out",
    "target",
    ".next",
    ".nuxt",
    "coverage",
    ".idea",
    ".vscode",
}

# Test file patterns
TEST_DIR_PREFIXES: Final[tuple[str, ...]] = ("test/", "tests/", "__tests__/")
TEST_FILE_PREFIXES: Final[tuple[str, ...]] = ("test_", "spec_")
TEST_FILE_SUFFIXES: Final[tuple[str, ...]] = (
    "_test.py",
    ".test.js",
    ".spec.js",
    ".test.jsx",
    ".spec.jsx",
    ".test.ts",
    ".spec.ts",
    ".test.tsx",
    ".spec.tsx",
)

# Common entrypoint file names
ENTRYPOINT_NAMES: Final[set[str]] = {
    "main.py",
    "app.py",
    "server.py",
    "manage.py",
    "index.js",
    "index.ts",
    "server.js",
    "server.ts",
    "app.js",
    "app.ts",
    "package.json",
    "pyproject.toml",
}

# Database defaults
DEFAULT_DB_DIR: Final[str] = ".codecompass"
DEFAULT_DB_NAME: Final[str] = "codecompass.db"

# SQLite WAL pragmas for high performance and concurrency
SQLITE_PRAGMAS: Final[list[str]] = [
    "PRAGMA journal_mode = WAL;",
    "PRAGMA synchronous = NORMAL;",
    "PRAGMA foreign_keys = ON;",
    "PRAGMA busy_timeout = 5000;",
    "PRAGMA cache_size = -64000;",  # 64MB memory cache
]


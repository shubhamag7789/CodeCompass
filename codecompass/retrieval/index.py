"""Zero-dependency lexical (BM25) code search over a repository for CodeCompass.

Provides in-process BM25 index with identifier-aware tokenization and structural boosts.
Feeds grounded context to the assistant and works fully offline.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from codecompass.config import DEFAULT_IGNORED_DIRS as IGNORED_DIRS, SUPPORTED_EXTENSIONS

# Chunk repositories into overlapping line windows so a match keeps its neighbours.
CHUNK_LINES = 50
CHUNK_STEP = 35
MAX_CHUNKS = 4000
MAX_CHUNK_CHARS = 4000

# BM25 tuning constants (standard defaults).
_BM25_K1 = 1.5
_BM25_B = 0.75

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
_CAMEL_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|[0-9]+")
_SYMBOL_RE = re.compile(r"^\s*(?:export\s+)?(?:public\s+|private\s+|protected\s+)?(?:async\s+)?(?:def|class|function|func|interface|struct)\s+([A-Za-z_$][\w$]*)")

_STOPWORDS = {
    "the", "and", "for", "with", "from", "this", "that", "self", "return",
    "import", "const", "let", "var", "def", "class", "function", "true", "false",
    "null", "none", "not", "are", "was", "you", "your", "how", "does", "where",
    "what", "which", "who", "when", "why", "into", "out", "get", "set",
}


@dataclass
class Chunk:
    id: str
    file: str
    language: str
    start_line: int
    end_line: int
    label: str
    text: str
    tokens: list[str] = field(default_factory=list)

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "file": self.file,
            "language": self.language,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "label": self.label,
            "text": self.text,
        }


def tokenize(text: str) -> list[str]:
    """Split code/prose into search terms, breaking identifiers on camelCase and _."""
    tokens: list[str] = []
    for raw in _TOKEN_RE.findall(text):
        low = raw.lower()
        if len(low) >= 2 and low not in _STOPWORDS:
            tokens.append(low)
        parts = _CAMEL_RE.findall(raw)
        for part in parts:
            part = part.lower()
            if len(part) >= 2 and part != low and part not in _STOPWORDS:
                tokens.append(part)
    return tokens


def _label_for(lines: list[str], fallback: str) -> str:
    for line in lines:
        match = _SYMBOL_RE.match(line)
        if match:
            return match.group(1)
    return fallback


def build_index(root: str | Path) -> dict[str, Any]:
    """Read the repository and build a persistable chunk index."""
    root = Path(root).resolve()
    chunks: list[dict[str, Any]] = []
    truncated = False

    for path in _iter_source_files(root):
        if len(chunks) >= MAX_CHUNKS:
            truncated = True
            break
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            try:
                text = path.read_text(encoding="utf-8-sig")
            except (UnicodeDecodeError, OSError):
                continue

        rel_path = path.relative_to(root).as_posix()
        language = SUPPORTED_EXTENSIONS.get(path.suffix, "Text")
        lines = text.splitlines()
        if not lines:
            continue

        for start in range(0, len(lines), CHUNK_STEP):
            if len(chunks) >= MAX_CHUNKS:
                truncated = True
                break
            window = lines[start : start + CHUNK_LINES]
            body = "\n".join(window).strip("\n")
            if not body.strip():
                continue
            end = start + len(window)
            chunk_text = body[:MAX_CHUNK_CHARS]
            chunks.append(
                {
                    "id": f"{rel_path}#{start + 1}",
                    "file": rel_path,
                    "language": language,
                    "start_line": start + 1,
                    "end_line": end,
                    "label": _label_for(window, Path(rel_path).name),
                    "text": chunk_text,
                }
            )

    return {"schema_version": "0.1.0", "chunk_count": len(chunks), "truncated": truncated, "chunks": chunks}


class SearchIndex:
    """In-memory BM25 search over the chunks produced by :func:`build_index`."""

    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks
        self._doc_freq: dict[str, int] = {}
        total_len = 0
        for chunk in chunks:
            total_len += len(chunk.tokens)
            for term in set(chunk.tokens):
                self._doc_freq[term] = self._doc_freq.get(term, 0) + 1
        self._n = len(chunks)
        self._avg_len = (total_len / self._n) if self._n else 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SearchIndex":
        chunks = []
        for item in data.get("chunks", []):
            chunk = Chunk(
                id=item["id"],
                file=item["file"],
                language=item.get("language", "Text"),
                start_line=item.get("start_line", 1),
                end_line=item.get("end_line", 1),
                label=item.get("label", item["file"]),
                text=item.get("text", ""),
            )
            chunk.tokens = tokenize(chunk.text)
            chunks.append(chunk)
        return cls(chunks)

    def _idf(self, term: str) -> float:
        df = self._doc_freq.get(term, 0)
        if df == 0:
            return 0.0
        return math.log(1 + (self._n - df + 0.5) / (df + 0.5))

    def search(self, query: str, k: int = 6) -> list[dict[str, Any]]:
        if not self.chunks:
            return []
        query_terms = tokenize(query)
        if not query_terms:
            return []
        query_set = set(query_terms)

        scored: list[tuple[float, Chunk]] = []
        for chunk in self.chunks:
            counts: dict[str, int] = {}
            for term in chunk.tokens:
                counts[term] = counts.get(term, 0) + 1
            length = len(chunk.tokens) or 1

            score = 0.0
            for term in query_set:
                tf = counts.get(term, 0)
                if not tf:
                    continue
                idf = self._idf(term)
                denom = tf + _BM25_K1 * (1 - _BM25_B + _BM25_B * length / (self._avg_len or 1))
                score += idf * (tf * (_BM25_K1 + 1)) / denom

            if score <= 0:
                continue

            # Structural boosts: a query term that names the file or symbol is a strong signal.
            path_terms = set(tokenize(chunk.file))
            label_terms = set(tokenize(chunk.label))
            score += 2.5 * len(query_set & label_terms)
            score += 1.5 * len(query_set & path_terms)
            scored.append((score, chunk))

        scored.sort(key=lambda item: item[0], reverse=True)
        results = []
        for score, chunk in scored[:k]:
            result = chunk.public()
            result["score"] = round(score, 4)
            results.append(result)
        return results


def write_index(index: dict[str, Any], output_path: str | Path) -> Path:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(index), encoding="utf-8")
    return destination


def default_index_path(analysis_path: str | Path) -> Path:
    analysis_path = Path(analysis_path)
    return analysis_path.with_name("index.json")


def load_index(index_path: str | Path) -> SearchIndex | None:
    path = Path(index_path)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return SearchIndex.from_dict(data)


def _iter_source_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORED_DIRS for part in path.relative_to(root).parts):
            continue
        if path.suffix in SUPPORTED_EXTENSIONS:
            yield path


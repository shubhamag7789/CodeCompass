from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any, Final

from codecompass.retrieval.tokenizer import tokenize
from codecompass.storage.database import Database
from codecompass.storage.models import SearchChunkRecord
from codecompass.storage.repositories import SearchChunkDAL

BM25_K1: Final[float] = 1.5
BM25_B: Final[float] = 0.75
BOOST_LABEL: Final[float] = 2.5
BOOST_PATH: Final[float] = 1.5


@dataclass(slots=True)
class SearchResult:
    id: str
    file: str
    label: str
    start_line: int
    end_line: int
    score: float
    content: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "file": self.file,
            "label": self.label,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "score": round(self.score, 4),
            "content": self.content,
        }


class BM25Index:
    """In-memory BM25 lexical search index over AST semantic chunks."""

    def __init__(self, chunks: list[SearchChunkRecord]) -> None:
        self.chunks = chunks
        self.parsed_tokens: list[list[str]] = []
        self._doc_freq: dict[str, int] = {}
        total_len = 0

        for chunk in chunks:
            try:
                tokens = json.loads(chunk.tokens_json)
            except Exception:
                tokens = tokenize(chunk.content)
            self.parsed_tokens.append(tokens)
            total_len += len(tokens)
            for term in set(tokens):
                self._doc_freq[term] = self._doc_freq.get(term, 0) + 1

        self._n = len(chunks)
        self._avg_len = (total_len / self._n) if self._n > 0 else 1.0

    @classmethod
    def from_database(cls, db: Database, repo_id: str) -> BM25Index:
        dal = SearchChunkDAL(db)
        chunks = dal.get_chunks_for_repo(repo_id)
        return cls(chunks)

    def _idf(self, term: str) -> float:
        df = self._doc_freq.get(term, 0)
        if df == 0:
            return 0.0
        return math.log(1 + (self._n - df + 0.5) / (df + 0.5))

    def search(self, query: str, k: int = 6) -> list[SearchResult]:
        if not self.chunks:
            return []

        query_terms = tokenize(query)
        if not query_terms:
            return []

        query_set = set(query_terms)
        scored: list[tuple[float, SearchChunkRecord]] = []

        for idx, chunk in enumerate(self.chunks):
            tokens = self.parsed_tokens[idx]
            if not tokens:
                continue

            counts: dict[str, int] = {}
            for t in tokens:
                counts[t] = counts.get(t, 0) + 1

            length = len(tokens) or 1
            score = 0.0

            for term in query_set:
                tf = counts.get(term, 0)
                if not tf:
                    continue
                idf = self._idf(term)
                denom = tf + BM25_K1 * (1 - BM25_B + BM25_B * length / self._avg_len)
                score += idf * (tf * (BM25_K1 + 1)) / denom

            if score <= 0.0:
                continue

            # Structural boosting: query terms present in symbol label or file path
            file_path = chunk.file_id.removeprefix("file:")
            path_terms = set(tokenize(file_path))
            label_terms = set(tokenize(chunk.label))

            score += BOOST_LABEL * len(query_set & label_terms)
            score += BOOST_PATH * len(query_set & path_terms)

            scored.append((score, chunk))

        scored.sort(key=lambda s: s[0], reverse=True)

        results: list[SearchResult] = []
        for score, chunk in scored[:k]:
            results.append(
                SearchResult(
                    id=chunk.id,
                    file=chunk.file_id.removeprefix("file:"),
                    label=chunk.label,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    score=score,
                    content=chunk.content,
                )
            )

        return results


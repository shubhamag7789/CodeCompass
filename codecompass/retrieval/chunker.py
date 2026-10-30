from __future__ import annotations

import json
from pathlib import Path
from typing import Final

from codecompass.extractor.models import RawEntity
from codecompass.retrieval.tokenizer import tokenize
from codecompass.storage.models import SearchChunkRecord

MAX_CHUNK_CHARS: Final[int] = 3000
FALLBACK_CHUNK_LINES: Final[int] = 50
FALLBACK_CHUNK_STEP: Final[int] = 35


def create_semantic_chunks(
    repo_id: str,
    file_id: str,
    rel_path: str,
    code_text: str,
    entities: list[RawEntity],
) -> list[SearchChunkRecord]:
    """Generates AST-aware search chunks aligned to exact function and class boundaries."""
    lines = code_text.splitlines()
    if not lines:
        return []

    chunks: list[SearchChunkRecord] = []
    covered_lines: set[int] = set()

    # Sort entities by start_line
    sorted_entities = sorted(entities, key=lambda e: (e.start_line, -e.end_line))

    # 1. Create chunks for discrete entities (Functions, Methods, standalone Classes)
    for entity in sorted_entities:
        if entity.kind not in {"Function", "Method", "Class"}:
            continue

        start_idx = max(0, entity.start_line - 1)
        end_idx = min(len(lines), entity.end_line)

        # For large classes, don't duplicate all methods into the class chunk; cap class header
        if entity.kind == "Class" and (end_idx - start_idx) > 25:
            header_end = min(start_idx + 18, len(lines))
            chunk_lines = lines[start_idx:header_end]
            label = f"class {entity.name}"
            chunk_end_line = start_idx + len(chunk_lines)
        else:
            chunk_lines = lines[start_idx:end_idx]
            label = f"{entity.qualified_name} ({entity.kind})"
            chunk_end_line = end_idx

        content = "\n".join(chunk_lines).strip()
        if not content:
            continue

        if len(content) > MAX_CHUNK_CHARS:
            content = content[:MAX_CHUNK_CHARS]

        tokens = tokenize(content)
        chunk_id = f"{file_id}#{entity.id}#{entity.start_line}"

        chunks.append(
            SearchChunkRecord(
                id=chunk_id,
                repo_id=repo_id,
                file_id=file_id,
                entity_id=entity.id,
                start_line=entity.start_line,
                end_line=chunk_end_line,
                label=label,
                content=content,
                tokens_json=json.dumps(tokens),
            )
        )

        for l in range(entity.start_line, chunk_end_line + 1):
            covered_lines.add(l)

    # 2. Chunk un-covered regions (e.g. module header, imports, top-level code)
    uncovered_start = None
    for line_no in range(1, len(lines) + 1):
        if line_no not in covered_lines:
            if uncovered_start is None:
                uncovered_start = line_no
        else:
            if uncovered_start is not None:
                _add_gap_chunk(
                    chunks, repo_id, file_id, rel_path, lines, uncovered_start, line_no - 1
                )
                uncovered_start = None

    if uncovered_start is not None:
        _add_gap_chunk(chunks, repo_id, file_id, rel_path, lines, uncovered_start, len(lines))

    # 3. Fallback if still empty
    if not chunks:
        chunks = _fallback_window_chunks(repo_id, file_id, rel_path, lines)

    return chunks


def _add_gap_chunk(
    chunks: list[SearchChunkRecord],
    repo_id: str,
    file_id: str,
    rel_path: str,
    lines: list[str],
    start_line: int,
    end_line: int,
) -> None:
    gap_lines = lines[start_line - 1 : end_line]
    if not gap_lines:
        return

    # If gap is large, slice with sliding window
    if len(gap_lines) >= FALLBACK_CHUNK_LINES:
        for s in range(0, len(gap_lines), FALLBACK_CHUNK_STEP):
            w = gap_lines[s : s + FALLBACK_CHUNK_LINES]
            c = "\n".join(w).strip()
            if not c:
                continue
            s_line = start_line + s
            e_line = s_line + len(w) - 1
            chunks.append(
                SearchChunkRecord(
                    id=f"{file_id}#gap#{s_line}",
                    repo_id=repo_id,
                    file_id=file_id,
                    entity_id=None,
                    start_line=s_line,
                    end_line=e_line,
                    label=Path(rel_path).name,
                    content=c[:MAX_CHUNK_CHARS],
                    tokens_json=json.dumps(tokenize(c[:MAX_CHUNK_CHARS])),
                )
            )
        return

    content = "\n".join(gap_lines).strip()
    if not content or len(content) < 15:
        return

    if len(content) > MAX_CHUNK_CHARS:
        content = content[:MAX_CHUNK_CHARS]

    tokens = tokenize(content)
    chunk_id = f"{file_id}#top#{start_line}"
    label = Path(rel_path).name

    chunks.append(
        SearchChunkRecord(
            id=chunk_id,
            repo_id=repo_id,
            file_id=file_id,
            entity_id=None,
            start_line=start_line,
            end_line=end_line,
            label=label,
            content=content,
            tokens_json=json.dumps(tokens),
        )
    )


def _fallback_window_chunks(
    repo_id: str,
    file_id: str,
    rel_path: str,
    lines: list[str],
) -> list[SearchChunkRecord]:
    chunks = []
    for start in range(0, len(lines), FALLBACK_CHUNK_STEP):
        window = lines[start : start + FALLBACK_CHUNK_LINES]
        content = "\n".join(window).strip()
        if not content:
            continue
        if len(content) > MAX_CHUNK_CHARS:
            content = content[:MAX_CHUNK_CHARS]

        start_line = start + 1
        end_line = start + len(window)
        tokens = tokenize(content)
        chunk_id = f"{file_id}#win#{start_line}"

        chunks.append(
            SearchChunkRecord(
                id=chunk_id,
                repo_id=repo_id,
                file_id=file_id,
                entity_id=None,
                start_line=start_line,
                end_line=end_line,
                label=Path(rel_path).name,
                content=content,
                tokens_json=json.dumps(tokens),
            )
        )
    return chunks

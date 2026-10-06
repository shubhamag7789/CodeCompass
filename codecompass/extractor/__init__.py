from __future__ import annotations

from pathlib import Path
from codecompass.extractor.languages.python import PythonExtractor
from codecompass.extractor.languages.typescript import TypeScriptExtractor
from codecompass.extractor.models import (
    FileParseResult,
    RawCall,
    RawEntity,
    RawImport,
    RawInheritance,
)
from codecompass.parser.engine import get_parser_engine


def extract_file(rel_path: str, code_bytes: bytes, language: str) -> FileParseResult:
    """Parses source code using Tree-sitter and extracts structured AST entities, imports, calls, and inheritances."""
    engine = get_parser_engine()

    # Determine specific language grammar for parser
    grammar_name = language
    if rel_path.endswith(".tsx"):
        grammar_name = "TSX"
    elif rel_path.endswith((".ts",)):
        grammar_name = "TypeScript"
    elif rel_path.endswith((".js", ".jsx")):
        grammar_name = "JavaScript"

    try:
        tree = engine.parse(code_bytes, grammar_name)
    except Exception as exc:
        # Graceful fallback: return empty result if parse completely fails
        return FileParseResult(rel_path=rel_path, language=language)

    if language == "Python":
        extractor = PythonExtractor(rel_path=rel_path, code_bytes=code_bytes)
        return extractor.extract(tree.root_node)
    elif language in {"TypeScript", "JavaScript"}:
        extractor = TypeScriptExtractor(rel_path=rel_path, code_bytes=code_bytes, is_tsx=rel_path.endswith(".tsx"))
        return extractor.extract(tree.root_node)

    return FileParseResult(rel_path=rel_path, language=language)


__all__ = [
    "extract_file",
    "FileParseResult",
    "RawEntity",
    "RawImport",
    "RawCall",
    "RawInheritance",
]


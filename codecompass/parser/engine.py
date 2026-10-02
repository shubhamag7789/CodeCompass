from __future__ import annotations

from typing import Final
import tree_sitter
import tree_sitter_javascript as ts_js
import tree_sitter_python as ts_py
import tree_sitter_typescript as ts_ts

# Load and wrap Language instances
PY_LANGUAGE: Final = tree_sitter.Language(ts_py.language())
JS_LANGUAGE: Final = tree_sitter.Language(ts_js.language())
TS_LANGUAGE: Final = tree_sitter.Language(ts_ts.language_typescript())
TSX_LANGUAGE: Final = tree_sitter.Language(ts_ts.language_tsx())

LANGUAGE_MAP: Final[dict[str, tree_sitter.Language]] = {
    "Python": PY_LANGUAGE,
    "JavaScript": JS_LANGUAGE,
    "TypeScript": TS_LANGUAGE,
    "TSX": TSX_LANGUAGE,
}

EXTENSION_MAP: Final[dict[str, str]] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TSX",
}


class ParserEngine:
    """Manages Tree-sitter Language instances and creates parsers for supported languages."""

    def __init__(self) -> None:
        self._parsers: dict[str, tree_sitter.Parser] = {
            lang_name: tree_sitter.Parser(lang) for lang_name, lang in LANGUAGE_MAP.items()
        }

    def get_language(self, language_name: str) -> tree_sitter.Language | None:
        return LANGUAGE_MAP.get(language_name)

    def detect_language(self, file_suffix: str) -> str | None:
        return EXTENSION_MAP.get(file_suffix.lower())

    def parse(self, code_bytes: bytes, language_name: str) -> tree_sitter.Tree:
        parser = self._parsers.get(language_name)
        if not parser:
            raise ValueError(f"Unsupported language for parsing: {language_name}")
        return parser.parse(code_bytes)


_engine: ParserEngine | None = None


def get_parser_engine() -> ParserEngine:
    global _engine
    if _engine is None:
        _engine = ParserEngine()
    return _engine


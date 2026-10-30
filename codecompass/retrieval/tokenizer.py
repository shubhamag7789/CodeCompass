from __future__ import annotations

import re
from typing import Final

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")
_CAMEL_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|[0-9]+")

STOPWORDS: Final[set[str]] = {
    "the", "and", "for", "with", "from", "this", "that", "self", "return",
    "import", "const", "let", "var", "def", "class", "function", "true", "false",
    "null", "none", "not", "are", "was", "you", "your", "how", "does", "where",
    "what", "which", "who", "when", "why", "into", "out", "get", "set", "new",
    "async", "await", "public", "private", "protected", "static", "export",
}


def tokenize(text: str) -> list[str]:
    """Splits code or prose into search terms, breaking identifiers on camelCase and snake_case."""
    tokens: list[str] = []
    for raw in _TOKEN_RE.findall(text):
        # Handle snake_case parts
        subparts = raw.split("_") if "_" in raw else [raw]
        for part in subparts:
            low = part.lower()
            if len(low) >= 2 and low not in STOPWORDS:
                tokens.append(low)

            # Handle camelCase / PascalCase sub-words
            camel_parts = _CAMEL_RE.findall(part)
            if len(camel_parts) > 1:
                for cp in camel_parts:
                    cp_low = cp.lower()
                    if len(cp_low) >= 2 and cp_low != low and cp_low not in STOPWORDS:
                        tokens.append(cp_low)
    return tokens


from __future__ import annotations

import os
from typing import Any


class QdrantVectorStore:
    """Boundary for semantic repository retrieval."""

    def __init__(self, url: str | None = None, api_key: str | None = None) -> None:
        self.url = url or os.getenv("QDRANT_URL", "")
        self.api_key = api_key or os.getenv("QDRANT_API_KEY", "")

    @property
    def configured(self) -> bool:
        return bool(self.url)

    def index_documents(self, documents: list[dict[str, Any]]) -> None:
        if not self.configured:
            raise RuntimeError("Qdrant is not configured. Set QDRANT_URL and optionally QDRANT_API_KEY.")
        raise NotImplementedError("Install qdrant-client and embed repository chunks before indexing.")


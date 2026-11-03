from __future__ import annotations

import os
from typing import Any


class Neo4jGraphStore:
    """Small boundary for the future production graph database.

    The local MVP keeps analysis as JSON so users do not need Neo4j setup.
    This class documents the contract the analyzer will write to once Neo4j is
    enabled in deployment.
    """

    def __init__(self, uri: str | None = None, username: str | None = None, password: str | None = None) -> None:
        self.uri = uri or os.getenv("NEO4J_URI", "")
        self.username = username or os.getenv("NEO4J_USERNAME", "")
        self.password = password or os.getenv("NEO4J_PASSWORD", "")

    @property
    def configured(self) -> bool:
        return bool(self.uri and self.username and self.password)

    def upsert_analysis(self, analysis: dict[str, Any]) -> None:
        if not self.configured:
            raise RuntimeError("Neo4j is not configured. Set NEO4J_URI, NEO4J_USERNAME, and NEO4J_PASSWORD.")
        raise NotImplementedError("Install the Neo4j driver and map nodes/relationships to Cypher writes.")


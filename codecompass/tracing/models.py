"""Data models for Feature Flow Tracing."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class FlowStep:
    step_number: int
    node_id: str
    label: str
    type: str
    path: str
    line: int | None = None
    relationship_type: str = "CALLS"
    caller_node_id: str | None = None
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["order"] = self.step_number
        d["symbol"] = self.label
        d["role"] = self.type
        d["file"] = self.path
        d["action"] = self.description
        return d


@dataclass
class ExecutionFlow:
    flow_id: str
    name: str
    category: str
    entry_point: FlowStep
    steps: list[FlowStep] = field(default_factory=list)
    involved_files: list[str] = field(default_factory=list)
    mermaid_sequence: str = ""
    mermaid_flowchart: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["entry_point"] = self.entry_point.to_dict()
        d["steps"] = [s.to_dict() for s in self.steps]
        d["files"] = self.involved_files
        d["mermaid"] = self.mermaid_sequence
        return d


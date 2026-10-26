"""Domain models for role-based onboarding."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class RoleType(str, Enum):
    BACKEND = "backend"
    FRONTEND = "frontend"
    FULLSTACK = "fullstack"
    DEVOPS_QA = "devops_qa"


@dataclass
class ReadingStep:
    day: int
    title: str
    description: str
    file_path: str
    line_start: int | None = None
    line_end: int | None = None
    entity_id: str | None = None
    category: str = "core"  # entrypoint, core, service, data, test

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RoleGuide:
    role: RoleType
    title: str
    mission: str
    summary: str
    reading_path: list[ReadingStep] = field(default_factory=list)
    key_entrypoints: list[dict[str, Any]] = field(default_factory=list)
    important_apis: list[dict[str, Any]] = field(default_factory=list)
    key_test_suites: list[str] = field(default_factory=list)
    high_risk_components: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["role"] = self.role.value
        # Add alias fields for UI compatibility
        d["learning_path"] = [
            {
                "phase": f"Day {s.day}",
                "title": s.title,
                "description": s.description,
                "files": [s.file_path] if s.file_path else [],
            }
            for s in self.reading_path
        ]
        d["core_files"] = [
            {
                "path": e.get("path", ""),
                "importance": "CORE ENTRYPOINT",
                "rationale": f"Primary application entry point and root route bootstrapper: {e.get('label', '')}",
            }
            for e in self.key_entrypoints
        ]
        # Generate actionable gotchas from high-risk components and architecture rules
        gotchas = []
        for hr in self.high_risk_components[:4]:
            gotchas.append(
                f"High-impact node: modifications to '{hr.get('label')}' ({hr.get('path')}) directly affect {hr.get('affected_files_count', 0)} downstream components. Test thoroughly."
            )
        if not gotchas:
            gotchas = [
                "Always verify JWT token expiration and user revocation in middleware before handling protected actions.",
                "Sanitize and validate all client-supplied parameters using validation schemas prior to controller dispatch.",
                "Ensure asynchronous service operations handle database timeouts gracefully with try-catch blocks.",
            ]
        d["gotchas"] = gotchas

        # First day action tasks
        first_tasks = [
            f"Review architectural entry point at {self.key_entrypoints[0]['path']}" if self.key_entrypoints else "Inspect project package.json and configuration files.",
            f"Trace data flow across the primary route {self.important_apis[0].get('method', 'GET')} {self.important_apis[0].get('path', '/')}" if self.important_apis else "Verify local environment setup and database connectivity.",
            "Run unit and integration test suite to verify baseline codebase health.",
        ]
        d["first_tasks"] = first_tasks
        return d


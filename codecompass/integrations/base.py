"""Abstract base classes and data models for CodeCompass LLM integrations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


CODECOMPASS_SYSTEM_PROMPT = (
    "You are CodeCompass AI, a senior software architect and codebase intelligence assistant. "
    "You answer developer questions about this software repository based ONLY on the provided "
    "repository architecture context, AST symbols, and retrieved code chunks.\n\n"
    "Guidelines:\n"
    "1. Ground all answers strictly in the provided code and repository context.\n"
    "2. When explaining components, functions, or workflows, cite the exact file path and line numbers.\n"
    "3. Trace execution clearly (e.g. Route -> Controller -> Service -> Model) when discussing features.\n"
    "4. If the context does not contain enough information to answer definitively, state so plainly "
    "instead of hallucinating or inventing code.\n"
    "5. Be concise, technically precise, and format code snippets in standard Markdown."
)


@dataclass
class LLMResponse:
    answer: str
    model: str
    provider: str
    tokens_used: int | None = None


class LLMProvider(ABC):
    """Abstract interface for LLM cloud providers."""

    @property
    @abstractmethod
    def configured(self) -> bool:
        """Returns True if the provider has valid credentials configured."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Returns the provider identifier (e.g. 'gemini', 'openrouter')."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Returns the active model name."""
        ...

    @abstractmethod
    def answer(
        self,
        question: str,
        context: str,
        prior_turns: list[dict[str, str]] | None = None,
        timeout: float = 60.0,
    ) -> LLMResponse:
        """Generates a grounded codebase answer from context and history."""
        ...


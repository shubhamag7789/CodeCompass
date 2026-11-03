"""LLM Integrations package for CodeCompass."""

from __future__ import annotations

import os
from pathlib import Path

from codecompass.integrations.base import LLMProvider, LLMResponse
from codecompass.integrations.gemini import GeminiAssistant
from codecompass.integrations.openrouter import OpenRouterAssistant

__all__ = ["GeminiAssistant", "LLMProvider", "LLMResponse", "OpenRouterAssistant", "get_llm_provider", "load_dotenv"]


def load_dotenv(dotenv_path: Path | str | None = None) -> None:
    """Loads environment variables from a .env file into os.environ (stdlib only)."""
    p = Path(dotenv_path) if dotenv_path else Path(".env")
    if not p.exists() or not p.is_file():
        return

    try:
        content = p.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = val
    except Exception:
        pass


def get_llm_provider(dotenv_path: Path | str | None = None) -> LLMProvider | None:
    """Returns the best available configured LLM provider (Gemini -> OpenRouter -> None)."""
    load_dotenv(dotenv_path)

    # 1. Prefer Gemini if GEMINI_API_KEY is configured
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    if gemini_key:
        return GeminiAssistant(api_key=gemini_key)

    # 2. Check OpenRouter if OPENROUTER_API_KEY is configured
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if openrouter_key:
        return OpenRouterAssistant(api_key=openrouter_key)

    # 3. None -> signals fallback to local extractive answering
    return None

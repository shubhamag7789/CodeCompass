"""OpenRouter LLM Integration for CodeCompass.

Enables cloud inference through OpenRouter chat completions using standard library HTTP.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from codecompass.integrations.base import CODECOMPASS_SYSTEM_PROMPT, LLMProvider, LLMResponse

DEFAULT_OPENROUTER_MODEL = "openai/gpt-4o-mini"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterAssistant(LLMProvider):
    """OpenRouter cloud assistant for grounded codebase Q&A."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key.strip() if api_key is not None else os.getenv("OPENROUTER_API_KEY", "").strip()
        self.model = model.strip() if model is not None else os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL).strip()

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    @property
    def provider_name(self) -> str:
        return "openrouter"

    @property
    def model_name(self) -> str:
        return self.model

    def answer(
        self,
        question: str,
        context: str,
        prior_turns: list[dict[str, str]] | None = None,
        timeout: float = 60.0,
    ) -> LLMResponse:
        if not self.configured:
            raise RuntimeError("OpenRouter is not configured. Set OPENROUTER_API_KEY.")

        messages: list[dict[str, str]] = [
            {"role": "system", "content": CODECOMPASS_SYSTEM_PROMPT}
        ]

        if prior_turns:
            for turn in prior_turns[-4:]:
                q = turn.get("question", "").strip()
                a = turn.get("answer", "").strip()
                if q:
                    messages.append({"role": "user", "content": q})
                if a:
                    messages.append({"role": "assistant", "content": a})

        messages.append({"role": "user", "content": f"{context}\n\nQuestion: {question}"})

        payload = {
            "model": self.model,
            "temperature": 0.15,
            "messages": messages,
        }

        request = urllib.request.Request(
            OPENROUTER_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/CodeCompass/CodeCompass",
                "X-Title": "CodeCompass",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:500]
            raise RuntimeError(f"OpenRouter request failed ({exc.code}): {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"OpenRouter connection failed: {exc.reason}") from exc

        try:
            text = data["choices"][0]["message"]["content"].strip()
            tokens = data.get("usage", {}).get("total_tokens")
            return LLMResponse(
                answer=text,
                model=self.model,
                provider="openrouter",
                tokens_used=tokens,
            )
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected OpenRouter response shape: {data!r}") from exc

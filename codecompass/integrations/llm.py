from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM_PROMPT = (
    "You are CodeCompass, an assistant that answers questions about a specific software "
    "repository. Answer only from the provided repository context: its summary and the "
    "retrieved code snippets. When you reference code, cite the file path and line range "
    "shown in the context. If the context does not contain the answer, say so plainly "
    "instead of guessing. Be concise and concrete."
)


class OpenRouterAssistant:
    """LLM-backed repository answers via OpenRouter chat completions.

    Uses only the standard library so the package stays dependency-free. The
    assistant is optional: when no API key is configured the caller falls back to
    a local extractive answer, keeping CodeCompass usable with zero setup.
    """

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        self.model = model or os.getenv("OPENROUTER_MODEL", "openai/gpt-4.1-mini")

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def answer(self, question: str, context: str, timeout: float = 60.0) -> str:
        if not self.configured:
            raise RuntimeError("OpenRouter is not configured. Set OPENROUTER_API_KEY.")

        payload = {
            "model": self.model,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"{context}\n\nQuestion: {question}"},
            ],
        }
        request = urllib.request.Request(
            OPENROUTER_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/Philipcyrus/CodeCompass",
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
            raise RuntimeError(f"OpenRouter request failed: {exc.reason}") from exc

        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected OpenRouter response shape: {data!r}") from exc

"""Google Gemini LLM Integration for CodeCompass.

Implements native REST API communication with Google AI Studio using standard library HTTP.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from codecompass.integrations.base import CODECOMPASS_SYSTEM_PROMPT, LLMProvider, LLMResponse

DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiAssistant(LLMProvider):
    """Google Gemini cloud assistant for grounded codebase Q&A."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key.strip() if api_key is not None else os.getenv("GEMINI_API_KEY", "").strip()
        self.model = model.strip() if model is not None else os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip()

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    @property
    def provider_name(self) -> str:
        return "gemini"

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
            raise RuntimeError("Gemini is not configured. Set GEMINI_API_KEY environment variable.")

        url = f"{GEMINI_BASE_URL.format(model=self.model)}?key={self.api_key}"

        # Construct multi-turn contents payload
        contents: list[dict[str, Any]] = []

        if prior_turns:
            # Include up to last 4 conversation turns for context continuity
            for turn in prior_turns[-4:]:
                q = turn.get("question", "").strip()
                a = turn.get("answer", "").strip()
                if q:
                    contents.append({"role": "user", "parts": [{"text": q}]})
                if a:
                    contents.append({"role": "model", "parts": [{"text": a}]})

        # Append final prompt with grounded repository context
        user_prompt = f"Repository Context:\n{context}\n\nDeveloper Question: {question}"
        contents.append({"role": "user", "parts": [{"text": user_prompt}]})

        payload = {
            "contents": contents,
            "system_instruction": {
                "parts": [{"text": CODECOMPASS_SYSTEM_PROMPT}]
            },
            "generationConfig": {
                "temperature": 0.15,
                "maxOutputTokens": 2048,
            },
        }

        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "CodeCompass/1.0",
            },
            method="POST",
        )

        import ssl
        import time
        ssl_ctx = ssl.create_default_context()

        last_err: Exception | None = None
        for attempt in range(2):
            try:
                with urllib.request.urlopen(request, context=ssl_ctx, timeout=timeout) as response:
                    data = json.loads(response.read().decode("utf-8"))
                    last_err = None
                    break
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "replace")[:500]
                if exc.code in {503, 429} and attempt == 0:
                    time.sleep(1.0)
                    fallback_url = f"{GEMINI_BASE_URL.format(model='gemini-flash-lite-latest')}?key={self.api_key}"
                    request = urllib.request.Request(fallback_url, data=request.data, headers=request.headers, method="POST")
                    continue
                raise RuntimeError(f"Gemini API request failed ({exc.code}): {detail}") from exc
            except urllib.error.URLError as exc:
                last_err = exc
                if attempt == 0:
                    time.sleep(0.5)
                    continue
                raise RuntimeError(f"Gemini network connection failed: {exc.reason}") from exc
            except Exception as exc:
                last_err = exc
                if attempt == 0:
                    time.sleep(0.5)
                    continue
                raise RuntimeError(f"Gemini request failed: {exc}") from exc

        if last_err:
            raise RuntimeError(f"Gemini call failed after retry: {last_err}")

        try:
            candidate = data["candidates"][0]
            answer_text = candidate["content"]["parts"][0]["text"].strip()
            total_tokens = data.get("usageMetadata", {}).get("totalTokenCount")
            return LLMResponse(
                answer=answer_text,
                model=self.model,
                provider="gemini",
                tokens_used=total_tokens,
            )
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected Gemini response structure: {data!r}") from exc

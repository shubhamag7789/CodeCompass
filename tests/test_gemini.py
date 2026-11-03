"""Automated unit tests for CodeCompass Google Gemini LLM Integration."""

from __future__ import annotations

import io
import json
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

from codecompass.integrations.gemini import GeminiAssistant


class GeminiAssistantTest(unittest.TestCase):
    def test_configured_state(self) -> None:
        unconfigured = GeminiAssistant(api_key="")
        self.assertFalse(unconfigured.configured)

        configured = GeminiAssistant(api_key="mock_key_123")
        self.assertTrue(configured.configured)
        self.assertEqual(configured.provider_name, "gemini")

    def test_unconfigured_call_raises_runtime_error(self) -> None:
        assistant = GeminiAssistant(api_key="")
        with self.assertRaises(RuntimeError) as ctx:
            assistant.answer("What does X do?", "context")
        self.assertIn("not configured", str(ctx.exception).lower())

    @patch("urllib.request.urlopen")
    def test_successful_gemini_generation(self, mock_urlopen) -> None:
        mock_response_payload = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "The function startServer() initializes express and listens on port 5000."}],
                        "role": "model",
                    },
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 50,
                "candidatesTokenCount": 18,
                "totalTokenCount": 68,
            },
        }

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_response_payload).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        assistant = GeminiAssistant(api_key="mock_valid_key", model="gemini-flash-lite-latest")
        res = assistant.answer(
            question="What does startServer do?",
            context="File: server.ts, startServer() on line 12",
            prior_turns=[{"question": "Where is the entry point?", "answer": "In server.ts"}],
        )

        self.assertEqual(res.provider, "gemini")
        self.assertEqual(res.model, "gemini-flash-lite-latest")
        self.assertIn("startServer()", res.answer)
        self.assertEqual(res.tokens_used, 68)

        # Verify request structure
        call_args, _ = mock_urlopen.call_args
        req = call_args[0]
        self.assertIn("key=mock_valid_key", req.full_url)
        body = json.loads(req.data.decode("utf-8"))
        self.assertIn("system_instruction", body)
        self.assertEqual(len(body["contents"]), 3)  # user Q1, model A1, user Q2 with context

    @patch("urllib.request.urlopen")
    def test_gemini_http_error_handling(self, mock_urlopen) -> None:
        error = urllib.error.HTTPError(
            url="https://generativelanguage.googleapis.com",
            code=403,
            msg="Forbidden",
            hdrs={},
            fp=io.BytesIO(b'{"error": {"message": "Invalid API key."}}'),
        )
        mock_urlopen.side_effect = error

        assistant = GeminiAssistant(api_key="invalid_key")
        with self.assertRaises(RuntimeError) as ctx:
            assistant.answer("Query", "Context")
        self.assertIn("403", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()


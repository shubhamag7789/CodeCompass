"""Automated unit tests for LLM provider discovery and fallback hierarchy."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from codecompass.integrations import get_llm_provider
from codecompass.integrations.gemini import GeminiAssistant
from codecompass.integrations.openrouter import OpenRouterAssistant


class LLMProviderDiscoveryTest(unittest.TestCase):
    @patch.dict(os.environ, {"GEMINI_API_KEY": "test_gemini", "OPENROUTER_API_KEY": "test_or"}, clear=True)
    def test_gemini_takes_precedence_when_both_set(self) -> None:
        provider = get_llm_provider(dotenv_path="nonexistent.env")
        self.assertIsNotNone(provider)
        self.assertIsInstance(provider, GeminiAssistant)
        self.assertEqual(provider.provider_name, "gemini")

    @patch.dict(os.environ, {"GEMINI_API_KEY": "", "OPENROUTER_API_KEY": "test_or"}, clear=True)
    def test_openrouter_selected_when_gemini_missing(self) -> None:
        provider = get_llm_provider(dotenv_path="nonexistent.env")
        self.assertIsNotNone(provider)
        self.assertIsInstance(provider, OpenRouterAssistant)
        self.assertEqual(provider.provider_name, "openrouter")

    @patch.dict(os.environ, {"GEMINI_API_KEY": "", "OPENROUTER_API_KEY": ""}, clear=True)
    def test_returns_none_when_no_keys_configured(self) -> None:
        provider = get_llm_provider(dotenv_path="nonexistent.env")
        self.assertIsNone(provider)


if __name__ == "__main__":
    unittest.main()


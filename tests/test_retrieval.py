import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from codecompass.assistant import answer_question
from codecompass.integrations import llm
from codecompass.integrations.llm import OpenRouterAssistant
from codecompass.retrieval import SearchIndex, build_index, tokenize


def _sample_repo(root: Path) -> None:
    (root / "auth.py").write_text(
        "\n".join(
            [
                "class AuthService:",
                "    def login(self, user, password):",
                "        # verify the password and issue a session token",
                "        return validate_credentials(user, password)",
            ]
        ),
        encoding="utf-8",
    )
    (root / "payments.py").write_text(
        "def charge_card(amount):\n    return stripe_client.charge(amount)\n",
        encoding="utf-8",
    )


class TokenizeTest(unittest.TestCase):
    def test_splits_camel_case_and_snake_case(self) -> None:
        tokens = tokenize("AuthService validate_credentials")
        self.assertIn("auth", tokens)
        self.assertIn("service", tokens)
        self.assertIn("validate", tokens)
        self.assertIn("credentials", tokens)


class SearchIndexTest(unittest.TestCase):
    def test_search_ranks_relevant_chunk_first(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _sample_repo(root)
            index = SearchIndex.from_dict(build_index(root))

        results = index.search("how does login authentication work", k=3)
        self.assertTrue(results)
        self.assertEqual(results[0]["file"], "auth.py")

    def test_empty_query_returns_nothing(self) -> None:
        index = SearchIndex.from_dict({"chunks": []})
        self.assertEqual(index.search("anything"), [])


class AssistantFallbackTest(unittest.TestCase):
    def test_local_answer_without_key_cites_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _sample_repo(root)
            index = SearchIndex.from_dict(build_index(root))

        analysis = {"summary": {"headline": "test repo", "primary_components": []}, "apis": [], "impact_index": {}}
        # An assistant with no key must never raise; it degrades to local retrieval.
        result = answer_question(analysis, index, "where is login handled", assistant=OpenRouterAssistant(api_key=""))
        self.assertEqual(result["mode"], "local")
        self.assertTrue(any(source["file"] == "auth.py" for source in result["sources"]))

    def test_llm_path_used_when_configured(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _sample_repo(root)
            index = SearchIndex.from_dict(build_index(root))

        class StubAssistant(OpenRouterAssistant):
            def __init__(self) -> None:
                super().__init__(api_key="test-key", model="stub/model")
                self.received_context = ""

            def answer(self, question: str, context: str, timeout: float = 60.0) -> str:
                self.received_context = context
                return "Login is handled in auth.py."

        analysis = {"summary": {"headline": "test repo", "primary_components": []}, "apis": [], "impact_index": {}}
        stub = StubAssistant()
        result = answer_question(analysis, index, "where is login handled", assistant=stub)
        self.assertEqual(result["mode"], "llm")
        self.assertEqual(result["answer"], "Login is handled in auth.py.")
        self.assertIn("auth.py", stub.received_context)


class OpenRouterWiringTest(unittest.TestCase):
    def test_answer_builds_request_and_parses_response(self) -> None:
        captured = {}

        class FakeResponse(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.close()
                return False

        def fake_urlopen(request, timeout=None):
            captured["url"] = request.full_url
            captured["auth"] = request.headers.get("Authorization")
            captured["body"] = json.loads(request.data.decode("utf-8"))
            payload = {"choices": [{"message": {"content": "  grounded answer  "}}]}
            return FakeResponse(json.dumps(payload).encode("utf-8"))

        assistant = OpenRouterAssistant(api_key="secret", model="stub/model")
        with mock.patch.object(llm.urllib.request, "urlopen", fake_urlopen):
            answer = assistant.answer("q?", "context here")

        self.assertEqual(answer, "grounded answer")
        self.assertEqual(captured["url"], llm.OPENROUTER_URL)
        self.assertEqual(captured["auth"], "Bearer secret")
        self.assertEqual(captured["body"]["model"], "stub/model")
        self.assertEqual(captured["body"]["messages"][0]["role"], "system")


if __name__ == "__main__":
    unittest.main()

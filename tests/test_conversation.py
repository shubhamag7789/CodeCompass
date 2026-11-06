import tempfile
import unittest
from pathlib import Path

from codecompass.conversation import (
    MAX_HISTORY_TURNS,
    MAX_TURNS_PER_CONVERSATION,
    Conversation,
    ConversationManager,
    Turn,
    chat_answer,
    resolve_query,
)
from codecompass.integrations.llm import OpenRouterAssistant
from codecompass.retrieval import SearchIndex, build_index


def _sample_repo(root: Path) -> None:
    (root / "auth.py").write_text(
        "\n".join(
            [
                "class AuthService:",
                "    def login(self, user, password):",
                "        # verify the password and issue a session token",
                "        return validate_credentials(user, password)",
                "",
                "def validate_credentials(user, password):",
                "    return lookup_user(user).check(password)",
            ]
        ),
        encoding="utf-8",
    )
    (root / "payments.py").write_text(
        "def charge_card(amount):\n    return stripe_client.charge(amount)\n",
        encoding="utf-8",
    )


def _index(root: Path) -> SearchIndex:
    return SearchIndex.from_dict(build_index(root))


def _analysis() -> dict:
    return {
        "repository": {"name": "sample"},
        "summary": {"headline": "sample repo", "primary_components": [], "languages": []},
        "apis": [],
        "impact_index": {},
    }


class OfflineAssistant(OpenRouterAssistant):
    def __init__(self) -> None:
        super().__init__(api_key="")


class ScriptedAssistant(OpenRouterAssistant):
    """Configured assistant that echoes the context so we can assert on it."""

    def __init__(self) -> None:
        super().__init__(api_key="key", model="stub/model")
        self.contexts: list[str] = []

    def answer(self, question: str, context: str, timeout: float = 60.0) -> str:
        self.contexts.append(context)
        return f"answer-for::{question}"


class ResolveQueryTest(unittest.TestCase):
    def test_pronoun_resolves_to_previous_entity(self) -> None:
        conv = Conversation(id="c1")
        conv.add_turn(Turn(question="How does login work?", answer="...", sources=[{"label": "auth.py", "file": "auth.py"}]))
        resolved = resolve_query("what calls it?", conv)
        self.assertTrue(resolved["referential"])
        self.assertEqual(resolved["entity"], "auth")
        self.assertIn("auth", resolved["text"].lower())
        self.assertNotIn(" it?", resolved["text"].lower())

    def test_phrase_reference_is_rewritten(self) -> None:
        conv = Conversation(id="c1")
        conv.add_turn(Turn(question="Explain charge_card", answer="...", sources=[{"label": "payments.py", "file": "payments.py"}]))
        resolved = resolve_query("where is that function used?", conv)
        self.assertIn("payments", resolved["text"].lower())

    def test_no_history_leaves_question_unchanged(self) -> None:
        resolved = resolve_query("what calls it?", Conversation(id="fresh"))
        self.assertIsNone(resolved["entity"])
        self.assertEqual(resolved["text"], "what calls it?")


class FollowUpRetrievalTest(unittest.TestCase):
    def test_followup_retrieves_previous_topic(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _sample_repo(root)
            index = _index(root)
        conv = Conversation(id="c1")

        first = chat_answer(_analysis(), index, conv, "How does login authentication work?", assistant=OfflineAssistant())
        self.assertTrue(any(s["file"] == "auth.py" for s in first["sources"]))

        # A bare follow-up with no topic words of its own must still find auth code.
        second = chat_answer(_analysis(), index, conv, "what validates it?", assistant=OfflineAssistant())
        self.assertTrue(any(s["file"] == "auth.py" for s in second["sources"]), second)
        self.assertEqual(len(conv.turns), 2)

    def test_llm_prompt_includes_prior_turns(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _sample_repo(root)
            index = _index(root)
        conv = Conversation(id="c1")
        scripted = ScriptedAssistant()

        chat_answer(_analysis(), index, conv, "How does login work?", assistant=scripted)
        chat_answer(_analysis(), index, conv, "what calls it?", assistant=scripted)

        # The second prompt must carry the first exchange as conversation history.
        self.assertIn("Conversation so far", scripted.contexts[1])
        self.assertIn("How does login work?", scripted.contexts[1])


class LongConversationTest(unittest.TestCase):
    def test_history_window_is_bounded(self) -> None:
        conv = Conversation(id="c1")
        for i in range(MAX_HISTORY_TURNS + 5):
            conv.add_turn(Turn(question=f"q{i}", answer=f"a{i}"))
        history = conv.history_for_prompt()
        self.assertLessEqual(len(history), MAX_HISTORY_TURNS)
        # Keeps the most recent turns, oldest-first.
        self.assertEqual(history[-1][0], f"q{MAX_HISTORY_TURNS + 4}")

    def test_turns_are_capped(self) -> None:
        conv = Conversation(id="c1")
        for i in range(MAX_TURNS_PER_CONVERSATION + 10):
            conv.add_turn(Turn(question=f"q{i}", answer="a"))
        self.assertEqual(len(conv.turns), MAX_TURNS_PER_CONVERSATION)
        self.assertEqual(conv.turns[-1].question, f"q{MAX_TURNS_PER_CONVERSATION + 9}")


class MissingContextTest(unittest.TestCase):
    def test_followup_without_history_degrades_gracefully(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _sample_repo(root)
            index = _index(root)
        conv = Conversation(id="c1")
        result = chat_answer(_analysis(), index, conv, "what does it return?", assistant=OfflineAssistant())
        self.assertIn("mode", result)
        self.assertTrue(result["answer"])  # never crashes / never empty
        self.assertEqual(len(conv.turns), 1)


class ResetTest(unittest.TestCase):
    def test_reset_clears_turns_and_entity(self) -> None:
        manager = ConversationManager()
        conv = manager.get_or_create("c1")
        conv.add_turn(Turn(question="q", answer="a", sources=[{"label": "auth.py"}]))
        self.assertEqual(conv.salient_entity(), "auth")

        self.assertTrue(manager.reset("c1"))
        self.assertEqual(len(conv.turns), 0)
        self.assertIsNone(conv.salient_entity())

    def test_reset_unknown_conversation_returns_false(self) -> None:
        self.assertFalse(ConversationManager().reset("nope"))

    def test_get_or_create_is_stable_and_generates_ids(self) -> None:
        manager = ConversationManager()
        a = manager.get_or_create("c1")
        b = manager.get_or_create("c1")
        self.assertIs(a, b)
        generated = manager.get_or_create()
        self.assertTrue(generated.id)
        self.assertNotEqual(generated.id, "c1")


class SQLitePersistenceTest(unittest.TestCase):
    def test_sqlite_turn_persistence_across_instances(self) -> None:
        from codecompass.storage.database import Database

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "test.db"
            db = Database(str(db_path))

            # Manager 1 writes turns
            mgr1 = ConversationManager(db=db)
            conv1 = mgr1.get_or_create("chat-123", repo_id="sample-repo")
            mgr1.record_turn(
                conv1,
                Turn(
                    question="Where is login?",
                    answer="In auth.py AuthService.login",
                    sources=[{"file": "auth.py", "start_line": 23, "end_line": 25}],
                    mode="llm",
                ),
            )
            self.assertEqual(len(conv1.turns), 1)

            # Manager 2 (fresh instance, simulating server restart)
            mgr2 = ConversationManager(db=db)
            conv2 = mgr2.get_or_create("chat-123", repo_id="sample-repo")
            self.assertEqual(len(conv2.turns), 1)
            self.assertEqual(conv2.turns[0].question, "Where is login?")
            self.assertEqual(conv2.turns[0].answer, "In auth.py AuthService.login")
            self.assertEqual(conv2.turns[0].sources[0]["file"], "auth.py")

            # Reset clears database records too
            mgr2.reset("chat-123")
            mgr3 = ConversationManager(db=db)
            conv3 = mgr3.get_or_create("chat-123", repo_id="sample-repo")
            self.assertEqual(len(conv3.turns), 0)


if __name__ == "__main__":
    unittest.main()

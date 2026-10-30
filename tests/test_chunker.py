import json
import unittest
from codecompass.extractor import extract_file
from codecompass.retrieval.chunker import create_semantic_chunks


class ChunkerTest(unittest.TestCase):
    def test_semantic_chunks_aligned_to_functions_and_classes(self) -> None:
        code = b'''"""Module header."""
import sys

def authenticate(username: str, password: str) -> bool:
    """Verifies credentials."""
    return username == "admin" and password == "secret"

class OrderProcessor:
    """Processes customer orders."""
    def process_order(self, order_id: int):
        return {"status": "shipped"}
'''
        result = extract_file("services/auth.py", code, "Python")
        chunks = create_semantic_chunks(
            repo_id="test_repo",
            file_id="file:services/auth.py",
            rel_path="services/auth.py",
            code_text=code.decode("utf-8"),
            entities=result.entities,
        )

        self.assertGreaterEqual(len(chunks), 2)

        # Find authenticate function chunk
        auth_chunk = next((c for c in chunks if "authenticate" in c.label), None)
        self.assertIsNotNone(auth_chunk)
        self.assertIn("def authenticate", auth_chunk.content)
        self.assertIn("Verifies credentials.", auth_chunk.content)
        self.assertEqual(auth_chunk.start_line, 4)

        # Check tokens
        tokens = json.loads(auth_chunk.tokens_json)
        self.assertIn("authenticate", tokens)
        self.assertIn("username", tokens)
        self.assertIn("password", tokens)

        # Find method chunk
        method_chunk = next((c for c in chunks if "process_order" in c.label), None)
        self.assertIsNotNone(method_chunk)
        self.assertIn("process_order", method_chunk.content)

    def test_fallback_chunking_on_plain_file(self) -> None:
        lines = [f"line {i} = {i * 10}" for i in range(1, 100)]
        plain_code = "\n".join(lines)

        chunks = create_semantic_chunks(
            repo_id="test_repo",
            file_id="file:config.txt",
            rel_path="config.txt",
            code_text=plain_code,
            entities=[],
        )

        self.assertGreater(len(chunks), 1)
        self.assertEqual(chunks[0].start_line, 1)


if __name__ == "__main__":
    unittest.main()


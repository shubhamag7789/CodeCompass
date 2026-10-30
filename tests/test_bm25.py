import json
import tempfile
import unittest
from pathlib import Path

from codecompass.retrieval.bm25 import BM25Index
from codecompass.retrieval.tokenizer import tokenize
from codecompass.storage.database import Database
from codecompass.storage.models import FileRecord, RepositoryRecord, SearchChunkRecord
from codecompass.storage.repositories import FileDAL, RepositoryDAL, SearchChunkDAL


class BM25Test(unittest.TestCase):
    def test_tokenizer_camel_and_snake(self) -> None:
        tokens = tokenize("calculateMonthlyInterest_v2")
        self.assertIn("calculate", tokens)
        self.assertIn("monthly", tokens)
        self.assertIn("interest", tokens)
        self.assertIn("v2", tokens)

    def test_bm25_ranking_and_structural_boosting(self) -> None:
        chunk1 = SearchChunkRecord(
            id="c1",
            repo_id="r1",
            file_id="file:services/auth.py",
            entity_id="e1",
            start_line=1,
            end_line=10,
            label="authenticate_user",
            content="def authenticate_user(token):\n    return verify(token)",
            tokens_json=json.dumps(tokenize("authenticate user verify token")),
        )
        chunk2 = SearchChunkRecord(
            id="c2",
            repo_id="r1",
            file_id="file:services/orders.py",
            entity_id="e2",
            start_line=1,
            end_line=10,
            label="process_order",
            content="def process_order(id):\n    print('order processed')",
            tokens_json=json.dumps(tokenize("process order printed")),
        )

        index = BM25Index([chunk1, chunk2])
        results = index.search("how to authenticate user", k=2)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, "c1")
        self.assertEqual(results[0].file, "services/auth.py")
        self.assertGreater(results[0].score, 0.0)

    def test_load_from_database(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.db"
            db = Database(db_path)

            repo_dal = RepositoryDAL(db)
            repo_dal.upsert_repository(RepositoryRecord(id="r1", name="R1", root_path="/r1"))

            file_dal = FileDAL(db)
            file_dal.upsert_files([
                FileRecord(
                    id="file:main.py",
                    repo_id="r1",
                    path="main.py",
                    language="Python",
                    size_bytes=50,
                    lines=5,
                    content_hash="h1",
                )
            ])

            chunk_dal = SearchChunkDAL(db)
            chunk_dal.replace_chunks_for_file("r1", "file:main.py", [
                SearchChunkRecord(
                    id="c1",
                    repo_id="r1",
                    file_id="file:main.py",
                    entity_id=None,
                    start_line=1,
                    end_line=5,
                    label="main_entry",
                    content="def main(): print('starting engine')",
                    tokens_json=json.dumps(tokenize("main starting engine")),
                )
            ])

            index = BM25Index.from_database(db, "r1")
            results = index.search("starting engine")
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].id, "c1")
            self.assertEqual(results[0].label, "main_entry")


if __name__ == "__main__":
    unittest.main()


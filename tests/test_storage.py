import tempfile
import unittest
from pathlib import Path

from codecompass.storage.database import Database
from codecompass.storage.models import (
    ConversationRecord,
    ConversationTurnRecord,
    EntityRecord,
    FileRecord,
    RelationshipRecord,
    RepositoryRecord,
    SearchChunkRecord,
)
from codecompass.storage.repositories import (
    ConversationDAL,
    EntityDAL,
    FileDAL,
    RelationshipDAL,
    RepositoryDAL,
    SearchChunkDAL,
)


class StorageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.db = Database(self.db_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_database_initialization_and_wal_mode(self) -> None:
        self.assertTrue(self.db_path.exists())
        mode = self.db.get_journal_mode().lower()
        self.assertEqual(mode, "wal")

    def test_repository_dal_upsert_and_get(self) -> None:
        dal = RepositoryDAL(self.db)
        repo = RepositoryRecord(id="repo:test", name="TestRepo", root_path="/path/to/test")
        dal.upsert_repository(repo)

        fetched = dal.get_by_root("/path/to/test")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.id, "repo:test")
        self.assertEqual(fetched.name, "TestRepo")

        # Update repository name
        updated_repo = RepositoryRecord(id="repo:test", name="TestRepoV2", root_path="/path/to/test")
        dal.upsert_repository(updated_repo)
        fetched_updated = dal.get_by_root("/path/to/test")
        self.assertEqual(fetched_updated.name, "TestRepoV2")

    def test_file_dal_crud_and_delete_missing(self) -> None:
        repo_dal = RepositoryDAL(self.db)
        repo_dal.upsert_repository(RepositoryRecord(id="repo:1", name="R1", root_path="/r1"))

        file_dal = FileDAL(self.db)
        f1 = FileRecord(
            id="file:app.py",
            repo_id="repo:1",
            path="app.py",
            language="Python",
            size_bytes=100,
            lines=10,
            content_hash="hash1",
            is_test=False,
        )
        f2 = FileRecord(
            id="file:test_app.py",
            repo_id="repo:1",
            path="tests/test_app.py",
            language="Python",
            size_bytes=200,
            lines=20,
            content_hash="hash2",
            is_test=True,
        )

        file_dal.upsert_files([f1, f2])
        files = file_dal.get_files_for_repo("repo:1")
        self.assertEqual(len(files), 2)
        self.assertEqual(files[0].path, "app.py")
        self.assertFalse(files[0].is_test)
        self.assertEqual(files[1].path, "tests/test_app.py")
        self.assertTrue(files[1].is_test)

        # Delete missing files: keep only f1
        deleted_count = file_dal.delete_missing_files("repo:1", {"app.py"})
        self.assertEqual(deleted_count, 1)
        remaining = file_dal.get_files_for_repo("repo:1")
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].path, "app.py")

    def test_entity_and_relationship_dal(self) -> None:
        repo_dal = RepositoryDAL(self.db)
        repo_dal.upsert_repository(RepositoryRecord(id="repo:1", name="R1", root_path="/r1"))
        file_dal = FileDAL(self.db)
        file_dal.upsert_files([
            FileRecord(
                id="file:main.py",
                repo_id="repo:1",
                path="main.py",
                language="Python",
                size_bytes=50,
                lines=5,
                content_hash="h1",
            )
        ])

        entity_dal = EntityDAL(self.db)
        e1 = EntityRecord(
            id="class:App",
            repo_id="repo:1",
            file_id="file:main.py",
            kind="Class",
            name="App",
            start_line=1,
            end_line=4,
        )
        entity_dal.replace_entities_for_file("repo:1", "file:main.py", [e1])

        entities = entity_dal.get_entities_for_repo("repo:1")
        self.assertEqual(len(entities), 1)
        self.assertEqual(entities[0].name, "App")
        self.assertEqual(entities[0].kind, "Class")

        rel_dal = RelationshipDAL(self.db)
        rel1 = RelationshipRecord(
            id=None,
            repo_id="repo:1",
            source_id="file:main.py",
            target_id="class:App",
            type="CONTAINS",
        )
        rel_dal.replace_relationships_for_repo("repo:1", [rel1])
        rels = rel_dal.get_relationships_for_repo("repo:1")
        self.assertEqual(len(rels), 1)
        self.assertEqual(rels[0].type, "CONTAINS")

    def test_search_chunk_dal(self) -> None:
        repo_dal = RepositoryDAL(self.db)
        repo_dal.upsert_repository(RepositoryRecord(id="repo:1", name="R1", root_path="/r1"))
        file_dal = FileDAL(self.db)
        file_dal.upsert_files([
            FileRecord(
                id="file:main.py",
                repo_id="repo:1",
                path="main.py",
                language="Python",
                size_bytes=50,
                lines=5,
                content_hash="h1",
            )
        ])

        chunk_dal = SearchChunkDAL(self.db)
        c1 = SearchChunkRecord(
            id="chunk:1",
            repo_id="repo:1",
            file_id="file:main.py",
            entity_id=None,
            start_line=1,
            end_line=5,
            label="main.py",
            content="print('hello')",
            tokens_json='["print", "hello"]',
        )
        chunk_dal.replace_chunks_for_file("repo:1", "file:main.py", [c1])
        chunks = chunk_dal.get_chunks_for_repo("repo:1")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].label, "main.py")

    def test_conversation_dal(self) -> None:
        repo_dal = RepositoryDAL(self.db)
        repo_dal.upsert_repository(RepositoryRecord(id="repo:1", name="R1", root_path="/r1"))

        conv_dal = ConversationDAL(self.db)
        conv = conv_dal.get_or_create_conversation("c1", "repo:1")
        self.assertEqual(conv.id, "c1")

        turn_id = conv_dal.add_turn(
            ConversationTurnRecord(
                id=None,
                conversation_id="c1",
                turn_index=0,
                question="What does main do?",
                answer="It prints hello.",
                mode="local",
                sources_json='[{"file": "main.py"}]',
            )
        )
        self.assertGreater(turn_id, 0)

        turns = conv_dal.get_turns("c1")
        self.assertEqual(len(turns), 1)
        self.assertEqual(turns[0].question, "What does main do?")

        conv_dal.reset_conversation("c1")
        turns_after_reset = conv_dal.get_turns("c1")
        self.assertEqual(len(turns_after_reset), 0)

    def test_foreign_key_cascades(self) -> None:
        repo_dal = RepositoryDAL(self.db)
        repo_dal.upsert_repository(RepositoryRecord(id="repo:del", name="Del", root_path="/del"))

        file_dal = FileDAL(self.db)
        file_dal.upsert_files([
            FileRecord(
                id="file:del.py",
                repo_id="repo:del",
                path="del.py",
                language="Python",
                size_bytes=10,
                lines=1,
                content_hash="h",
            )
        ])

        with self.db.transaction() as conn:
            conn.execute("DELETE FROM repositories WHERE id = ?", ("repo:del",))

        files = file_dal.get_files_for_repo("repo:del")
        self.assertEqual(len(files), 0)


if __name__ == "__main__":
    unittest.main()


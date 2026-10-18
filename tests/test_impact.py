import unittest
from codecompass.graph.impact import GraphImpactAnalyzer
from codecompass.storage.models import EntityRecord, FileRecord, RelationshipRecord


class ImpactAnalyzerTest(unittest.TestCase):
    def test_two_hop_reverse_dependency_walk_and_risk(self) -> None:
        # Topology:
        # endpoint (API in api.py) -> CALLS -> auth_service (Method in auth.py)
        # auth_service (Method in auth.py) -> CALLS -> db_query (Function in db.py)
        # test_auth (in tests/test_auth.py) -> TESTS -> auth.py

        files = [
            FileRecord(id="file:api.py", repo_id="r1", path="api.py", language="Python", size_bytes=100, lines=10, content_hash="h1"),
            FileRecord(id="file:auth.py", repo_id="r1", path="auth.py", language="Python", size_bytes=100, lines=10, content_hash="h2"),
            FileRecord(id="file:db.py", repo_id="r1", path="db.py", language="Python", size_bytes=100, lines=10, content_hash="h3"),
            FileRecord(id="file:tests/test_auth.py", repo_id="r1", path="tests/test_auth.py", language="Python", size_bytes=100, lines=10, content_hash="h4", is_test=True),
        ]

        entities = [
            EntityRecord(id="api:login", repo_id="r1", file_id="file:api.py", kind="API", name="POST /login", start_line=1, end_line=5),
            EntityRecord(id="method:auth", repo_id="r1", file_id="file:auth.py", kind="Method", name="authenticate", start_line=1, end_line=5),
            EntityRecord(id="fn:db", repo_id="r1", file_id="file:db.py", kind="Function", name="query_user", start_line=1, end_line=5),
        ]

        relationships = [
            # api:login calls method:auth
            RelationshipRecord(id=1, repo_id="r1", source_id="api:login", target_id="method:auth", type="CALLS"),
            # method:auth calls fn:db
            RelationshipRecord(id=2, repo_id="r1", source_id="method:auth", target_id="fn:db", type="CALLS"),
            # test_auth tests file:auth.py
            RelationshipRecord(id=3, repo_id="r1", source_id="file:tests/test_auth.py", target_id="file:auth.py", type="TESTS"),
            # file contains entities
            RelationshipRecord(id=4, repo_id="r1", source_id="file:auth.py", target_id="method:auth", type="CONTAINS"),
        ]

        analyzer = GraphImpactAnalyzer(files=files, entities=entities, relationships=relationships)

        # Walk starting from deep dependency: fn:db
        impact_db = analyzer.analyze_node("fn:db", max_depth=2)

        # Hop 1: method:auth (in auth.py)
        # Hop 2: api:login (in api.py)
        affected_files = impact_db["affected_files"]
        self.assertIn("auth.py", affected_files)
        self.assertIn("api.py", affected_files)

        affected_apis = impact_db["affected_apis"]
        self.assertIn("POST /login", affected_apis)

        # Risk rating: affected_apis >= 1 -> Medium
        self.assertEqual(impact_db["risk"], "Medium")

    def test_build_full_impact_index(self) -> None:
        files = [
            FileRecord(id="file:core.py", repo_id="r1", path="core.py", language="Python", size_bytes=50, lines=5, content_hash="h1")
        ]
        entities = [
            EntityRecord(id="fn:core", repo_id="r1", file_id="file:core.py", kind="Function", name="core_fn", start_line=1, end_line=5)
        ]
        analyzer = GraphImpactAnalyzer(files=files, entities=entities, relationships=[])
        index = analyzer.build_impact_index()

        self.assertIn("file:core.py", index)
        self.assertIn("fn:core", index)
        self.assertEqual(index["fn:core"]["risk"], "Low")


if __name__ == "__main__":
    unittest.main()


import tempfile
import unittest
from pathlib import Path

from codecompass.analyzer import analyze_with_treesitter
from codecompass.extractor import extract_file
from codecompass.resolver.scoped_resolver import ScopedResolver
from codecompass.storage.database import Database
from codecompass.storage.repositories import EntityDAL, RelationshipDAL


class ResolverTest(unittest.TestCase):
    def test_scoped_call_resolution_prevents_cross_contamination(self) -> None:
        """Verifies that calling a local function binds locally and DOES NOT link to an unrelated function in another file."""
        code_a = b"""
def run():
    return format_data()

def format_data():
    return 'data_a'
"""
        code_b = b"""
def execute():
    return format_data()

def format_data():
    return 'data_b'
"""
        parsed_a = extract_file("module_a.py", code_a, "Python")
        parsed_b = extract_file("module_b.py", code_b, "Python")

        resolver = ScopedResolver(repo_id="test_repo", parsed_files=[parsed_a, parsed_b])
        relationships = resolver.resolve_relationships()

        calls_from_run = [
            r for r in relationships
            if r.type == "CALLS" and r.source_id == [e.id for e in parsed_a.entities if e.name == "run"][0]
        ]
        self.assertEqual(len(calls_from_run), 1)

        # Must bind to module_a's format_data, NOT module_b's
        expected_target_id = [e.id for e in parsed_a.entities if e.name == "format_data"][0]
        forbidden_target_id = [e.id for e in parsed_b.entities if e.name == "format_data"][0]

        self.assertEqual(calls_from_run[0].target_id, expected_target_id)
        self.assertNotEqual(calls_from_run[0].target_id, forbidden_target_id)

    def test_imported_symbol_resolution(self) -> None:
        """Verifies that calling an imported function links to the target module's entity."""
        code_auth = b"""
def verify_token(token: str) -> bool:
    return True
"""
        code_api = b"""
from .auth import verify_token

def handle_request(tok: str):
    return verify_token(tok)
"""
        parsed_auth = extract_file("services/auth.py", code_auth, "Python")
        parsed_api = extract_file("services/api.py", code_api, "Python")

        resolver = ScopedResolver(repo_id="test_repo", parsed_files=[parsed_auth, parsed_api])
        relationships = resolver.resolve_relationships()

        handle_req_id = [e.id for e in parsed_api.entities if e.name == "handle_request"][0]
        verify_tok_id = [e.id for e in parsed_auth.entities if e.name == "verify_token"][0]

        calls = [r for r in relationships if r.type == "CALLS" and r.source_id == handle_req_id]
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].target_id, verify_tok_id)

    def test_full_treesitter_analysis_pipeline_with_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / ".codecompass" / "codecompass.db"

            # Create sample files
            (root / "app.py").write_text(
                "from services.user import UserService\n\ndef main():\n    return UserService().get()\n",
                encoding="utf-8",
            )
            services_dir = root / "services"
            services_dir.mkdir()
            (services_dir / "user.py").write_text(
                "class UserService:\n    def get(self):\n        return 'user'\n",
                encoding="utf-8",
            )

            db = Database(db_path)
            result = analyze_with_treesitter(root, db=db)

            self.assertEqual(result["stats"]["files"], 2)
            self.assertEqual(result["stats"]["classes"], 1)
            self.assertGreater(result["relationships_count"], 0)

            # Query database directly to confirm persistence
            entity_dal = EntityDAL(db)
            entities = entity_dal.get_entities_for_repo(result["repository"]["id"])
            entity_names = {e.name for e in entities}
            self.assertIn("UserService", entity_names)
            self.assertIn("main", entity_names)
            self.assertIn("get", entity_names)

            rel_dal = RelationshipDAL(db)
            rels = rel_dal.get_relationships_for_repo(result["repository"]["id"])
            rel_types = {r.type for r in rels}
            self.assertIn("CONTAINS", rel_types)
            self.assertIn("IMPORTS", rel_types)


if __name__ == "__main__":
    unittest.main()


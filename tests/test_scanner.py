import tempfile
import unittest
from pathlib import Path

from codecompass.cli import main
from codecompass.scanner.ignore import IgnoreRuleSet
from codecompass.scanner.walker import (
    compute_file_hash,
    detect_changes,
    is_test_file,
    walk_repository,
)
from codecompass.storage.database import Database
from codecompass.storage.repositories import FileDAL, RepositoryDAL


class ScannerTest(unittest.TestCase):
    def test_test_file_classification(self) -> None:
        self.assertTrue(is_test_file("tests/test_something.py"))
        self.assertTrue(is_test_file("test/unit_test.py"))
        self.assertTrue(is_test_file("__tests__/app.test.js"))
        self.assertTrue(is_test_file("src/components/Button.test.tsx"))
        self.assertTrue(is_test_file("src/service.spec.ts"))
        self.assertTrue(is_test_file("src/spec_helper.py"))
        self.assertFalse(is_test_file("src/testimony.py"))
        self.assertFalse(is_test_file("src/app.py"))
        self.assertFalse(is_test_file("src/components/Button.tsx"))

    def test_compute_file_hash_differs_on_content_change(self) -> None:
        h1 = compute_file_hash(b"hello world")
        h2 = compute_file_hash(b"hello world")
        h3 = compute_file_hash(b"hello world!")
        self.assertEqual(h1, h2)
        self.assertNotEqual(h1, h3)

    def test_ignore_rules_and_gitignore(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".gitignore").write_text("*.log\n/build/\n!keep.log\n", encoding="utf-8")

            rules = IgnoreRuleSet(root)

            # File matching *.log
            self.assertTrue(rules.is_ignored(root / "debug.log", is_dir=False))
            # Negated file
            self.assertFalse(rules.is_ignored(root / "keep.log", is_dir=False))
            # Root /build/ directory
            self.assertTrue(rules.is_ignored(root / "build", is_dir=True))
            # Default ignored directories
            self.assertTrue(rules.is_ignored(root / "node_modules", is_dir=True))
            self.assertTrue(rules.is_ignored(root / ".venv", is_dir=True))
            self.assertTrue(rules.is_ignored(root / ".git", is_dir=True))
            # Normal file
            self.assertFalse(rules.is_ignored(root / "src" / "index.ts", is_dir=False))

    def test_walk_repository_real_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            # Create source files
            src = root / "src"
            src.mkdir(parents=True)
            (src / "app.py").write_text("def run():\n    pass\n", encoding="utf-8")
            (src / "index.ts").write_text("console.log('hi');\n", encoding="utf-8")
            (src / "component.jsx").write_text("export default function Comp() {}\n", encoding="utf-8")

            # Create ignored directory
            node_modules = root / "node_modules" / "pkg"
            node_modules.mkdir(parents=True)
            (node_modules / "index.js").write_text("module.exports = {};", encoding="utf-8")

            # Create test file
            tests = root / "tests"
            tests.mkdir(parents=True)
            (tests / "test_app.py").write_text("def test_run(): pass\n", encoding="utf-8")

            scan = walk_repository(root)

            self.assertEqual(scan.stats["total_files"], 4)
            paths = {f.path for f in scan.files}
            self.assertIn("src/app.py", paths)
            self.assertIn("src/index.ts", paths)
            self.assertIn("src/component.jsx", paths)
            self.assertIn("tests/test_app.py", paths)
            self.assertNotIn("node_modules/pkg/index.js", paths)

            languages = scan.language_counts
            self.assertEqual(languages["Python"], 2)
            self.assertEqual(languages["TypeScript"], 1)
            self.assertEqual(languages["JavaScript"], 1)

            test_files = [f for f in scan.files if f.is_test]
            self.assertEqual(len(test_files), 1)
            self.assertEqual(test_files[0].path, "tests/test_app.py")

    def test_detect_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "file1.py").write_text("a = 1\n", encoding="utf-8")
            (root / "file2.py").write_text("b = 2\n", encoding="utf-8")

            scan1 = walk_repository(root)
            self.assertEqual(len(scan1.files), 2)

            # Modify file1.py, delete file2.py, add file3.py
            (root / "file1.py").write_text("a = 99\n", encoding="utf-8")
            (root / "file2.py").unlink()
            (root / "file3.py").write_text("c = 3\n", encoding="utf-8")

            scan2 = walk_repository(root)
            changes = detect_changes(scan1.files, scan2.files)

            self.assertTrue(changes.has_changes)
            self.assertEqual([f.path for f in changes.added], ["file3.py"])
            self.assertEqual([f.path for f in changes.modified], ["file1.py"])
            self.assertEqual(changes.deleted, ["file2.py"])
            self.assertEqual(len(changes.unchanged), 0)

    def test_cli_scan_integration(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "main.py").write_text("print('CodeCompass')\n", encoding="utf-8")
            db_file = root / ".codecompass" / "codecompass.db"

            exit_code = main(["scan", str(root)])
            self.assertEqual(exit_code, 0)
            self.assertTrue(db_file.exists())

            db = Database(db_file)
            repo_dal = RepositoryDAL(db)
            file_dal = FileDAL(db)

            repo = repo_dal.get_by_root(str(root))
            self.assertIsNotNone(repo)

            files = file_dal.get_files_for_repo(repo.id)
            self.assertEqual(len(files), 1)
            self.assertEqual(files[0].path, "main.py")
            self.assertEqual(files[0].language, "Python")


if __name__ == "__main__":
    unittest.main()


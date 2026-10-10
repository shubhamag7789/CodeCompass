import unittest
from pathlib import Path

from codecompass.analyzer import analyze_repository


class AnalyzerTest(unittest.TestCase):
    def test_python_fastapi_routes_and_imports(self) -> None:
        with self.subTest("fastapi analysis"):
            import tempfile

            with tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                app = root / "app.py"
                app.write_text(
                    "\n".join(
                        [
                            "from fastapi import FastAPI",
                            "from services.users import UserService",
                            "app = FastAPI()",
                            "",
                            "class AuthService:",
                            "    def login(self):",
                            "        return UserService()",
                            "",
                            "@app.post('/login')",
                            "def login():",
                            "    return AuthService().login()",
                        ]
                    ),
                    encoding="utf-8",
                )
                services = root / "services"
                services.mkdir()
                (services / "users.py").write_text("class UserService:\n    pass\n", encoding="utf-8")

                analysis = analyze_repository(root)

            self.assertEqual(analysis["summary"]["stats"]["files"], 2)
            self.assertIn(
                {"method": "POST", "path": "/login", "file": "app.py", "line": 10, "id": analysis["apis"][0]["id"]},
                analysis["apis"],
            )
            self.assertTrue(any(rel["type"] == "IMPORTS" and rel["source"] == "file:app.py" for rel in analysis["relationships"]))
            self.assertTrue(any(node["label"] == "AuthService" and node["type"] == "Class" for node in analysis["nodes"]))

    def test_javascript_express_route(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            index = root / "index.ts"
            index.write_text(
                "import express from 'express';\nconst app = express();\napp.get('/users', listUsers);\nfunction listUsers() {}\n",
                encoding="utf-8",
            )

            analysis = analyze_repository(root)

        self.assertEqual(analysis["apis"][0]["method"], "GET")
        self.assertEqual(analysis["apis"][0]["path"], "/users")
        self.assertIn("TypeScript", analysis["repository"]["supported_languages"])


if __name__ == "__main__":
    unittest.main()

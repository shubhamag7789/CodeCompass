"""Automated tests for CodeCompass Role-based Onboarding Generator."""

from __future__ import annotations

import unittest

from codecompass.onboarding.generator import RoleOnboardingGenerator
from codecompass.onboarding.models import RoleType


class OnboardingGeneratorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_analysis = {
            "repository": {"name": "TestPlatform", "path": "/mock/repo"},
            "files": [
                {"path": "server/src/server.ts", "lines": 60, "is_test": False},
                {"path": "server/src/routes/authRoutes.ts", "lines": 45, "is_test": False},
                {"path": "server/src/controllers/authController.ts", "lines": 120, "is_test": False},
                {"path": "server/src/models/userModel.ts", "lines": 80, "is_test": False},
                {"path": "client/src/App.tsx", "lines": 50, "is_test": False},
                {"path": "client/src/routes/AppRoutes.tsx", "lines": 35, "is_test": False},
                {"path": "client/src/pages/DashboardPage.tsx", "lines": 140, "is_test": False},
                {"path": "client/src/api/authClient.ts", "lines": 40, "is_test": False},
                {"path": "server/tests/test_auth.ts", "lines": 90, "is_test": True},
                {"path": "docker-compose.yml", "lines": 30, "is_test": False},
                {"path": "package.json", "lines": 45, "is_test": False},
            ],
            "apis": [
                {"method": "POST", "path": "/api/auth/login", "file": "server/src/routes/authRoutes.ts"},
                {"method": "POST", "path": "/api/auth/register", "file": "server/src/routes/authRoutes.ts"},
            ],
            "impact_index": {
                "file:server/src/models/userModel.ts": {
                    "path": "server/src/models/userModel.ts",
                    "risk": "High",
                    "affected_files": ["server/src/controllers/authController.ts", "server/src/server.ts"],
                },
                "file:client/src/App.tsx": {
                    "path": "client/src/App.tsx",
                    "risk": "Medium",
                    "affected_files": ["client/src/routes/AppRoutes.tsx"],
                },
            },
        }
        self.generator = RoleOnboardingGenerator(self.mock_analysis)

    def test_generate_backend_guide_contains_backend_files_only(self) -> None:
        guide = self.generator.generate(RoleType.BACKEND)
        self.assertEqual(guide.role, RoleType.BACKEND)
        self.assertIn("Backend", guide.title)
        self.assertTrue(len(guide.reading_path) > 0)

        # All reading path files must be backend files
        for step in guide.reading_path:
            self.assertTrue(
                "server" in step.file_path or "auth" in step.file_path,
                f"Unexpected non-backend file in backend guide: {step.file_path}",
            )

        # Key APIs present
        self.assertEqual(len(guide.important_apis), 2)
        # Test suites present
        self.assertIn("server/tests/test_auth.ts", guide.key_test_suites)

    def test_generate_frontend_guide_contains_frontend_files_only(self) -> None:
        guide = self.generator.generate(RoleType.FRONTEND)
        self.assertEqual(guide.role, RoleType.FRONTEND)
        self.assertIn("Frontend", guide.title)
        self.assertTrue(len(guide.reading_path) > 0)

        # All reading path files must be frontend files
        for step in guide.reading_path:
            self.assertTrue(
                "client" in step.file_path or step.file_path.endswith((".tsx", ".jsx")),
                f"Unexpected non-frontend file in frontend guide: {step.file_path}",
            )

    def test_generate_devops_qa_guide_focuses_on_tests_and_configs(self) -> None:
        guide = self.generator.generate(RoleType.DEVOPS_QA)
        self.assertEqual(guide.role, RoleType.DEVOPS_QA)
        self.assertIn("DevOps", guide.title)

        paths = [step.file_path for step in guide.reading_path]
        self.assertTrue(any("docker" in p or "package.json" in p for p in paths))
        self.assertTrue(any("test" in p for p in paths))

    def test_generate_all_returns_four_roles(self) -> None:
        all_guides = self.generator.generate_all()
        self.assertEqual(len(all_guides), 4)
        self.assertIn("backend", all_guides)
        self.assertIn("frontend", all_guides)
        self.assertIn("fullstack", all_guides)
        self.assertIn("devops_qa", all_guides)


if __name__ == "__main__":
    unittest.main()


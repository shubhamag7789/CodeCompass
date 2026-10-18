"""Automated unit tests for CodeCompass Progressive Graph API and Hierarchy traversal.

Ensures:
1. /api/graph/hierarchy returns structured hierarchical containment mappings.
2. Root node level 1 contains only top-level directories/files, not all nodes.
3. /api/graph/neighborhood returns real incoming and outgoing relationships.
4. No fabricated or phantom relationships exist.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from codecompass.server import CodeCompassHandler


class GraphApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)

        # Create a test analysis.json representing a realistic codebase
        self.analysis_data = {
            "repository": {"name": "TestRepo", "path": str(self.base_dir)},
            "nodes": [
                {"id": "repo:root", "type": "Repository", "label": "TestRepo", "path": ""},
                {"id": "dir:src", "type": "Directory", "label": "src", "path": "src"},
                {"id": "dir:tests", "type": "Directory", "label": "tests", "path": "tests"},
                {"id": "file:src/app.py", "type": "File", "label": "app.py", "path": "src/app.py"},
                {"id": "func:src/app.py:start_server", "type": "Function", "label": "start_server", "path": "src/app.py", "line": 10},
                {"id": "func:src/app.py:handle_request", "type": "Function", "label": "handle_request", "path": "src/app.py", "line": 25},
                {"id": "file:tests/test_app.py", "type": "File", "label": "test_app.py", "path": "tests/test_app.py"},
                {"id": "func:tests/test_app.py:test_start", "type": "Function", "label": "test_start", "path": "tests/test_app.py", "line": 5},
            ],
            "relationships": [
                # Hierarchy (CONTAINS)
                {"source": "repo:root", "type": "CONTAINS", "target": "dir:src"},
                {"source": "repo:root", "type": "CONTAINS", "target": "dir:tests"},
                {"source": "dir:src", "type": "CONTAINS", "target": "file:src/app.py"},
                {"source": "file:src/app.py", "type": "CONTAINS", "target": "func:src/app.py:start_server"},
                {"source": "file:src/app.py", "type": "CONTAINS", "target": "func:src/app.py:handle_request"},
                {"source": "dir:tests", "type": "CONTAINS", "target": "file:tests/test_app.py"},
                {"source": "file:tests/test_app.py", "type": "CONTAINS", "target": "func:tests/test_app.py:test_start"},
                # Call dependencies (CALLS)
                {"source": "func:src/app.py:start_server", "type": "CALLS", "target": "func:src/app.py:handle_request"},
                {"source": "func:tests/test_app.py:test_start", "type": "CALLS", "target": "func:src/app.py:start_server"},
            ],
        }

        self.analysis_path = self.base_dir / "analysis.json"
        self.analysis_path.write_text(json.dumps(self.analysis_data), encoding="utf-8")

        # Mock handler
        self.handler = CodeCompassHandler.__new__(CodeCompassHandler)
        self.handler.analysis_path = self.analysis_path
        self.handler._resolve_paths = MagicMock(return_value=(self.analysis_path, self.analysis_path, self.base_dir))

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_hierarchy_structure_and_level_1_containment(self) -> None:
        response_payload = {}
        def mock_json(payload, status=200):
            nonlocal response_payload
            response_payload = payload

        self.handler._json = mock_json
        self.handler._send_graph_hierarchy()

        self.assertIn("root_id", response_payload)
        self.assertEqual(response_payload["root_id"], "repo:root")

        children_map = response_payload.get("children_by_parent", {})
        # Level 1 must ONLY contain immediate top-level directories
        root_children = children_map.get("repo:root", [])
        self.assertEqual(len(root_children), 2)
        self.assertIn("dir:src", root_children)
        self.assertIn("dir:tests", root_children)

        # Children of src
        src_children = children_map.get("dir:src", [])
        self.assertEqual(src_children, ["file:src/app.py"])

        # Children of file:src/app.py
        file_children = children_map.get("file:src/app.py", [])
        self.assertEqual(len(file_children), 2)
        self.assertIn("func:src/app.py:start_server", file_children)
        self.assertIn("func:src/app.py:handle_request", file_children)

    def test_dependency_counts_exclude_containment(self) -> None:
        response_payload = {}
        self.handler._json = lambda payload, status=200: response_payload.update(payload)
        self.handler._send_graph_hierarchy()

        dep_counts = response_payload.get("dep_counts", {})
        # func:src/app.py:start_server has 1 incoming (from test_start) and 1 outgoing (to handle_request)
        start_counts = dep_counts.get("func:src/app.py:start_server", {"in": 0, "out": 0})
        self.assertEqual(start_counts["in"], 1)
        self.assertEqual(start_counts["out"], 1)

        # func:src/app.py:handle_request has 1 incoming and 0 outgoing
        handle_counts = dep_counts.get("func:src/app.py:handle_request", {"in": 0, "out": 0})
        self.assertEqual(handle_counts["in"], 1)
        self.assertEqual(handle_counts["out"], 0)

    def test_neighborhood_endpoint_separates_incoming_and_outgoing(self) -> None:
        response_payload = {}
        self.handler._json = lambda payload, status=200: response_payload.update(payload)
        self.handler._send_graph_neighborhood("func:src/app.py:start_server")

        self.assertIn("node", response_payload)
        self.assertEqual(response_payload["node"]["label"], "start_server")

        incoming = response_payload.get("incoming", [])
        outgoing = response_payload.get("outgoing", [])

        self.assertEqual(len(incoming), 1)
        self.assertEqual(incoming[0]["source_node"]["label"], "test_start")
        self.assertEqual(incoming[0]["rel"]["type"], "CALLS")

        self.assertEqual(len(outgoing), 1)
        self.assertEqual(outgoing[0]["target_node"]["label"], "handle_request")
        self.assertEqual(outgoing[0]["rel"]["type"], "CALLS")

    def test_neighborhood_returns_404_for_nonexistent_node(self) -> None:
        error_resp = {}
        def mock_json(payload, status=200):
            nonlocal error_resp
            error_resp = payload

        self.handler._json = mock_json
        self.handler._send_graph_neighborhood("nonexistent:node:123")
        self.assertIn("error", error_resp)


if __name__ == "__main__":
    unittest.main()


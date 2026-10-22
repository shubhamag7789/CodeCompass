"""Automated unit tests for CodeCompass Feature Flow Tracer."""

from __future__ import annotations

import unittest

from codecompass.tracing.flow_tracer import FeatureFlowTracer


class FlowTracerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_analysis = {
            "nodes": [
                {"id": "api:POST /api/auth/login", "type": "API", "label": "POST /api/auth/login", "path": "server/src/routes/auth.ts"},
                {"id": "func:authController.login", "type": "Function", "label": "login", "path": "server/src/controllers/auth.ts", "line": 20},
                {"id": "func:authService.authenticate", "type": "Function", "label": "authenticate", "path": "server/src/services/auth.ts", "line": 15},
                {"id": "func:userModel.findByEmail", "type": "Function", "label": "findByEmail", "path": "server/src/models/user.ts", "line": 30},
                {"id": "func:crypto.verifyPassword", "type": "Function", "label": "verifyPassword", "path": "server/src/utils/crypto.ts", "line": 10},
                # External dependency
                {"id": "ext:jsonwebtoken", "type": "ExternalDependency", "label": "jsonwebtoken", "path": ""},
            ],
            "relationships": [
                {"source": "api:POST /api/auth/login", "type": "CALLS", "target": "func:authController.login"},
                {"source": "func:authController.login", "type": "CALLS", "target": "func:authService.authenticate"},
                {"source": "func:authService.authenticate", "type": "CALLS", "target": "func:userModel.findByEmail"},
                {"source": "func:authService.authenticate", "type": "CALLS", "target": "func:crypto.verifyPassword"},
                {"source": "func:authService.authenticate", "type": "IMPORTS", "target": "ext:jsonwebtoken"},
            ],
            "apis": [
                {"method": "POST", "path": "/api/auth/login", "file": "server/src/routes/auth.ts"},
            ],
            "files": [
                {"path": "server/src/routes/auth.ts"},
                {"path": "server/src/controllers/auth.ts"},
                {"path": "server/src/services/auth.ts"},
                {"path": "server/src/models/user.ts"},
            ],
        }
        self.tracer = FeatureFlowTracer(self.mock_analysis)

    def test_discover_flows_includes_api_and_controllers(self) -> None:
        flows = self.tracer.discover_flows()
        self.assertTrue(len(flows) >= 1)
        self.assertEqual(flows[0]["name"], "POST /api/auth/login")

    def test_trace_flow_by_entrypoint_id(self) -> None:
        flow = self.tracer.trace_flow(entry_point_id="api:POST /api/auth/login")
        self.assertIsNotNone(flow)
        self.assertIn("login", flow.name.lower())
        self.assertEqual(len(flow.steps), 5)  # API -> Controller -> Service -> Model & Crypto (excluding ext:jsonwebtoken)

        step_labels = [s.label for s in flow.steps]
        self.assertEqual(step_labels[0], "POST /api/auth/login")
        self.assertEqual(step_labels[1], "login")
        self.assertEqual(step_labels[2], "authenticate")
        self.assertIn("findByEmail", step_labels)
        self.assertIn("verifyPassword", step_labels)

        # Mermaid output generated
        self.assertIn("sequenceDiagram", flow.mermaid_sequence)
        self.assertIn("flowchart TD", flow.mermaid_flowchart)

    def test_trace_flow_by_query_keyword(self) -> None:
        flow = self.tracer.trace_flow(query="auth login")
        self.assertIsNotNone(flow)
        self.assertEqual(flow.entry_point.label, "POST /api/auth/login")

    def test_trace_flow_handles_recursive_cycles_safely(self) -> None:
        # Create a cycle: A -> B -> C -> A
        cyclic_analysis = {
            "nodes": [
                {"id": "func:nodeA", "type": "Function", "label": "nodeA", "path": "a.ts"},
                {"id": "func:nodeB", "type": "Function", "label": "nodeB", "path": "b.ts"},
                {"id": "func:nodeC", "type": "Function", "label": "nodeC", "path": "c.ts"},
            ],
            "relationships": [
                {"source": "func:nodeA", "type": "CALLS", "target": "func:nodeB"},
                {"source": "func:nodeB", "type": "CALLS", "target": "func:nodeC"},
                {"source": "func:nodeC", "type": "CALLS", "target": "func:nodeA"},  # Cycle!
            ],
            "apis": [],
            "files": [],
        }
        cyclic_tracer = FeatureFlowTracer(cyclic_analysis)
        flow = cyclic_tracer.trace_flow(entry_point_id="func:nodeA")
        self.assertIsNotNone(flow)
        # Should terminate cleanly with exactly 3 steps, without getting stuck in infinite loop
        self.assertEqual(len(flow.steps), 3)


if __name__ == "__main__":
    unittest.main()


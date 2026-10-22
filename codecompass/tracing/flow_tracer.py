"""Feature Flow Tracer for CodeCompass.

Traces sequential execution paths through the codebase call graph, mapping API endpoints
or user-initiated features through routes, controllers, services, utilities, and data models.
"""

from __future__ import annotations

import re
from collections import defaultdict, deque
from typing import Any

from codecompass.tracing.models import ExecutionFlow, FlowStep


class FeatureFlowTracer:
    """Discovers and traces end-to-end execution flows across codebase symbols."""

    def __init__(self, analysis: dict[str, Any]) -> None:
        self.analysis = analysis
        self.nodes = analysis.get("nodes", [])
        self.nodes_by_id: dict[str, dict[str, Any]] = {n["id"]: n for n in self.nodes}
        self.relationships = analysis.get("relationships", [])
        self.apis = analysis.get("apis", [])
        self.files = analysis.get("files", [])

        # Build forward adjacency list for non-contains relationships (CALLS, IMPORTS, EXTENDS)
        self.outgoing_rels: dict[str, list[dict[str, str]]] = defaultdict(list)
        for r in self.relationships:
            if r.get("type") in {"CALLS", "IMPORTS", "EXTENDS"}:
                self.outgoing_rels[r["source"]].append(r)

    def discover_flows(self) -> list[dict[str, Any]]:
        """Discovers common traceable entry points across APIs and primary controllers."""
        flows: list[dict[str, Any]] = []

        # 1. API Endpoints
        for api in self.apis:
            method = api.get("method", "GET").upper()
            route_path = api.get("path", "")
            file_path = api.get("file", "")

            # Categorize flow by domain
            category = "Core System"
            fl = file_path.lower()
            if "auth" in fl or "guard" in fl:
                category = "Authentication & Security"
            elif "analytics" in fl:
                category = "Analytics & Insights"
            elif "interview" in fl:
                category = "Mock Interviews & AI"
            elif "resume" in fl:
                category = "Resume Intelligence"
            elif "user" in fl:
                category = "User Management"
            elif "link" in fl or "redirect" in fl:
                category = "Links & URL Redirection"
            elif "health" in fl:
                category = "Health & Diagnostics"
            elif "metric" in fl:
                category = "Metrics & Monitoring"

            flows.append({
                "id": f"api:{method} {route_path}",
                "name": f"{method} {route_path}",
                "category": category,
                "file": file_path,
                "method": method,
                "path": route_path,
                "description": f"HTTP {method} API endpoint defined in {file_path}",
            })

        # 2. Key controller / service functions
        for node in self.nodes:
            if node.get("type") in {"Function", "Method"} and any(
                term in (node.get("path") or "").lower()
                for term in ["controller", "service", "handler"]
            ):
                flows.append({
                    "id": node["id"],
                    "name": node.get("label", node["id"]),
                    "category": "Business Logic",
                    "file": node.get("path", ""),
                    "method": "FUNC",
                    "path": node.get("path", ""),
                    "description": f"Function execution in {node.get('path', '')}",
                })

        # Deduplicate
        seen = set()
        unique_flows = []
        for f in flows:
            if f["id"] not in seen:
                seen.add(f["id"])
                unique_flows.append(f)

        return unique_flows[:50]

    def trace_flow(
        self,
        entry_point_id: str | None = None,
        query: str | None = None,
        max_depth: int = 6,
    ) -> ExecutionFlow | None:
        """Traces execution path starting from an entry point or best-matched query."""
        entry_node = None

        if entry_point_id:
            # Direct match
            entry_node = self.nodes_by_id.get(entry_point_id)
            if not entry_node and entry_point_id.startswith("api:"):
                # Find matching API node
                raw = entry_point_id[4:].strip()
                for n in self.nodes:
                    if n.get("type") == "API" and raw.lower() in n.get("label", "").lower():
                        entry_node = n
                        break
        elif query:
            # Find best candidate by query keyword
            entry_node = self._find_entry_node_by_query(query)

        if not entry_node:
            # Fallback to first available API or Function
            for n in self.nodes:
                if n.get("type") in {"API", "Function"}:
                    entry_node = n
                    break

        if not entry_node:
            return None

        # Build execution flow
        return self._traverse_flow(entry_node, max_depth)

    def _find_entry_node_by_query(self, query: str) -> dict[str, Any] | None:
        q = query.lower().strip()
        tokens = re.findall(r"\w+", q)

        # 1. Check API endpoints first
        for node in self.nodes:
            if node.get("type") == "API":
                lbl = node.get("label", "").lower()
                if any(t in lbl for t in tokens):
                    return node

        # 2. Check functions / controllers
        best_node = None
        best_score = 0
        for node in self.nodes:
            if node.get("type") in {"Function", "Method", "Class"}:
                lbl = node.get("label", "").lower()
                path = (node.get("path") or "").lower()
                score = sum(2 for t in tokens if t in lbl) + sum(1 for t in tokens if t in path)
                if "controller" in path:
                    score += 2
                if "route" in path:
                    score += 2
                if score > best_score:
                    best_score = score
                    best_node = node

        return best_node

    def _traverse_flow(self, entry_node: dict[str, Any], max_depth: int) -> ExecutionFlow:
        visited: set[str] = {entry_node["id"]}
        queue: deque[tuple[dict[str, Any], int, str | None, str]] = deque([
            (entry_node, 1, None, "ENTRY_POINT")
        ])

        # Check if entry node has explicit CALLS/DISPATCHES targets in outgoing_rels
        explicit_targets = [
            r["target"]
            for r in self.outgoing_rels.get(entry_node["id"], [])
            if r["target"] in self.nodes_by_id
            and self.nodes_by_id[r["target"]].get("type") != "ExternalDependency"
        ]

        # If entry node is an API and has no direct outgoing calls, bridge through domain knowledge
        if entry_node.get("type") == "API" and not explicit_targets:
            self._bridge_api_flow(entry_node, queue, visited)
        elif entry_node.get("type") == "API" and explicit_targets:
            for rel in self.outgoing_rels.get(entry_node["id"], []):
                target_id = rel["target"]
                if target_id not in visited and target_id in self.nodes_by_id:
                    visited.add(target_id)
                    queue.append((self.nodes_by_id[target_id], 2, entry_node["id"], rel.get("type", "CALLS")))

        steps: list[FlowStep] = []
        step_number = 1

        while queue and step_number <= 25:
            current_node, depth, caller_id, rel_type = queue.popleft()

            # Categorize step role
            step_desc = self._describe_step(current_node, depth, rel_type)

            steps.append(
                FlowStep(
                    step_number=step_number,
                    node_id=current_node["id"],
                    label=current_node.get("label", current_node["id"]),
                    type=current_node.get("type", "Unknown"),
                    path=current_node.get("path", ""),
                    line=current_node.get("line"),
                    relationship_type=rel_type,
                    caller_node_id=caller_id,
                    description=step_desc,
                )
            )
            step_number += 1

            if depth >= max_depth:
                continue

            # Find next calls
            for rel in self.outgoing_rels.get(current_node["id"], []):
                target_id = rel["target"]
                if target_id not in visited and target_id in self.nodes_by_id:
                    visited.add(target_id)
                    target_node = self.nodes_by_id[target_id]
                    # Filter out purely external third-party dependencies from step sequence
                    if target_node.get("type") != "ExternalDependency":
                        queue.append((target_node, depth + 1, current_node["id"], rel.get("type", "CALLS")))

        involved_files = sorted(list({s.path for s in steps if s.path}))
        mermaid_seq = self._generate_mermaid_sequence(steps)
        mermaid_flow = self._generate_mermaid_flowchart(steps)

        entry_step = steps[0]
        flow_name = f"Execution Flow: {entry_node.get('label', entry_node['id'])}"

        return ExecutionFlow(
            flow_id=f"flow:{entry_node['id']}",
            name=flow_name,
            category="api_flow" if entry_node.get("type") == "API" else "feature_flow",
            entry_point=entry_step,
            steps=steps,
            involved_files=involved_files,
            mermaid_sequence=mermaid_seq,
            mermaid_flowchart=mermaid_flow,
        )

    def _bridge_api_flow(
        self,
        api_node: dict[str, Any],
        queue: deque[tuple[dict[str, Any], int, str | None, str]],
        visited: set[str],
    ) -> None:
        """Bridges API endpoint through its middlewares, controller handler, services, and models."""
        raw_label = api_node.get("label", "")
        method = (api_node.get("method") or raw_label.split()[0] if raw_label else "GET").upper()
        route_str = api_node.get("route") or (raw_label.split()[1] if len(raw_label.split()) > 1 else "")
        api_file = (api_node.get("file") or api_node.get("path") or "").lower()
        caller_id = api_node["id"]

        # 1. Middlewares: protect, limiter, validate, upload
        is_public = route_str in {"/health", "/login", "/register", "/refresh", "/forgot-password"} or "health" in route_str
        if not is_public:
            protect_node = next(
                (n for n in self.nodes if n.get("label") == "protect" or (n.get("type") in {"Function", "File"} and "authMiddleware" in (n.get("path") or ""))),
                None,
            )
            if protect_node and protect_node["id"] not in visited:
                visited.add(protect_node["id"])
                queue.append((protect_node, 2, caller_id, "MIDDLEWARE"))
                caller_id = protect_node["id"]

        if "auth" in api_file:
            limiter_node = next(
                (n for n in self.nodes if "limiter" in (n.get("path") or "").lower() or n.get("label") == "authLimiter"),
                None,
            )
            if limiter_node and limiter_node["id"] not in visited:
                visited.add(limiter_node["id"])
                queue.append((limiter_node, 2, caller_id, "MIDDLEWARE"))
                caller_id = limiter_node["id"]

        if "analyze" in route_str or "resume" in api_file and method == "POST":
            upload_node = next(
                (n for n in self.nodes if "upload" in (n.get("label") or "").lower() or "multer" in (n.get("path") or "").lower()),
                None,
            )
            if upload_node and upload_node["id"] not in visited:
                visited.add(upload_node["id"])
                queue.append((upload_node, 2, caller_id, "MIDDLEWARE"))
                caller_id = upload_node["id"]

        # 2. Controller Handler Matching
        route_norm = re.sub(r"[^a-zA-Z0-9]", "", route_str).lower()
        ctrl_node = None

        # First check if there is a method or function defined in the exact same controller file
        same_file_nodes = [
            n for n in self.nodes
            if n.get("type") in {"Function", "Method"} and (n.get("path") or "").lower() == api_file
        ]
        if same_file_nodes:
            api_line = api_node.get("line", 0)
            candidates = [n for n in same_file_nodes if (n.get("line") or 0) >= api_line]
            if candidates:
                candidates.sort(key=lambda n: n.get("line", 0))
                ctrl_node = candidates[0]
            else:
                same_file_nodes.sort(key=lambda n: abs((n.get("line") or 0) - api_line))
                ctrl_node = same_file_nodes[0]

        if not ctrl_node:
            # Exact mappings for PrepWise and standard REST APIs
            handler_map = {
                "dashboard": "getDashboard",
                "analytics": "getAnalytics",
                "roadmap": "getRoadmap" if method == "GET" else "generateRoadmap",
                "roadmapgenerate": "generateRoadmap",
                "login": "login",
                "register": "register",
                "logout": "logout",
                "me": "getMe",
                "refresh": "refreshAccessToken",
                "forgotpassword": "forgotPassword",
                "resetpasswordtoken": "resetPassword",
                "sessions": "listSessions" if method == "GET" else "createSession",
                "sessionsid": "getSession" if method == "GET" else "deleteSession",
                "sessionsidmessage": "sendMessage",
                "sessionsidend": "endSession",
                "analyze": "analyzeResumeUpload",
                "latest": "getLatestAnalysis",
                "profile": "getProfile" if method == "GET" else ("updateProfile" if method == "PATCH" else "deleteProfile"),
                "health": "health",
            }

            target_handler_name = handler_map.get(route_norm)
            if not target_handler_name:
                if method == "DELETE":
                    target_handler_name = "delete" + route_norm.capitalize()
                elif method == "POST":
                    target_handler_name = "create" + route_norm.capitalize()
                else:
                    target_handler_name = "get" + route_norm.capitalize()

            # Find matching controller function
            for n in self.nodes:
                if n.get("type") in {"Function", "Method"} and "controller" in (n.get("path") or "").lower():
                    nl = n.get("label", "")
                    if target_handler_name and (nl == target_handler_name or target_handler_name.lower() in nl.lower()):
                        ctrl_node = n
                        break
                    elif route_norm and route_norm in nl.lower():
                        ctrl_node = n
                        break

        if ctrl_node and ctrl_node["id"] not in visited:
            visited.add(ctrl_node["id"])
            queue.append((ctrl_node, 3, caller_id, "HANDLES"))
            caller_id = ctrl_node["id"]

        # Check for service calls from the controller
        if ctrl_node:
            stem = Path(api_file).stem.replace(".controller", "").replace("Routes", "").replace("Controller", "").lower()
            matching_services = [
                n for n in self.nodes
                if "service" in (n.get("path") or "").lower() and stem in (n.get("path") or "").lower()
            ]
            for s_node in matching_services[:2]:
                if s_node["id"] not in visited:
                    visited.add(s_node["id"])
                    queue.append((s_node, 4, caller_id, "DISPATCHES"))
                    caller_id = s_node["id"]

        # 3. Downstream Services & Models
        if "analytics" in api_file or "dashboard" in route_str or "roadmap" in route_str:
            svc_node = next(
                (n for n in self.nodes if n.get("label") in {"computeDashboardSnapshot", "computeUserAnalytics", "generatePrepRoadmap"} or (n.get("type") == "File" and "analyticsService" in n.get("label", ""))),
                None,
            )
            if svc_node and svc_node["id"] not in visited:
                visited.add(svc_node["id"])
                queue.append((svc_node, 4, caller_id, "DISPATCHES"))
                caller_id = svc_node["id"]

            model_node = next(
                (n for n in self.nodes if "PrepInsight" in n.get("label", "") or "PrepInsight" in (n.get("path") or "")),
                None,
            )
            if model_node and model_node["id"] not in visited:
                visited.add(model_node["id"])
                queue.append((model_node, 5, caller_id, "QUERIES"))

        elif "auth" in api_file or route_str in {"/login", "/register", "/me"}:
            user_model = next(
                (n for n in self.nodes if n.get("label") in {"User.js", "User"} and "model" in (n.get("path") or "").lower()),
                None,
            )
            if user_model and user_model["id"] not in visited:
                visited.add(user_model["id"])
                queue.append((user_model, 4, caller_id, "QUERIES"))

            token_node = next(
                (n for n in self.nodes if "generateToken" in (n.get("path") or "") or n.get("label") in {"generateAccessToken", "generateRefreshToken"}),
                None,
            )
            if token_node and token_node["id"] not in visited:
                visited.add(token_node["id"])
                queue.append((token_node, 5, caller_id, "DISPATCHES"))

        elif "interview" in api_file or "session" in route_str:
            sess_model = next(
                (n for n in self.nodes if "InterviewSession" in n.get("label", "") and "models" in (n.get("path") or "").lower()),
                None,
            ) or next((n for n in self.nodes if "InterviewSession" in n.get("label", "")), None)
            if sess_model and sess_model["id"] not in visited:
                visited.add(sess_model["id"])
                queue.append((sess_model, 4, caller_id, "QUERIES"))

            ai_node = next(
                (n for n in self.nodes if "evaluateAnswer" in n.get("label", "") or (n.get("type") == "File" and "aiService" in n.get("label", ""))),
                None,
            )
            if ai_node and ai_node["id"] not in visited:
                visited.add(ai_node["id"])
                queue.append((ai_node, 5, caller_id, "DISPATCHES"))

        elif "resume" in api_file or "analyze" in route_str:
            pdf_node = next(
                (n for n in self.nodes if "pdfParser" in (n.get("path") or "") or "extractResumeText" in n.get("label", "")),
                None,
            )
            if pdf_node and pdf_node["id"] not in visited:
                visited.add(pdf_node["id"])
                queue.append((pdf_node, 4, caller_id, "DISPATCHES"))

            resume_model = next(
                (n for n in self.nodes if "ResumeAnalysis" in n.get("label", "") and "models" in (n.get("path") or "").lower()),
                None,
            ) or next((n for n in self.nodes if "ResumeAnalysis" in n.get("label", "")), None)
            if resume_model and resume_model["id"] not in visited:
                visited.add(resume_model["id"])
                queue.append((resume_model, 5, caller_id, "QUERIES"))

        elif "user" in api_file or "profile" in route_str:
            user_model = next(
                (n for n in self.nodes if n.get("label") in {"User.js", "User"} and "model" in (n.get("path") or "").lower()),
                None,
            )
            if user_model and user_model["id"] not in visited:
                visited.add(user_model["id"])
                queue.append((user_model, 4, caller_id, "QUERIES"))

        # 4. Standard Response Formatter
        resp_node = next(
            (n for n in self.nodes if "ApiResponse" in n.get("label", "") or "ApiResponse" in (n.get("path") or "")),
            None,
        )
        if resp_node and resp_node["id"] not in visited:
            visited.add(resp_node["id"])
            queue.append((resp_node, 6, caller_id, "RESPONDS"))

    def _describe_step(self, node: dict[str, Any], depth: int, rel_type: str = "CALLS") -> str:
        ntype = node.get("type", "")
        path = (node.get("path") or "").lower()
        lbl = node.get("label", "")

        if rel_type == "ENTRY_POINT" or depth == 1:
            return f"Entry point invocation ({ntype}) receives incoming request at {node.get('path', 'root')}."
        if rel_type == "MIDDLEWARE" or "middleware" in path or lbl in {"protect", "authLimiter", "validate", "handleUpload"}:
            if "protect" in lbl or "auth" in lbl:
                return "Validates JWT Bearer authorization token and attaches authenticated user context to request."
            if "limit" in lbl:
                return "Evaluates client IP request rate against security throughput limits."
            if "validate" in lbl:
                return "Validates input request parameters and request payload against schema."
            if "upload" in lbl or "multer" in lbl:
                return "Parses incoming multipart/form-data payload and buffers uploaded documents."
            return f"Middleware layer executes request pre-processing in {lbl}."
        if "controller" in path:
            return f"Controller handler {lbl} processes request arguments and orchestrates domain workflow."
        if "service" in path:
            return f"Service layer executes business domain logic, computations, and data transformations."
        if "model" in path or "schema" in path or "db" in path:
            return f"Data model queries collection, enforces schema constraints, and executes database operations."
        if "util" in path or "helper" in path or "response" in path or "token" in path:
            if "response" in lbl.lower():
                return "Constructs standardized JSON response payload with HTTP status code and sends to client."
            return f"Utility helper {lbl} performs auxiliary cryptographic or parsing operations."
        return f"Invokes {ntype} '{lbl}' ({rel_type})."

    def _generate_mermaid_sequence(self, steps: list[FlowStep]) -> str:
        lines = ["sequenceDiagram", "autonumber"]
        participants = {}
        for s in steps:
            # Map path/file to participant
            file_name = s.path.split("/")[-1] if s.path else s.label
            clean_alias = re.sub(r"\W+", "_", file_name) or "System"
            if clean_alias not in participants:
                participants[clean_alias] = file_name
                lines.append(f"participant {clean_alias} as {file_name}")

        # Add interactions
        for i in range(len(steps) - 1):
            src_step = steps[i]
            tgt_step = steps[i + 1]

            src_file = re.sub(r"\W+", "_", src_step.path.split("/")[-1] if src_step.path else src_step.label) or "System"
            tgt_file = re.sub(r"\W+", "_", tgt_step.path.split("/")[-1] if tgt_step.path else tgt_step.label) or "System"

            call_label = tgt_step.label[:25]
            if src_file != tgt_file:
                lines.append(f"{src_file}->>{tgt_file}: {tgt_step.relationship_type} {call_label}()")
            else:
                lines.append(f"{src_file}->>{src_file}: {call_label}()")

        return "\n".join(lines)

    def _generate_mermaid_flowchart(self, steps: list[FlowStep]) -> str:
        lines = ["flowchart TD"]
        for i, s in enumerate(steps):
            node_key = f"step_{i+1}"
            safe_label = re.sub(r'["\n]', "", s.label)[:30]
            ntype = s.type
            lines.append(f'{node_key}["{i+1}. {safe_label} ({ntype})"]')

        for i in range(len(steps) - 1):
            lines.append(f"step_{i+1} -->|{steps[i+1].relationship_type}| step_{i+2}")

        return "\n".join(lines)

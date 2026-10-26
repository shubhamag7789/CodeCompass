"""Role-based onboarding generator for CodeCompass.

Generates targeted developer onboarding guides tailored to specific engineering roles
(Backend, Frontend, FullStack, DevOps/QA) using actual knowledge graph entities,
dependency topologies, API routes, and impact metrics.
"""

from __future__ import annotations

from typing import Any

from codecompass.onboarding.models import ReadingStep, RoleGuide, RoleType


class RoleOnboardingGenerator:
    """Generates persona-specific onboarding roadmaps from repository knowledge maps."""

    def __init__(self, analysis: dict[str, Any]) -> None:
        self.analysis = analysis
        self.nodes = analysis.get("nodes", [])
        self.nodes_by_id = {n["id"]: n for n in self.nodes}
        self.files = analysis.get("files", [])
        self.apis = analysis.get("apis", [])
        self.impact_index = analysis.get("impact_index", {})
        self.relationships = analysis.get("relationships", [])
        self.repo_name = analysis.get("repository", {}).get("name", "Repository")

    def generate_all(self) -> dict[str, dict[str, Any]]:
        """Generates guides for all supported roles."""
        return {
            RoleType.BACKEND.value: self.generate(RoleType.BACKEND).to_dict(),
            RoleType.FRONTEND.value: self.generate(RoleType.FRONTEND).to_dict(),
            RoleType.FULLSTACK.value: self.generate(RoleType.FULLSTACK).to_dict(),
            RoleType.DEVOPS_QA.value: self.generate(RoleType.DEVOPS_QA).to_dict(),
        }

    def generate(self, role: RoleType | str) -> RoleGuide:
        """Generates a complete guide for a single role."""
        if isinstance(role, str):
            try:
                role = RoleType(role.lower())
            except ValueError:
                role = RoleType.FULLSTACK

        if role == RoleType.BACKEND:
            return self._generate_backend()
        if role == RoleType.FRONTEND:
            return self._generate_frontend()
        if role == RoleType.DEVOPS_QA:
            return self._generate_devops_qa()
        return self._generate_fullstack()

    def _generate_backend(self) -> RoleGuide:
        backend_files = [f for f in self.files if self._is_backend_file(f.get("path", ""))]
        if not backend_files:
            backend_files = self.files

        reading_path: list[ReadingStep] = []

        # Day 1: Server Entry Point
        entry_candidates = [
            f for f in backend_files
            if any(name in f["path"].lower() for name in ["server", "main", "app", "index", "bootstrap"])
        ]
        entry = entry_candidates[0] if entry_candidates else (backend_files[0] if backend_files else None)
        if entry:
            reading_path.append(
                ReadingStep(
                    day=1,
                    title="Backend Entry Point & App Bootstrapping",
                    description=f"Inspect server setup, middleware registration, and port bindings in {entry['path']}.",
                    file_path=entry["path"],
                    category="entrypoint",
                )
            )

        # Day 1: Route Registration
        route_files = [f for f in backend_files if "route" in f["path"].lower() or "api" in f["path"].lower() or "controller" in f["path"].lower()]
        for rf in route_files[:2]:
            if not entry or rf["path"] != entry["path"]:
                reading_path.append(
                    ReadingStep(
                        day=1,
                        title=f"API Routing: {rf['path'].split('/')[-1]}",
                        description=f"Explore HTTP endpoint registrations and URL-to-handler bindings in {rf['path']}.",
                        file_path=rf["path"],
                        category="entrypoint",
                    )
                )

        # Day 2: Controllers & Business Logic
        ctrl_files = [f for f in backend_files if "controller" in f["path"].lower() or "service" in f["path"].lower() or "handler" in f["path"].lower()]
        for cf in ctrl_files[:3]:
            reading_path.append(
                ReadingStep(
                    day=2,
                    title=f"Core Domain Logic: {cf['path'].split('/')[-1]}",
                    description=f"Analyze request processing, payload validation, and service invocations in {cf['path']}.",
                    file_path=cf["path"],
                    category="core",
                )
            )

        # Day 3: Data Models & Persistence
        model_files = [f for f in backend_files if any(w in f["path"].lower() for w in ["model", "schema", "db", "prisma", "repository", "entity", "store"])]
        for mf in model_files[:2]:
            reading_path.append(
                ReadingStep(
                    day=3,
                    title=f"Data Persistence & Schema: {mf['path'].split('/')[-1]}",
                    description=f"Review data schema, relational constraints, and database queries in {mf['path']}.",
                    file_path=mf["path"],
                    category="data",
                )
            )

        self._ensure_three_days(reading_path, backend_files)

        # High risk items
        high_risk = self._find_high_risk(lambda p: self._is_backend_file(p))

        return RoleGuide(
            role=RoleType.BACKEND,
            title=f"{self.repo_name} — Backend Engineering Roadmap",
            mission="Deliver robust APIs, reliable business logic, database transactions, and secure authentication.",
            summary=f"The backend encompasses {len(backend_files)} files and {len(self.apis)} registered API endpoints. Your primary focus is on API routes, request controllers, and data storage.",
            reading_path=reading_path,
            key_entrypoints=[{"path": f["path"], "label": f["path"].split("/")[-1]} for f in (entry_candidates[:3] or backend_files[:3])],
            important_apis=self.apis[:10],
            key_test_suites=[f["path"] for f in self.files if f.get("is_test") and self._is_backend_file(f.get("path", ""))][:5],
            high_risk_components=high_risk[:4],
        )

    def _generate_frontend(self) -> RoleGuide:
        frontend_files = [f for f in self.files if self._is_frontend_file(f.get("path", ""))]
        if not frontend_files:
            frontend_files = self.files

        reading_path: list[ReadingStep] = []

        # Day 1: Root UI & Router
        root_candidates = [
            f for f in frontend_files
            if any(name in f["path"].lower() for name in ["app", "main", "index", "root", "router"])
        ]
        root = root_candidates[0] if root_candidates else (frontend_files[0] if frontend_files else None)
        if root:
            reading_path.append(
                ReadingStep(
                    day=1,
                    title="Client App Root & Navigation Shell",
                    description=f"Understand root component mounting, navigation providers, and theme wrappers in {root['path']}.",
                    file_path=root["path"],
                    category="entrypoint",
                )
            )

        # Day 1: Client Routes
        route_files = [f for f in frontend_files if "route" in f["path"].lower()]
        for rf in route_files[:1]:
            reading_path.append(
                ReadingStep(
                    day=1,
                    title="Page Navigation & Routing Tables",
                    description=f"Examine path definitions, protected routes, and page view mappings in {rf['path']}.",
                    file_path=rf["path"],
                    category="entrypoint",
                )
            )

        # Day 2: Core Views & Pages
        pages = [f for f in frontend_files if "page" in f["path"].lower() or "view" in f["path"].lower() or "screen" in f["path"].lower() or "component" in f["path"].lower()]
        for pf in pages[:3]:
            reading_path.append(
                ReadingStep(
                    day=2,
                    title=f"User Facing UI Component: {pf['path'].split('/')[-1]}",
                    description=f"Inspect UI layout, state management, and user interaction handlers in {pf['path']}.",
                    file_path=pf["path"],
                    category="core",
                )
            )

        # Day 3: API Client & State Management
        api_clients = [f for f in frontend_files if "api" in f["path"].lower() or "hook" in f["path"].lower() or "store" in f["path"].lower() or "service" in f["path"].lower()]
        for af in api_clients[:2]:
            reading_path.append(
                ReadingStep(
                    day=3,
                    title=f"Client Integration & Services: {af['path'].split('/')[-1]}",
                    description=f"Review data communication, state hooks, and client-side caching in {af['path']}.",
                    file_path=af["path"],
                    category="service",
                )
            )

        self._ensure_three_days(reading_path, frontend_files)

        high_risk = self._find_high_risk(lambda p: self._is_frontend_file(p))

        return RoleGuide(
            role=RoleType.FRONTEND,
            title=f"{self.repo_name} — Frontend Engineering Roadmap",
            mission="Craft responsive, accessible user interfaces, seamless page transitions, and responsive state flows.",
            summary=f"The frontend structure includes {len(frontend_files)} client files across components, views, and API connectors. Your focus is component architecture and user experience.",
            reading_path=reading_path,
            key_entrypoints=[{"path": f["path"], "label": f["path"].split("/")[-1]} for f in (root_candidates[:3] or frontend_files[:3])],
            important_apis=self.apis[:8],
            key_test_suites=[f["path"] for f in self.files if f.get("is_test") and self._is_frontend_file(f.get("path", ""))][:5],
            high_risk_components=high_risk[:4],
        )

    def _generate_fullstack(self) -> RoleGuide:
        reading_path: list[ReadingStep] = []

        # Client root
        client_roots = [f for f in self.files if self._is_frontend_file(f.get("path", "")) and any(n in f["path"].lower() for n in ["app", "index", "main"])]
        if client_roots:
            reading_path.append(
                ReadingStep(
                    day=1,
                    title="Client-Side Root App",
                    description=f"Examine client UI bootstrapping and navigation entry in {client_roots[0]['path']}.",
                    file_path=client_roots[0]["path"],
                    category="entrypoint",
                )
            )

        # Server root
        server_roots = [f for f in self.files if self._is_backend_file(f.get("path", "")) and any(n in f["path"].lower() for n in ["server", "main", "app", "index", "bootstrap"])]
        if server_roots:
            reading_path.append(
                ReadingStep(
                    day=1,
                    title="Server-Side App Bootstrapper",
                    description=f"Review backend API server initialisation and route mounting in {server_roots[0]['path']}.",
                    file_path=server_roots[0]["path"],
                    category="entrypoint",
                )
            )

        # End-to-end API glue
        api_files = [f for f in self.files if "api" in f["path"].lower() or "route" in f["path"].lower() or "controller" in f["path"].lower()]
        for af in api_files[:2]:
            reading_path.append(
                ReadingStep(
                    day=2,
                    title=f"API & Route Architecture: {af['path'].split('/')[-1]}",
                    description=f"Study data contract between client caller and backend handler in {af['path']}.",
                    file_path=af["path"],
                    category="core",
                )
            )

        # Core Domain
        controllers = [f for f in self.files if "controller" in f["path"].lower() or "service" in f["path"].lower() or "model" in f["path"].lower()]
        for cf in controllers[:2]:
            reading_path.append(
                ReadingStep(
                    day=3,
                    title=f"Business Logic & Data Model: {cf['path'].split('/')[-1]}",
                    description=f"Inspect domain logic and database operations in {cf['path']}.",
                    file_path=cf["path"],
                    category="service",
                )
            )

        self._ensure_three_days(reading_path, self.files)

        high_risk = self._find_high_risk(lambda _: True)

        all_entry_candidates = client_roots[:2] + server_roots[:2]
        if not all_entry_candidates and self.files:
            all_entry_candidates = self.files[:2]

        return RoleGuide(
            role=RoleType.FULLSTACK,
            title=f"{self.repo_name} — Full-Stack Architecture Guide",
            mission="Bridge user interaction with backend persistence, ensuring unified contracts, low latency, and robust end-to-end reliability.",
            summary=f"This codebase comprises {len(self.files)} files across client and server tiers with {len(self.apis)} REST/HTTP endpoints.",
            reading_path=reading_path,
            key_entrypoints=[{"path": f["path"], "label": f["path"].split("/")[-1]} for f in all_entry_candidates],
            important_apis=self.apis[:10],
            key_test_suites=[f["path"] for f in self.files if f.get("is_test")][:6],
            high_risk_components=high_risk[:4],
        )

    def _generate_devops_qa(self) -> RoleGuide:
        devops_files = [f for f in self.files if self._is_devops_file(f.get("path", "")) or f.get("is_test")]
        reading_path: list[ReadingStep] = []

        # Day 1: Build & Config
        config_files = [f for f in self.files if any(n in f["path"].lower() for n in ["package", "pyproject", "docker", "makefile", ".env", "tsconfig", "config", "module"])]
        for cf in config_files[:3]:
            reading_path.append(
                ReadingStep(
                    day=1,
                    title=f"Build & Configuration: {cf['path'].split('/')[-1]}",
                    description=f"Examine project dependencies, build scripts, and runtime environment specifications in {cf['path']}.",
                    file_path=cf["path"],
                    category="entrypoint",
                )
            )

        # Day 2: Test Suites
        test_files = [f for f in self.files if f.get("is_test")]
        for tf in test_files[:3]:
            reading_path.append(
                ReadingStep(
                    day=2,
                    title=f"Automated Test Suite: {tf['path'].split('/')[-1]}",
                    description=f"Analyze assertions, mocked dependencies, and integration fixtures in {tf['path']}.",
                    file_path=tf["path"],
                    category="test",
                )
            )

        # Day 3: CI/CD Workflows & Infrastructure
        ci_files = [f for f in self.files if any(w in f["path"].lower() for w in [".github", "workflow", "ci", "cd", "script", "seed"])]
        for cf in ci_files[:2]:
            reading_path.append(
                ReadingStep(
                    day=3,
                    title=f"DevOps & Infrastructure Script: {cf['path'].split('/')[-1]}",
                    description=f"Review CI build pipelines, automated checks, and maintenance scripts in {cf['path']}.",
                    file_path=cf["path"],
                    category="service",
                )
            )

        self._ensure_three_days(reading_path, self.files)

        high_risk = self._find_high_risk(lambda _: True)

        return RoleGuide(
            role=RoleType.DEVOPS_QA,
            title=f"{self.repo_name} — DevOps & QA Verification Guide",
            mission="Maintain deployment pipelines, build reproducibility, automated test coverage, and blast-radius prevention.",
            summary=f"Identified {len(test_files)} test suites and build/runtime configuration files. Monitor highest-risk impact nodes prior to merges.",
            reading_path=reading_path,
            key_entrypoints=[{"path": f["path"], "label": f["path"].split("/")[-1]} for f in (config_files[:3] or self.files[:3])],
            important_apis=self.apis[:5],
            key_test_suites=[f["path"] for f in test_files][:8],
            high_risk_components=high_risk[:5],
        )

    def _find_high_risk(self, path_filter) -> list[dict[str, Any]]:
        results = []
        for node_id, item in self.impact_index.items():
            path = item.get("path") or ""
            if path and not path_filter(path):
                continue
            if item.get("risk") in {"High", "Medium"}:
                results.append({
                    "id": node_id,
                    "label": item.get("label", node_id),
                    "path": path,
                    "risk": item.get("risk"),
                    "affected_files_count": len(item.get("affected_files", [])),
                })
        results.sort(key=lambda x: -x["affected_files_count"])
        return results

    def _ensure_three_days(self, reading_path: list[ReadingStep], pool_files: list[dict[str, Any]]) -> None:
        """Guarantees that Day 1, Day 2, and Day 3 always have at least one onboarding reading step."""
        if not pool_files:
            return

        used_paths = {s.file_path for s in reading_path}
        available = [f for f in pool_files if f.get("path") not in used_paths]

        days_present = {s.day for s in reading_path}

        for day_num, day_title, day_cat in [
            (1, "Core System Bootstrapping", "entrypoint"),
            (2, "Architecture & Service Logic", "core"),
            (3, "Persistence & Verification", "service"),
        ]:
            if day_num not in days_present:
                target_file = available.pop(0) if available else pool_files[min(day_num - 1, len(pool_files) - 1)]
                p = target_file.get("path", "")
                reading_path.append(
                    ReadingStep(
                        day=day_num,
                        title=f"{day_title}: {p.split('/')[-1]}",
                        description=f"Review code architecture, structure, and conventions in {p}.",
                        file_path=p,
                        category=day_cat,
                    )
                )
        reading_path.sort(key=lambda s: s.day)

    @staticmethod
    def _is_backend_file(path: str) -> bool:
        p = path.lower().replace("\\", "/")
        if "client/" in p or "frontend/" in p or "web/" in p:
            return False
        return any(
            token in p
            for token in [
                "server", "backend", "controller", "route", "model", "service",
                "middleware", "database", "db", "prisma", "api/", "apps/api", "src/api"
            ]
        ) or p.endswith((".py", ".go", ".rs", ".java", ".ts", ".js"))

    @staticmethod
    def _is_frontend_file(path: str) -> bool:
        p = path.lower().replace("\\", "/")
        if "server" in p or "backend" in p or "apps/api" in p:
            return False
        return any(
            token in p
            for token in ["client", "frontend", "component", "page", "view", "screen", "ui/", "style", "public/"]
        ) or p.endswith((".jsx", ".tsx", ".vue", ".svelte", ".html", ".css"))

    @staticmethod
    def _is_devops_file(path: str) -> bool:
        p = path.lower()
        return any(
            token in p
            for token in ["docker", "k8s", "kubernetes", ".github", "ci", "cd", "makefile", "compose", "jenkins", "terraform"]
        )


from __future__ import annotations

import json
import mimetypes
import os
import re
import shutil
import subprocess
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from codecompass.analyzer import analyze_repository, write_analysis
from codecompass.assistant import answer_question
from codecompass.auth.manager import AuthManager
from codecompass.conversation import ConversationManager, chat_answer
from codecompass.integrations import get_llm_provider, load_dotenv
from codecompass.retrieval import build_index, default_index_path, load_index, write_index
from codecompass.onboarding.generator import RoleOnboardingGenerator
from codecompass.tracing.flow_tracer import FeatureFlowTracer

load_dotenv()

STATIC_DIR = Path(__file__).parent / "static"
BASE_STORAGE_DIR = Path(".codecompass")
REGISTRY_FILE = BASE_STORAGE_DIR / "registry.json"
WORKSPACES_DIR = BASE_STORAGE_DIR / "workspaces"
REPOS_DIR = BASE_STORAGE_DIR / "repositories"
DB_PATH = BASE_STORAGE_DIR / "codecompass.db"


def _get_database():
    try:
        from codecompass.storage.database import Database
        _ensure_dirs()
        return Database(str(DB_PATH))
    except Exception:
        return None


def _ensure_dirs() -> None:
    BASE_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)
    REPOS_DIR.mkdir(parents=True, exist_ok=True)


def _load_registry() -> dict:
    _ensure_dirs()
    if not REGISTRY_FILE.exists():
        default_registry = {"active_repo_id": "default", "repositories": {}}
        REGISTRY_FILE.write_text(json.dumps(default_registry, indent=2), encoding="utf-8")
        return default_registry
    try:
        return json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"active_repo_id": "default", "repositories": {}}


def _save_registry(registry: dict) -> None:
    _ensure_dirs()
    REGISTRY_FILE.write_text(json.dumps(registry, indent=2), encoding="utf-8")


def _is_git_url(path_or_url: str) -> bool:
    parsed = urlparse(path_or_url.strip())
    return parsed.scheme in {"http", "https", "git"} and bool(parsed.netloc)


def _clone_git_repo(url: str) -> Path:
    _ensure_dirs()
    git = shutil.which("git")
    if not git:
        raise RuntimeError("Git is required on PATH to clone GitHub repositories.")

    name = re.sub(r"[^a-zA-Z0-9_-]", "_", url.rstrip("/").split("/")[-1].removesuffix(".git")) or "repo"
    dest = WORKSPACES_DIR / name

    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"

    try:
        if dest.exists() and (dest / ".git").exists():
            subprocess.run([git, "-C", str(dest), "pull", "--ff-only"], capture_output=True, text=True, timeout=30, env=env)
        else:
            if dest.exists():
                shutil.rmtree(dest, ignore_errors=True)
            res = subprocess.run([git, "clone", "--depth", "1", url, str(dest)], capture_output=True, text=True, timeout=45, env=env)
            if res.returncode != 0:
                raise RuntimeError(f"Git clone failed: {res.stderr.strip() or 'Unknown error'}")
    except subprocess.TimeoutExpired:
        raise RuntimeError("Git clone timed out after 45 seconds. Verify the repository link is public and accessible.")
    return dest


class CodeCompassHandler(BaseHTTPRequestHandler):
    analysis_path = BASE_STORAGE_DIR / "analysis.json"
    _db = _get_database()
    _auth = AuthManager(_db) if _db else None
    conversations = ConversationManager(db=_db)  # shared across all requests in this process

    def _get_authenticated_user(self) -> dict | None:
        if not self._auth:
            return None
        auth_header = self.headers.get("Authorization", "")
        token = ""
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        elif "X-Auth-Token" in self.headers:
            token = self.headers["X-Auth-Token"].strip()
        if token:
            return self._auth.authenticate_token(token)
        return None

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Auth-Token")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        if parsed.path == "/api/auth/me":
            self._send_auth_me()
            return
        if parsed.path == "/api/auth/security-settings":
            self._send_security_settings()
            return
        if parsed.path == "/api/ai/status":
            self._send_ai_status()
            return

        if parsed.path == "/api/repositories":
            self._send_repositories()
            return
        if parsed.path == "/api/analysis":
            repo_id = query.get("repo", [""])[0]
            self._send_analysis(repo_id)
            return
        if parsed.path == "/api/impact":
            node_id = query.get("id", [""])[0]
            repo_id = query.get("repo", [""])[0]
            self._send_impact(node_id, repo_id)
            return
        if parsed.path == "/api/file":
            file_path = query.get("path", [""])[0]
            repo_id = query.get("repo", [""])[0]
            self._send_file_content(file_path, repo_id)
            return
        if parsed.path == "/api/filetree":
            repo_id = query.get("repo", [""])[0]
            self._send_file_tree(repo_id)
            return
        if parsed.path == "/api/graph/hierarchy":
            repo_id = query.get("repo", [""])[0]
            self._send_graph_hierarchy(repo_id)
            return
        if parsed.path == "/api/graph/neighborhood":
            node_id = query.get("id", [""])[0]
            repo_id = query.get("repo", [""])[0]
            self._send_graph_neighborhood(node_id, repo_id)
            return
        if parsed.path == "/api/onboarding":
            repo_id = query.get("repo", [""])[0]
            role = query.get("role", [""])[0]
            self._send_onboarding(repo_id, role)
            return
        if parsed.path == "/api/flow/discover":
            repo_id = query.get("repo", [""])[0]
            self._send_flow_discover(repo_id)
            return
        if parsed.path == "/api/flow/trace":
            repo_id = query.get("repo", [""])[0]
            entry_id = query.get("id", [""])[0]
            trace_q = query.get("query", [""])[0]
            self._send_flow_trace(repo_id, entry_id, trace_q)
            return
        self._send_static(parsed.path)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/auth/register":
            self._handle_auth_register()
            return
        if parsed.path == "/api/auth/login":
            self._handle_auth_login()
            return
        if parsed.path == "/api/auth/logout":
            self._handle_auth_logout()
            return
        if parsed.path in {"/api/auth/forgot-password", "/api/auth/recovery-info"}:
            self._handle_auth_forgot_password()
            return
        if parsed.path == "/api/auth/reset-password":
            self._handle_auth_reset_password()
            return
        if parsed.path == "/api/auth/security-settings":
            self._handle_update_security_settings()
            return
        if parsed.path == "/api/analyze":
            self._handle_analyze()
            return
        if parsed.path == "/api/switch-repo":
            self._handle_switch_repo()
            return
        if parsed.path == "/api/repositories/delete":
            self._handle_delete_repo()
            return
        if parsed.path == "/api/ask":
            self._handle_ask()
            return
        if parsed.path == "/api/chat":
            self._handle_chat()
            return
        self.send_error(404)

    def do_DELETE(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path == "/api/repositories":
            repo_id = query.get("id", [""])[0]
            self._delete_repo_by_id(repo_id)
            return
        self.send_error(404)

    def _resolve_paths(self, repo_id: str | None = None) -> tuple[Path, Path, Path]:
        """Returns (analysis_path, index_path, root_dir) for given or active repo."""
        registry = _load_registry()
        user = self._get_authenticated_user()
        user_active = self._auth.get_active_repository(user["id"]) if (user and self._auth) else None

        # If user is authenticated but has 0 repositories, do not fallback to other users' repos
        if user and self._auth and not repo_id:
            user_repos = self._auth.get_user_repositories(user["id"])
            if not user_repos:
                return Path(".codecompass/nonexistent/analysis.json"), Path(".codecompass/nonexistent/index.json"), Path(".")

        rid = repo_id or user_active or registry.get("active_repo_id") or "default"
        repo_meta = registry.get("repositories", {}).get(rid)

        if repo_meta:
            root_path = Path(repo_meta.get("root_path", ".")).resolve()
            a_path = Path(repo_meta.get("analysis_file") or (REPOS_DIR / rid / "analysis.json"))
            i_path = Path(repo_meta.get("index_file") or (REPOS_DIR / rid / "index.json"))

            if a_path.exists():
                return a_path, i_path, root_path

            # If not yet analyzed but root directory exists, analyze it now on-demand
            if root_path.exists() and root_path.is_dir():
                a_path.parent.mkdir(parents=True, exist_ok=True)
                analysis = analyze_repository(root_path)
                write_analysis(analysis, a_path)
                write_index(build_index(root_path), i_path)
                repo_meta["analysis_file"] = str(a_path)
                repo_meta["index_file"] = str(i_path)
                repo_meta["stats"] = analysis.get("summary", {}).get("stats", {})
                repo_meta["headline"] = analysis.get("summary", {}).get("headline", "")
                registry["repositories"][rid] = repo_meta
                _save_registry(registry)
                return a_path, i_path, root_path

        # If fallback analysis exists in .codecompass
        fallback_analysis = BASE_STORAGE_DIR / "analysis.json"
        if fallback_analysis.exists():
            return fallback_analysis, default_index_path(fallback_analysis), Path(".").resolve()

        # Generate on-demand analysis for current working directory
        cwd = Path(".").resolve()
        fallback_analysis.parent.mkdir(parents=True, exist_ok=True)
        analysis = analyze_repository(cwd)
        write_analysis(analysis, fallback_analysis)
        write_index(build_index(cwd), default_index_path(fallback_analysis))
        return fallback_analysis, default_index_path(fallback_analysis), cwd

    def _handle_analyze(self) -> None:
        try:
            payload = self._read_json()
            raw_target = (payload.get("path") or ".").strip()
            is_git = _is_git_url(raw_target)

            if is_git:
                local_root = _clone_git_repo(raw_target)
                repo_name = local_root.name
            else:
                local_root = Path(raw_target).resolve()
                if not local_root.exists():
                    raise FileNotFoundError(f"Local path does not exist: {local_root}")
                repo_name = local_root.name or "repository"

            # Create distinct directory for this repository's artifacts
            safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", repo_name).lower()
            repo_artifact_dir = REPOS_DIR / safe_id
            repo_artifact_dir.mkdir(parents=True, exist_ok=True)

            a_path = repo_artifact_dir / "analysis.json"
            i_path = repo_artifact_dir / "index.json"

            # Run analysis and build search index
            analysis = analyze_repository(local_root)
            write_analysis(analysis, a_path)
            write_index(build_index(local_root), i_path)

            # Update multi-repo registry
            registry = _load_registry()
            registry["active_repo_id"] = safe_id
            registry["repositories"][safe_id] = {
                "id": safe_id,
                "name": repo_name,
                "root_path": str(local_root),
                "source": "github" if is_git else "local",
                "source_url": raw_target if is_git else None,
                "analysis_file": str(a_path),
                "index_file": str(i_path),
                "stats": analysis.get("summary", {}).get("stats", {}),
                "headline": analysis.get("summary", {}).get("headline", ""),
            }
            _save_registry(registry)

            # Associate repository with authenticated user
            user = self._get_authenticated_user()
            if user and self._auth:
                self._auth.add_user_repository(user["id"], safe_id, is_active=True)

            # Reset conversation for new repo
            self.conversations = ConversationManager(db=self._db)

            response_data = dict(analysis)
            response_data["repo_id"] = safe_id
            response_data["active_repo_id"] = safe_id
            self._json(response_data)
        except Exception as exc:
            self._json({"error": str(exc)}, status=400)

    def _handle_switch_repo(self) -> None:
        try:
            payload = self._read_json()
            repo_id = payload.get("repo_id")
            registry = _load_registry()
            if repo_id not in registry.get("repositories", {}):
                self._json({"error": f"Repository '{repo_id}' not found."}, status=404)
                return
            registry["active_repo_id"] = repo_id
            _save_registry(registry)

            user = self._get_authenticated_user()
            if user and self._auth:
                self._auth.set_active_repository(user["id"], repo_id)

            self._json({"status": "ok", "active_repo_id": repo_id})
        except Exception as exc:
            self._json({"error": str(exc)}, status=400)

    def _delete_repo_by_id(self, repo_id: str) -> None:
        if not repo_id:
            self._json({"error": "Repository ID is required."}, status=400)
            return

        registry = _load_registry()
        repos = registry.get("repositories", {})
        if repo_id not in repos:
            self._json({"error": f"Repository '{repo_id}' not found."}, status=404)
            return

        user = self._get_authenticated_user()
        if user and self._auth:
            self._auth.remove_user_repository(user["id"], repo_id)

        # Delete artifact directory if present
        repo_artifact_dir = REPOS_DIR / repo_id
        if repo_artifact_dir.exists():
            shutil.rmtree(repo_artifact_dir, ignore_errors=True)

        # Delete from SQLite database
        if self._db is not None:
            try:
                with self._db.transaction() as conn:
                    conn.execute("DELETE FROM repositories WHERE id = ?", (repo_id,))
            except Exception:
                pass

        # Delete from registry
        del repos[repo_id]

        # Reassign active repo if needed
        active_id = registry.get("active_repo_id")
        if active_id == repo_id:
            if user and self._auth:
                active_id = self._auth.get_active_repository(user["id"]) or (next(iter(repos.keys())) if repos else "default")
            else:
                active_id = next(iter(repos.keys())) if repos else "default"
            registry["active_repo_id"] = active_id

        _save_registry(registry)
        
        user_repo_list = list(repos.values())
        if user and self._auth:
            user_repo_ids = set(self._auth.get_user_repositories(user["id"]))
            user_repo_list = [r for r in user_repo_list if r["id"] in user_repo_ids]

        self._json({
            "status": "ok",
            "active_repo_id": active_id,
            "repositories": user_repo_list,
        })

    def _handle_delete_repo(self) -> None:
        try:
            payload = self._read_json()
            repo_id = payload.get("repo_id")
            self._delete_repo_by_id(repo_id)
        except Exception as exc:
            self._json({"error": str(exc)}, status=400)

    def _send_auth_me(self) -> None:
        user = self._get_authenticated_user()
        if not user:
            self._json({"error": "Unauthorized"}, status=401)
            return
        self._json({"user": user})

    def _handle_auth_register(self) -> None:
        if not self._auth:
            self._json({"error": "Authentication database not available"}, status=500)
            return
        try:
            payload = self._read_json()
            email = payload.get("email", "")
            password = payload.get("password", "")
            name = payload.get("name", "")
            security_question = payload.get("security_question")
            security_answer = payload.get("security_answer")
            recovery_passphrase = payload.get("recovery_passphrase")
            res = self._auth.register(
                email=email,
                password=password,
                name=name,
                security_question=security_question,
                security_answer=security_answer,
                recovery_passphrase=recovery_passphrase,
            )

            # In production, new user accounts start with a clean blank workspace (0 repositories).
            # They will never see any other user's projects.
            self._json({
                "status": "ok",
                "token": res["token"],
                "user": res["user"],
                "security_question": res.get("security_question"),
                "recovery_passphrase": res.get("recovery_passphrase"),
            })
        except Exception as exc:
            self._json({"error": str(exc)}, status=400)

    def _handle_auth_login(self) -> None:
        if not self._auth:
            self._json({"error": "Authentication database not available"}, status=500)
            return
        try:
            payload = self._read_json()
            email = payload.get("email", "")
            password = payload.get("password", "")
            res = self._auth.login(email, password)
            self._json({"status": "ok", "token": res["token"], "user": res["user"]})
        except Exception as exc:
            self._json({"error": str(exc)}, status=400)

    def _handle_auth_logout(self) -> None:
        auth_header = self.headers.get("Authorization", "")
        token = auth_header.removeprefix("Bearer ").strip() if auth_header.startswith("Bearer ") else self.headers.get("X-Auth-Token", "")
        if self._auth and token:
            self._auth.logout(token)
        self._json({"status": "ok"})

    def _handle_auth_forgot_password(self) -> None:
        if not self._auth:
            self._json({"error": "Authentication database not available"}, status=500)
            return
        try:
            payload = self._read_json()
            email = payload.get("email", "")
            # Request password reset code (fallback and test support)
            reset_res = self._auth.request_password_reset(email)
            # Retrieve security question & recovery passphrase info
            try:
                rec_info = self._auth.get_recovery_info(email)
            except Exception:
                rec_info = {
                    "has_security_question": False,
                    "has_recovery_passphrase": False,
                    "security_question": None,
                }
            merged = {**reset_res, **rec_info}
            self._json(merged)
        except Exception as exc:
            self._json({"error": str(exc)}, status=400)

    def _handle_auth_reset_password(self) -> None:
        if not self._auth:
            self._json({"error": "Authentication database not available"}, status=500)
            return
        try:
            payload = self._read_json()
            email = payload.get("email", "")
            new_password = payload.get("new_password", "")
            code = payload.get("code")
            security_answer = payload.get("security_answer")
            recovery_passphrase = payload.get("recovery_passphrase")
            security_question = payload.get("security_question")

            if security_answer or recovery_passphrase or (not code and security_question):
                res = self._auth.reset_password_with_security(
                    email=email,
                    new_password=new_password,
                    security_answer=security_answer,
                    recovery_passphrase=recovery_passphrase,
                    security_question=security_question,
                )
            elif code:
                res = self._auth.reset_password_with_code(email, code, new_password)
            else:
                res = self._auth.reset_password_with_security(
                    email=email,
                    new_password=new_password,
                    security_answer=security_answer,
                    recovery_passphrase=recovery_passphrase,
                    security_question=security_question,
                )
            self._json(res)
        except Exception as exc:
            self._json({"error": str(exc)}, status=400)

    def _send_security_settings(self) -> None:
        user = self._get_authenticated_user()
        if not user or not self._auth:
            self._json({"error": "Unauthorized"}, status=401)
            return
        try:
            settings = self._auth.get_user_security_settings(user["id"])
            self._json({"status": "ok", **settings})
        except Exception as exc:
            self._json({"error": str(exc)}, status=400)

    def _handle_update_security_settings(self) -> None:
        user = self._get_authenticated_user()
        if not user or not self._auth:
            self._json({"error": "Unauthorized"}, status=401)
            return
        try:
            payload = self._read_json()
            sec_q = payload.get("security_question", "")
            sec_ans = payload.get("security_answer", "")
            rec_phrase = payload.get("recovery_passphrase")
            res = self._auth.update_security_settings(
                user_id=user["id"],
                security_question=sec_q,
                security_answer=sec_ans,
                recovery_passphrase=rec_phrase,
            )
            self._json(res)
        except Exception as exc:
            self._json({"error": str(exc)}, status=400)

    def _send_repositories(self) -> None:
        registry = _load_registry()
        user = self._get_authenticated_user()
        all_repos_map = registry.get("repositories", {})

        # Sync latest stats and headline from analysis files
        for r_id, r in all_repos_map.items():
            a_path = Path(r.get("analysis_file") or (REPOS_DIR / r_id / "analysis.json"))
            if a_path.exists():
                try:
                    data = json.loads(a_path.read_text(encoding="utf-8"))
                    r["stats"] = data.get("summary", {}).get("stats", r.get("stats", {}))
                    r["headline"] = data.get("summary", {}).get("headline", r.get("headline", ""))
                    registry["repositories"][r_id]["stats"] = r["stats"]
                    registry["repositories"][r_id]["headline"] = r["headline"]
                except Exception:
                    pass
        _save_registry(registry)

        if user and self._auth:
            user_repo_ids = self._auth.get_user_repositories(user["id"])
            user_repos = [all_repos_map[rid] for rid in user_repo_ids if rid in all_repos_map]
            active_id = self._auth.get_active_repository(user["id"]) or (user_repos[0]["id"] if user_repos else "")
            self._json({"active_repo_id": active_id, "repositories": user_repos})
            return

        # Fallback for general access
        active_id = registry.get("active_repo_id") or "default"
        repos = list(all_repos_map.values())
        self._json({"active_repo_id": active_id, "repositories": repos})

    def _send_analysis(self, repo_id: str = "") -> None:
        a_path, _, _ = self._resolve_paths(repo_id if repo_id else None)
        if not a_path.exists():
            self._json({"error": f"No analysis found. Import or analyze a repository first."}, status=404)
            return
        data = json.loads(a_path.read_text(encoding="utf-8"))
        registry = _load_registry()
        data["active_repo_id"] = repo_id or registry.get("active_repo_id")
        self._json(data)

    def _send_impact(self, node_id: str, repo_id: str = "") -> None:
        a_path, _, root_path = self._resolve_paths(repo_id if repo_id else None)
        if not a_path.exists():
            self._json({"error": "No analysis found."}, status=404)
            return

        analysis = json.loads(a_path.read_text(encoding="utf-8"))
        nodes = analysis.get("nodes", [])
        relationships = analysis.get("relationships", [])
        impact_map = analysis.get("impact_index", {})

        nodes_by_id = {n["id"]: n for n in nodes}
        target_node = nodes_by_id.get(node_id)
        if not target_node:
            for n in nodes:
                if n.get("label") == node_id or n.get("path") == node_id:
                    target_node = n
                    node_id = n["id"]
                    break

        base_impact = impact_map.get(node_id, {})
        affected_files = list(base_impact.get("affected_files", []))
        affected_apis = list(base_impact.get("affected_apis", []))
        affected_tests = list(base_impact.get("affected_tests", []))
        risk = base_impact.get("risk", "Low")

        # 2-Hop reverse dependency BFS
        rev_adj = defaultdict(list)
        for r in relationships:
            if r.get("type") in {"CALLS", "IMPORTS", "EXTENDS", "TESTS"}:
                rev_adj[r.get("target")].append(r)

        seen = {node_id}
        queue = deque([(node_id, 0)])

        # If node is a class, method, or function inside a file, bridge from its file's importers
        parent_file_id = f"file:{target_node.get('path', '')}" if target_node else ""
        if target_node and target_node.get("type") != "File" and parent_file_id in rev_adj:
            for r in rev_adj[parent_file_id]:
                src_id = r.get("source")
                if src_id and src_id not in seen:
                    queue.append((src_id, 1))
                    seen.add(src_id)

        hop1_nodes = []
        hop2_nodes = []

        while queue:
            curr, depth = queue.popleft()
            if depth >= 2:
                continue
            for r in rev_adj.get(curr, []):
                src_id = r.get("source")
                if src_id and src_id not in seen:
                    seen.add(src_id)
                    src_node = nodes_by_id.get(src_id, {"id": src_id, "label": src_id, "type": "Entity"})
                    item = {
                        "id": src_id,
                        "name": src_node.get("label", src_id),
                        "kind": src_node.get("type", "Entity"),
                        "file": src_node.get("path", ""),
                        "start_line": src_node.get("line"),
                        "relation": r.get("type", "DEPENDS_ON"),
                    }
                    if depth == 0:
                        hop1_nodes.append(item)
                    else:
                        hop2_nodes.append(item)
                    queue.append((src_id, depth + 1))

        # Risk scoring
        if len(affected_files) >= 5 or len(affected_apis) >= 3 or len(hop1_nodes) >= 3:
            risk = "High"
        elif len(affected_files) >= 2 or len(affected_apis) >= 1 or len(hop1_nodes) >= 1:
            risk = "Medium"

        blast_score = min(
            100,
            len(hop1_nodes) * 15 + len(hop2_nodes) * 8 + len(affected_apis) * 20 + len(affected_files) * 5,
        )
        if blast_score == 0 and (hop1_nodes or affected_files):
            blast_score = 15

        recommendations = []
        if risk == "High":
            recommendations.append(
                f"High blast radius: changing this entity cascades into {len(affected_files)} downstream files and {len(affected_apis)} public API endpoints."
            )
        elif risk == "Medium":
            recommendations.append(
                f"Moderate impact: {len(affected_files)} files and {len(hop1_nodes)} direct callers depend on this component."
            )
        else:
            path_l = (target_node.get("path") or "").lower() if target_node else ""
            if any(k in path_l for k in ["main.", "index.", "app.module", "server."]):
                recommendations.append("Root application bootstrap runner: Executed at startup, with no upstream internal callers.")
            else:
                recommendations.append("Isolated component with minimal downstream blast radius.")

        if affected_tests:
            recommendations.append(f"Run tests in: {', '.join(sorted(affected_tests)[:3])}")
        else:
            recommendations.append("No automated test files detected directly covering this dependency path.")

        if affected_apis:
            recommendations.append(f"Verify public contracts for: {', '.join(sorted(affected_apis)[:3])}")

        target_label = target_node.get("label") if target_node else base_impact.get("label", node_id)
        target_kind = target_node.get("type") if target_node else base_impact.get("type", "Component")
        target_path = target_node.get("path") if target_node else base_impact.get("path", "")
        line = target_node.get("line") if target_node else None

        self._json({
            "id": node_id,
            "label": target_label,
            "kind": target_kind,
            "type": target_kind,
            "file": target_path,
            "line": line,
            "line_range": [line, line] if line else None,
            "affected_files": affected_files,
            "affected_apis": affected_apis,
            "affected_tests": affected_tests,
            "direct_dependents": hop1_nodes,
            "transitive_dependents": hop2_nodes,
            "blast_score": blast_score,
            "recommendations": recommendations,
            "risk": risk,
        })

    def _send_file_content(self, file_path: str, repo_id: str = "") -> None:
        if not file_path:
            self._json({"error": "Missing 'path' parameter."}, status=400)
            return
        _, _, root_path = self._resolve_paths(repo_id if repo_id else None)
        target = (root_path / file_path).resolve()
        if not target.exists() or not target.is_file():
            self._json({"error": f"File not found: {file_path}"}, status=404)
            return
        try:
            content = target.read_text(encoding="utf-8", errors="replace")
            self._json({"path": file_path, "content": content, "lines": len(content.splitlines())})
        except Exception as exc:
            self._json({"error": str(exc)}, status=500)

    def _send_file_tree(self, repo_id: str = "") -> None:
        a_path, _, _ = self._resolve_paths(repo_id if repo_id else None)
        if not a_path.exists():
            self._json({"tree": []})
            return
        try:
            analysis = json.loads(a_path.read_text(encoding="utf-8"))
            files = [f["path"] for f in analysis.get("files", [])]
            self._json({"files": files})
        except Exception:
            self._json({"files": []})

    def _send_graph_hierarchy(self, repo_id: str = "") -> None:
        a_path, _, _ = self._resolve_paths(repo_id if repo_id else None)
        if not a_path.exists():
            self._json({"error": "No analysis found."}, status=404)
            return
        analysis = json.loads(a_path.read_text(encoding="utf-8"))
        nodes = analysis.get("nodes", [])
        rels = analysis.get("relationships", [])

        # Filter to CONTAINS relationships for hierarchy
        contains_rels = [r for r in rels if r.get("type") == "CONTAINS"]
        children_by_parent: dict[str, list[str]] = defaultdict(list)
        for r in contains_rels:
            children_by_parent[r["source"]].append(r["target"])

        # Count incoming and outgoing dependencies per node (excluding CONTAINS)
        dep_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"in": 0, "out": 0})
        for r in rels:
            if r.get("type") != "CONTAINS":
                dep_counts[r["source"]]["out"] += 1
                dep_counts[r["target"]]["in"] += 1

        self._json({
            "root_id": "repo:root",
            "children_by_parent": dict(children_by_parent),
            "dep_counts": dict(dep_counts),
            "nodes_by_id": {n["id"]: n for n in nodes},
        })

    def _send_graph_neighborhood(self, node_id: str, repo_id: str = "") -> None:
        if not node_id:
            self._json({"error": "Missing 'id' parameter."}, status=400)
            return
        a_path, _, _ = self._resolve_paths(repo_id if repo_id else None)
        if not a_path.exists():
            self._json({"error": "No analysis found."}, status=404)
            return
        analysis = json.loads(a_path.read_text(encoding="utf-8"))
        nodes_by_id = {n["id"]: n for n in analysis.get("nodes", [])}
        target_node = nodes_by_id.get(node_id)
        if not target_node:
            self._json({"error": f"Node '{node_id}' not found."}, status=404)
            return

        rels = analysis.get("relationships", [])
        outgoing = [
            {"rel": r, "target_node": nodes_by_id.get(r["target"])}
            for r in rels
            if r.get("source") == node_id and r.get("target") in nodes_by_id and r.get("type") != "CONTAINS"
        ]
        incoming = [
            {"rel": r, "source_node": nodes_by_id.get(r["source"])}
            for r in rels
            if r.get("target") == node_id and r.get("source") in nodes_by_id and r.get("type") != "CONTAINS"
        ]

        self._json({
            "node": target_node,
            "incoming": incoming,
            "outgoing": outgoing,
        })

    def _send_onboarding(self, repo_id: str = "", role: str = "") -> None:
        a_path, _, _ = self._resolve_paths(repo_id if repo_id else None)
        if not a_path.exists():
            self._json({"error": "No analysis found."}, status=404)
            return
        try:
            analysis = json.loads(a_path.read_text(encoding="utf-8"))
            generator = RoleOnboardingGenerator(analysis)
            if role:
                guide = generator.generate(role)
                self._json(guide.to_dict())
            else:
                guides = generator.generate_all()
                self._json({"roles": guides})
        except Exception as exc:
            self._json({"error": str(exc)}, status=500)

    def _send_flow_discover(self, repo_id: str = "") -> None:
        a_path, _, _ = self._resolve_paths(repo_id if repo_id else None)
        if not a_path.exists():
            self._json({"flows": []})
            return
        try:
            analysis = json.loads(a_path.read_text(encoding="utf-8"))
            tracer = FeatureFlowTracer(analysis)
            self._json({"flows": tracer.discover_flows()})
        except Exception as exc:
            self._json({"error": str(exc)}, status=500)

    def _send_flow_trace(self, repo_id: str = "", entry_point_id: str = "", query: str = "") -> None:
        a_path, _, _ = self._resolve_paths(repo_id if repo_id else None)
        if not a_path.exists():
            self._json({"error": "No analysis found."}, status=404)
            return
        try:
            analysis = json.loads(a_path.read_text(encoding="utf-8"))
            tracer = FeatureFlowTracer(analysis)
            flow = tracer.trace_flow(entry_point_id=entry_point_id or None, query=query or None)
            if not flow:
                self._json({"error": "Could not trace execution flow for target."}, status=404)
                return
            self._json(flow.to_dict())
        except Exception as exc:
            self._json({"error": str(exc)}, status=500)

    def _handle_ask(self) -> None:
        try:
            payload = self._read_json()
            question = (payload.get("question") or "").strip()
            repo_id = payload.get("repo_id")
            if not question:
                self._json({"error": "Provide a 'question'."}, status=400)
                return
            a_path, i_path, _ = self._resolve_paths(repo_id)
            if not a_path.exists():
                self._json({"error": "No analysis found. Import or analyze a repository first."}, status=404)
                return
            analysis = json.loads(a_path.read_text(encoding="utf-8"))
            index = load_index(i_path)
            self._json(answer_question(analysis, index, question))
        except Exception as exc:
            self._json({"error": str(exc)}, status=400)

    def _handle_chat(self) -> None:
        try:
            payload = self._read_json()
            conversation_id = payload.get("conversation_id")
            question = (payload.get("question") or "").strip()
            repo_id = payload.get("repo_id")

            if payload.get("reset"):
                if conversation_id:
                    self.conversations.reset(conversation_id)
                if not question:
                    self._json({"conversation_id": conversation_id, "reset": True, "turn": 0})
                    return

            if not question:
                self._json({"error": "Provide a 'question'."}, status=400)
                return

            a_path, i_path, _ = self._resolve_paths(repo_id)
            if not a_path.exists():
                self._json({"error": "No analysis found. Import or analyze a repository first."}, status=404)
                return

            analysis = json.loads(a_path.read_text(encoding="utf-8"))
            index = load_index(i_path)
            conversation = self.conversations.get_or_create(conversation_id, repo_id=repo_id or "default")
            self._json(chat_answer(analysis, index, conversation, question, manager=self.conversations))
        except Exception as exc:
            self._json({"error": str(exc)}, status=400)

    def _send_ai_status(self) -> None:
        try:
            provider = get_llm_provider()
            if provider and provider.configured:
                self._json({
                    "configured": True,
                    "provider": getattr(provider, "provider_name", "llm"),
                    "model": getattr(provider, "model", getattr(provider, "model_name", "unknown")),
                })
            else:
                self._json({
                    "configured": False,
                    "provider": None,
                    "model": None,
                    "mode": "local",
                })
        except Exception as exc:
            self._json({"configured": False, "error": str(exc), "mode": "local"})

    def _read_json(self) -> dict:
        body = self.rfile.read(int(self.headers.get("Content-Length", "0") or "0"))
        return json.loads(body.decode("utf-8") or "{}")

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return

    def _send_static(self, request_path: str) -> None:
        dist_dir = STATIC_DIR / "dist"
        
        # Explicit request for classic dashboard
        if request_path.startswith("/classic"):
            relative = request_path.removeprefix("/classic").lstrip("/") or "index.html"
            target = (STATIC_DIR / relative).resolve()
        elif dist_dir.exists() and (dist_dir / "index.html").exists():
            # Modern React + Vite application
            relative = request_path.lstrip("/") or "index.html"
            candidate = (dist_dir / relative).resolve()
            if candidate.is_relative_to(dist_dir.resolve()) and candidate.is_file():
                target = candidate
            elif (STATIC_DIR / relative).resolve().is_file() and (STATIC_DIR / relative).resolve().is_relative_to(STATIC_DIR.resolve()):
                target = (STATIC_DIR / relative).resolve()
            else:
                # SPA fallback
                target = dist_dir / "index.html"
        else:
            relative = request_path.lstrip("/") or "index.html"
            target = (STATIC_DIR / relative).resolve()

        if not target.is_relative_to(STATIC_DIR.resolve()) or not target.exists() or not target.is_file():
            self.send_error(404)
            return

        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, payload: dict | list, status: int = 200) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Auth-Token")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.end_headers()
        self.wfile.write(data)


def serve_dashboard(analysis_path: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    handler = type("ConfiguredCodeCompassHandler", (CodeCompassHandler,), {"analysis_path": analysis_path})
    server = ThreadingHTTPServer((host, port), handler)
    print(f"CodeCompass dashboard running at http://{host}:{port}")
    print(f"Active analysis file: {analysis_path}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

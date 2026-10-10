"""Codebase analysis engine for CodeCompass.

Provides both lightweight regex/AST repository analysis (:func:`analyze_repository`)
and deep Tree-sitter semantic AST extraction with scoped resolution (:func:`analyze_with_treesitter`).
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from codecompass.config import DEFAULT_IGNORED_DIRS as IGNORED_DIRS, SUPPORTED_EXTENSIONS
from codecompass.extractor import extract_file
from codecompass.extractor.models import FileParseResult
from codecompass.graph.impact import GraphImpactAnalyzer
from codecompass.resolver.scoped_resolver import ScopedResolver, to_entity_records
from codecompass.retrieval.bm25 import BM25Index
from codecompass.retrieval.chunker import create_semantic_chunks
from codecompass.scanner.walker import walk_repository
from codecompass.storage.database import Database
from codecompass.storage.models import FileRecord, SearchChunkRecord
from codecompass.storage.repositories import (
    EntityDAL,
    FileDAL,
    RelationshipDAL,
    RepositoryDAL,
    SearchChunkDAL,
)

ENTRYPOINT_NAMES = {
    "main.py",
    "app.py",
    "server.py",
    "manage.py",
    "index.js",
    "index.ts",
    "server.js",
    "server.ts",
    "app.js",
    "app.ts",
    "package.json",
    "pyproject.toml",
    "pom.xml",
}

API_METHODS = {"get", "post", "put", "patch", "delete", "options", "head"}
GRAPH_RELATIONSHIPS = {"CALLS", "IMPORTS", "USES", "IMPLEMENTS", "EXTENDS", "TESTS", "REFERENCES"}


@dataclass
class ParsedFile:
    path: Path
    rel_path: str
    language: str
    lines: int
    imports: list[str] = field(default_factory=list)
    classes: list[dict[str, Any]] = field(default_factory=list)
    functions: list[dict[str, Any]] = field(default_factory=list)
    methods: list[dict[str, Any]] = field(default_factory=list)
    apis: list[dict[str, Any]] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)
    inheritance: list[tuple[str, str]] = field(default_factory=list)


def analyze_repository(target: str | Path) -> dict[str, Any]:
    """Analyzes a repository and produces the complete CodeCompass architecture map."""
    root = Path(target).resolve()
    if not root.exists():
        raise FileNotFoundError(f"Repository path does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Repository path must be a directory: {root}")

    source_files = list(_iter_source_files(root))
    parsed_files = [_parse_file(root, path) for path in source_files]
    parsed_files = [item for item in parsed_files if item is not None]

    nodes: list[dict[str, Any]] = []
    relationships: list[dict[str, Any]] = []
    seen_nodes: set[str] = set()
    seen_relationships: set[tuple[str, str, str]] = set()

    def add_node(node_id: str, node_type: str, label: str, **props: Any) -> None:
        if node_id in seen_nodes:
            return
        seen_nodes.add(node_id)
        nodes.append({"id": node_id, "type": node_type, "label": label, **props})

    def add_rel(source: str, rel_type: str, target_id: str, **props: Any) -> None:
        key = (source, rel_type, target_id)
        if key in seen_relationships or source == target_id:
            return
        seen_relationships.add(key)
        relationships.append({"source": source, "type": rel_type, "target": target_id, **props})

    repo_id = "repo:root"
    add_node(repo_id, "Repository", root.name or str(root), path=str(root))

    directory_ids = _add_directory_nodes(root, [item.path for item in parsed_files], add_node, add_rel, repo_id)

    symbol_by_name: dict[str, list[str]] = defaultdict(list)
    module_to_file = _module_index(parsed_files)
    all_file_paths = {item.rel_path.replace("\\", "/") for item in parsed_files}
    file_infos: list[dict[str, Any]] = []
    api_infos: list[dict[str, Any]] = []
    external_dependencies: set[str] = set()

    for parsed in parsed_files:
        file_id = _file_id(parsed.rel_path)
        parent_dir_id = directory_ids.get(_parent_rel(parsed.rel_path), repo_id)
        add_node(
            file_id,
            "File",
            Path(parsed.rel_path).name,
            path=parsed.rel_path,
            language=parsed.language,
            lines=parsed.lines,
            is_test=_is_test_file(parsed.rel_path),
        )
        add_rel(parent_dir_id, "CONTAINS", file_id)

        file_infos.append(
            {
                "id": file_id,
                "path": parsed.rel_path,
                "language": parsed.language,
                "lines": parsed.lines,
                "is_test": _is_test_file(parsed.rel_path),
                "imports": sorted(set(parsed.imports)),
                "symbols": [item["name"] for item in parsed.classes + parsed.functions + parsed.methods],
            }
        )

        for klass in parsed.classes:
            node_id = _symbol_id("class", parsed.rel_path, klass["name"], klass["line"])
            add_node(
                node_id,
                "Class",
                klass["name"],
                path=parsed.rel_path,
                line=klass["line"],
                docstring=klass.get("docstring"),
                language=parsed.language,
            )
            add_rel(file_id, "CONTAINS", node_id)
            symbol_by_name[klass["name"]].append(node_id)

        for fn in parsed.functions:
            node_id = _symbol_id("func", parsed.rel_path, fn["name"], fn["line"])
            add_node(
                node_id,
                "Function",
                fn["name"],
                path=parsed.rel_path,
                line=fn["line"],
                docstring=fn.get("docstring"),
                language=parsed.language,
            )
            add_rel(file_id, "CONTAINS", node_id)
            symbol_by_name[fn["name"]].append(node_id)

        for method in parsed.methods:
            node_id = _symbol_id("method", parsed.rel_path, method["name"], method["line"])
            add_node(
                node_id,
                "Method",
                method["name"],
                path=parsed.rel_path,
                line=method["line"],
                docstring=method.get("docstring"),
                language=parsed.language,
            )
            add_rel(file_id, "CONTAINS", node_id)
            symbol_by_name[method["name"]].append(node_id)

        for api in parsed.apis:
            node_id = _api_id(parsed.rel_path, api["method"], api["path"])
            label = f"{api['method']} {api['path']}"
            add_node(
                node_id,
                "API",
                label,
                path=parsed.rel_path,
                line=api["line"],
                method=api["method"],
                route=api["path"],
            )
            add_rel(file_id, "CONTAINS", node_id)
            api_infos.append(
                {
                    "id": node_id,
                    "method": api["method"],
                    "path": api["path"],
                    "file": parsed.rel_path,
                    "line": api["line"],
                }
            )

        for base, derived in parsed.inheritance:
            derived_ids = symbol_by_name.get(derived, [])
            base_ids = symbol_by_name.get(base, [])
            for d_id in derived_ids:
                for b_id in base_ids:
                    add_rel(d_id, "EXTENDS", b_id)

        for call in parsed.calls:
            targets = symbol_by_name.get(call, [])
            for target_id in targets:
                add_rel(file_id, "CALLS", target_id)

        for imported in parsed.imports:
            target_path = _resolve_import(parsed.rel_path, imported, module_to_file, all_file_paths)
            if target_path:
                target_file_id = _file_id(target_path)
                add_rel(file_id, "IMPORTS", target_file_id)
            else:
                dep_name = _dependency_name(imported)
                if dep_name:
                    external_dependencies.add(dep_name)

    _link_tests(file_infos, relationships, add_rel)

    summary = _build_summary(root, parsed_files, api_infos, external_dependencies)
    components = _build_components(parsed_files)
    onboarding = _build_onboarding(summary, components, file_infos, api_infos)
    impact_index = _build_impact_index(nodes, relationships)

    return {
        "schema_version": "0.2.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository": {
            "name": root.name,
            "path": str(root),
            "supported_languages": sorted(set(item.language for item in parsed_files)),
            "file_count": len(parsed_files),
        },
        "summary": summary,
        "components": components,
        "onboarding": onboarding,
        "files": file_infos,
        "apis": api_infos,
        "nodes": nodes,
        "relationships": relationships,
        "impact_index": impact_index,
    }


def write_analysis(analysis: dict[str, Any], output_path: str | Path) -> Path:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(analysis, indent=2), encoding="utf-8")
    return destination


def default_output_path(repo_path: str | Path) -> Path:
    return Path(repo_path).resolve() / ".codecompass" / "analysis.json"


def _iter_source_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORED_DIRS for part in path.relative_to(root).parts):
            continue
        if path.suffix in SUPPORTED_EXTENSIONS:
            yield path


def _parse_file(root: Path, path: Path) -> ParsedFile | None:
    rel_path = _rel(root, path)
    language = SUPPORTED_EXTENSIONS.get(path.suffix)
    if not language:
        return None

    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (UnicodeDecodeError, OSError):
            return None

    parsed = ParsedFile(
        path=path,
        rel_path=rel_path,
        language=language,
        lines=len(text.splitlines()),
    )

    if language == "Python":
        _parse_python(text, parsed)
    elif language in {"JavaScript", "TypeScript"}:
        _parse_javascript_like(text, parsed)

    next_route = _nextjs_route_from_path(rel_path)
    if next_route:
        parsed.apis.append(next_route)

    return parsed


def _parse_python(text: str, parsed: ParsedFile) -> None:
    try:
        module = ast.parse(text)
    except SyntaxError:
        _parse_python_regex(text, parsed)
        return

    for node in module.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    parsed.imports.append(alias.name)
            else:
                module_name = node.module or ""
                for alias in node.names:
                    parsed.imports.append(f"{module_name}.{alias.name}" if module_name else alias.name)
        elif isinstance(node, ast.ClassDef):
            parsed.classes.append({"name": node.name, "line": node.lineno, "docstring": ast.get_docstring(node)})
            for base in node.bases:
                base_name = _ast_name(base)
                if base_name:
                    parsed.inheritance.append((base_name, node.name))
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    parsed.methods.append({"name": f"{node.name}.{item.name}", "line": item.lineno, "docstring": ast.get_docstring(item)})
                    parsed.apis.extend(_python_api_routes(item.decorator_list, item.lineno))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            parsed.functions.append({"name": node.name, "line": node.lineno, "docstring": ast.get_docstring(node)})
            parsed.apis.extend(_python_api_routes(node.decorator_list, node.lineno))

    for node in ast.walk(module):
        if isinstance(node, ast.Call):
            call_name = _ast_name(node.func)
            if call_name and not call_name.startswith("self."):
                parsed.calls.append(call_name.split(".")[-1])


def _parse_python_regex(text: str, parsed: ParsedFile) -> None:
    for line_no, line in enumerate(text.splitlines(), start=1):
        class_match = re.match(r"^\s*class\s+([A-Za-z_]\w*)", line)
        if class_match:
            parsed.classes.append({"name": class_match.group(1), "line": line_no})
        fn_match = re.match(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)", line)
        if fn_match:
            parsed.functions.append({"name": fn_match.group(1), "line": line_no})
        import_match = re.match(r"^\s*(?:from\s+([A-Za-z_.\w]+)\s+import|import\s+([A-Za-z_.\w]+))", line)
        if import_match:
            parsed.imports.append(import_match.group(1) or import_match.group(2))


def _parse_javascript_like(text: str, parsed: ParsedFile) -> None:
    import_re = re.compile(r"""(?:import\s+.*?from\s+['"]([^'"]+)['"]|require\(['"]([^'"]+)['"]\))""")
    class_re = re.compile(r"""^\s*(?:export\s+)?class\s+([A-Za-z_$][\w$]*)(?:\s+extends\s+([A-Za-z_$][\w$]*))?""", re.MULTILINE)
    fn_re = re.compile(r"""^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)""", re.MULTILINE)
    arrow_re = re.compile(r"""^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>""", re.MULTILINE)
    route_re = re.compile(r"""(?:app|router|server|fastify)\.(get|post|put|delete|patch|options|head)\(\s*['"`]([^'"`]+)['"`]""", re.IGNORECASE)
    nestjs_ctrl_re = re.compile(r"""@Controller\(\s*(?:['"`]([^'"`]*)['"`])?\s*\)""")
    nestjs_method_re = re.compile(r"""@(Get|Post|Put|Delete|Patch|Options|Head)\(\s*(?:['"`]([^'"`]*)['"`])?\s*\)""", re.IGNORECASE)
    ts_method_re = re.compile(r"""^\s{2,4}(?:(?:public|private|protected|async|static|readonly)\s+)*([A-Za-z_$][\w$]*)\s*\(""")
    ts_keywords = {"constructor", "if", "for", "while", "switch", "catch", "function", "return", "super", "import", "export", "class", "const", "let", "var", "Number", "String", "Boolean"}

    current_controller_prefix = ""
    current_class = ""

    lines = text.splitlines()
    for line_no, line in enumerate(lines, start=1):
        for match in import_re.finditer(line):
            target = match.group(1) or match.group(2)
            if target:
                parsed.imports.append(target)

        # NestJS controller decorator
        ctrl_match = nestjs_ctrl_re.search(line)
        if ctrl_match:
            raw_p = ctrl_match.group(1) or ""
            if raw_p and not raw_p.startswith("/"):
                raw_p = "/" + raw_p
            current_controller_prefix = raw_p.rstrip("/")

        # NestJS method decorator
        nest_m = nestjs_method_re.search(line)
        if nest_m:
            method_verb = nest_m.group(1).upper()
            subpath = (nest_m.group(2) or "").strip()
            if subpath and not subpath.startswith("/"):
                subpath = "/" + subpath
            full_route = f"{current_controller_prefix}{subpath}" or "/"
            parsed.apis.append({"method": method_verb, "path": full_route, "line": line_no})

        for match in class_re.finditer(line):
            name, base = match.group(1), match.group(2)
            current_class = name
            parsed.classes.append({"name": name, "line": line_no})
            if base:
                parsed.inheritance.append((base, name))

        for match in fn_re.finditer(line):
            parsed.functions.append({"name": match.group(1), "line": line_no})

        for match in arrow_re.finditer(line):
            parsed.functions.append({"name": match.group(1), "line": line_no})

        for match in route_re.finditer(line):
            parsed.apis.append({"method": match.group(1).upper(), "path": match.group(2), "line": line_no})

        # Class method extraction
        if current_class:
            tm = ts_method_re.match(line)
            if tm:
                m_name = tm.group(1)
                prev_line = lines[line_no - 2].strip() if line_no >= 2 else ""
                if m_name not in ts_keywords and (
                    prev_line.startswith("@")
                    or any(w in line for w in ["public", "private", "async", "protected"])
                ):
                    parsed.methods.append({"name": f"{current_class}.{m_name}", "line": line_no})
                    parsed.methods.append({"name": m_name, "line": line_no})

    call_re = re.compile(r"""\b([A-Za-z_$][\w$]*)\s*\(""")
    for line in text.splitlines():
        for call_match in call_re.finditer(line):
            token = call_match.group(1)
            if token not in {"import", "require", "function", "if", "for", "while", "switch", "catch"}:
                parsed.calls.append(token)


def _python_api_routes(decorators: list[ast.expr], line_no: int) -> list[dict[str, Any]]:
    routes: list[dict[str, Any]] = []
    for dec in decorators:
        if not isinstance(dec, ast.Call):
            continue
        func_name = _ast_name(dec.func) or ""
        method = func_name.split(".")[-1].lower()
        if method in API_METHODS and dec.args:
            path_arg = dec.args[0]
            if isinstance(path_arg, ast.Constant) and isinstance(path_arg.value, str):
                routes.append({"method": method.upper(), "path": path_arg.value, "line": line_no})
    return routes


def _ast_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _ast_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    if isinstance(node, ast.Call):
        return _ast_name(node.func)
    return None


def _nextjs_route_from_path(rel_path: str) -> dict[str, Any] | None:
    path = Path(rel_path)
    parts = list(path.parts)
    if "api" not in parts:
        return None
    if path.name not in {"route.ts", "route.js", "route.tsx", "route.jsx"}:
        return None
    api_index = parts.index("api")
    route_parts = parts[api_index + 1 : -1]
    route = "/" + "/".join(route_parts)
    route = route.replace("[", ":").replace("]", "")
    return {"method": "GET", "path": route or "/", "line": 1}


def _add_directory_nodes(root: Path, files: list[Path], add_node, add_rel, repo_id: str) -> dict[str, str]:
    directory_ids: dict[str, str] = {"": repo_id}
    directories: set[str] = set()
    for file_path in files:
        relative = file_path.relative_to(root)
        current: list[str] = []
        for part in relative.parts[:-1]:
            current.append(part)
            directories.add("/".join(current))

    for directory in sorted(directories, key=lambda item: (item.count("/"), item)):
        node_id = f"dir:{directory}"
        directory_ids[directory] = node_id
        add_node(node_id, "Directory", Path(directory).name, path=directory)
        parent = _parent_rel(directory)
        add_rel(directory_ids.get(parent, repo_id), "CONTAINS", node_id)

    return directory_ids


def _module_index(parsed_files: list[ParsedFile]) -> dict[str, str]:
    modules: dict[str, str] = {}
    for parsed in parsed_files:
        rel = parsed.rel_path.replace("\\", "/")
        stem = rel.rsplit(".", 1)[0]
        modules[stem.replace("/", ".")] = rel
        modules[Path(rel).stem] = rel
        if Path(rel).name == "__init__.py":
            modules[str(Path(rel).parent).replace("\\", ".").replace("/", ".")] = rel
    return modules


def _resolve_import(current_file: str, import_name: str, module_to_file: dict[str, str], all_file_paths: set[str] | None = None) -> str | None:
    raw = import_name.strip()
    if not raw:
        return None

    paths_set = all_file_paths or set(module_to_file.values())

    # Handle relative imports (starts with '.' or '..')
    if raw.startswith("."):
        source_dir = Path(current_file).parent
        suffixes = ["", ".ts", ".js", ".tsx", ".jsx", ".py", "/index.ts", "/index.js", "/index.py"]
        for sfx in suffixes:
            cand = (source_dir / (raw + sfx)).as_posix()
            parts: list[str] = []
            for p in cand.split("/"):
                if p == "..":
                    if parts:
                        parts.pop()
                elif p != "." and p != "":
                    parts.append(p)
            norm = "/".join(parts)
            if norm in paths_set:
                return norm
            if norm.lstrip("/") in paths_set:
                return norm.lstrip("/")

    # Handle module/stem imports
    normalized = raw.replace("/", ".").replace("\\", ".").strip(".")
    if normalized in module_to_file:
        return module_to_file[normalized]
    base_name = raw.split("/")[-1].split(".")[0]
    if base_name in module_to_file:
        return module_to_file[base_name]

    for module_name, file_path in module_to_file.items():
        if normalized.startswith(module_name + ".") or module_name.startswith(normalized + "."):
            return file_path

    return None


def _dependency_name(import_name: str) -> str:
    if not import_name or import_name.startswith("."):
        return ""
    if import_name.startswith("@"):
        parts = import_name.split("/")
        return "/".join(parts[:2])
    return re.split(r"[./]", import_name)[0]


def _link_tests(file_infos: list[dict[str, Any]], relationships: list[dict[str, Any]], add_rel) -> None:
    file_by_module = {Path(item["path"]).stem.lower(): item["id"] for item in file_infos}
    for file_info in file_infos:
        if not file_info["is_test"]:
            continue
        for imported in file_info["imports"]:
            candidate = Path(imported).stem.lower()
            if candidate in file_by_module:
                add_rel(file_info["id"], "TESTS", file_by_module[candidate])


def _build_summary(root: Path, parsed_files: list[ParsedFile], apis: list[dict[str, Any]], external_dependencies: set[str]) -> dict[str, Any]:
    language_counter = Counter(item.language for item in parsed_files)
    line_counter = Counter({language: 0 for language in language_counter})
    for parsed in parsed_files:
        line_counter[parsed.language] += parsed.lines

    entry_points = []
    for path in root.iterdir() if root.exists() else []:
        if path.name in ENTRYPOINT_NAMES:
            entry_points.append(path.name)
    for parsed in parsed_files:
        if Path(parsed.rel_path).name in ENTRYPOINT_NAMES and parsed.rel_path not in entry_points:
            entry_points.append(parsed.rel_path)

    if not entry_points and parsed_files:
        candidates = [
            p.rel_path for p in parsed_files
            if any(k in Path(p.rel_path).stem.lower() for k in ["main", "app", "index", "server"])
        ]
        if candidates:
            entry_points.extend(candidates[:5])
        else:
            sorted_by_lines = sorted(parsed_files, key=lambda x: -x.lines)
            entry_points.extend([p.rel_path for p in sorted_by_lines[:3]])

    top_level_dirs = Counter()
    for parsed in parsed_files:
        parts = Path(parsed.rel_path).parts
        top_level_dirs[parts[0] if len(parts) > 1 else "root"] += 1

    component_names = [name for name, _ in top_level_dirs.most_common(6)]
    primary_components = [_human_component_name(name) for name in component_names]
    repo_kind = _repo_kind(language_counter, apis, external_dependencies)

    return {
        "headline": f"{root.name} is a {repo_kind}.",
        "primary_components": primary_components,
        "entry_points": entry_points[:8],
        "languages": [{"name": name, "files": count, "lines": line_counter[name]} for name, count in language_counter.most_common()],
        "external_dependencies": sorted(external_dependencies)[:50],
        "api_count": len(apis),
        "architecture_layers": _architecture_layers(parsed_files, apis),
        "stats": {
            "files": len(parsed_files),
            "classes": sum(len(item.classes) for item in parsed_files),
            "functions": sum(len(item.functions) + len(item.methods) for item in parsed_files),
            "imports": sum(len(set(item.imports)) for item in parsed_files),
            "apis": len(apis),
            "lines": sum(item.lines for item in parsed_files),
        },
    }


def _repo_kind(language_counter: Counter, apis: list[dict[str, Any]], external_dependencies: set[str]) -> str:
    deps = {item.lower() for item in external_dependencies}
    if apis:
        return "service-oriented application with HTTP APIs"
    if {"react", "next", "vue", "svelte"} & deps:
        return "frontend application"
    if not language_counter:
        return "software repository"
    top_lang, _ = language_counter.most_common(1)[0]
    if top_lang in {"TypeScript", "JavaScript"}:
        return "TypeScript/JavaScript application"
    if top_lang == "Python":
        return "Python codebase"
    if top_lang == "Java":
        return "Java application"
    if top_lang == "Go":
        return "Go application"
    if top_lang == "Rust":
        return "Rust application"
    return f"{top_lang} repository"


def _architecture_layers(parsed_files: list[ParsedFile], apis: list[dict[str, Any]]) -> list[dict[str, Any]]:
    layer_rules = [
        ("Frontend", ("frontend", "client", "web", "pages", "components", "app")),
        ("API Layer", ("api", "routes", "controllers", "views", "handlers")),
        ("Services", ("service", "services", "usecase", "usecases", "domain")),
        ("Data Layer", ("db", "database", "models", "repository", "repositories", "schema", "migration")),
        ("Tests", ("test", "tests", "__tests__")),
    ]
    counts: Counter[str] = Counter()
    for parsed in parsed_files:
        lower_path = parsed.rel_path.lower()
        for layer, terms in layer_rules:
            if any(term in lower_path for term in terms):
                counts[layer] += 1
    if apis:
        counts["API Layer"] += len(apis)

    layers = [{"name": name, "files": counts[name]} for name, _ in layer_rules if counts[name]]
    if not layers and parsed_files:
        layers = [{"name": "Application Code", "files": len(parsed_files)}]
    return layers


def _build_components(parsed_files: list[ParsedFile]) -> list[dict[str, Any]]:
    grouped: dict[str, list[ParsedFile]] = defaultdict(list)
    for parsed in parsed_files:
        parts = Path(parsed.rel_path).parts
        key = parts[0] if len(parts) > 1 else "root"
        grouped[key].append(parsed)

    components = []
    for name, files in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0]))[:12]:
        languages = Counter(item.language for item in files)
        components.append(
            {
                "name": _human_component_name(name),
                "path": "" if name == "root" else name,
                "files": len(files),
                "lines": sum(item.lines for item in files),
                "languages": [language for language, _ in languages.most_common()],
                "responsibility": _component_responsibility(name),
            }
        )
    return components


def _build_onboarding(summary: dict[str, Any], components: list[dict[str, Any]], files: list[dict[str, Any]], apis: list[dict[str, Any]]) -> dict[str, Any]:
    important_files = sorted(files, key=lambda item: (not item["path"].split("/")[-1] in ENTRYPOINT_NAMES, -item["lines"]))[:8]
    guide_steps = [
        {"title": "Architecture", "items": [layer["name"] for layer in summary["architecture_layers"]]},
        {"title": "Core Components", "items": [component["name"] for component in components[:6]]},
        {"title": "Important Files", "items": [item["path"] for item in important_files]},
        {"title": "API Surface", "items": [f"{item['method']} {item['path']}" for item in apis[:12]] or ["No HTTP APIs detected yet."]},
        {"title": "Change Workflow", "items": ["Open the impact view before modifying high-degree files.", "Run related tests for files marked as affected."]},
    ]
    return {"title": "30 Minute Onboarding Guide", "steps": guide_steps}


def _build_impact_index(nodes: list[dict[str, Any]], relationships: list[dict[str, Any]]) -> dict[str, Any]:
    reverse: dict[str, list[dict[str, str]]] = defaultdict(list)
    node_lookup = {node["id"]: node for node in nodes}
    for rel in relationships:
        if rel["type"] in GRAPH_RELATIONSHIPS:
            reverse[rel["target"]].append(rel)

    file_to_apis: dict[str, list[str]] = defaultdict(list)
    for node in nodes:
        if node.get("type") == "API":
            file_to_apis[node.get("path") or ""].append(node.get("label", ""))

    impact: dict[str, Any] = {}
    for node in nodes:
        if node["type"] not in {"File", "Class", "Function", "Method", "API"}:
            continue
        seen: set[str] = set()
        queue = deque([(node["id"], 0)])
        affected_ids: set[str] = set()
        while queue:
            current, depth = queue.popleft()
            if depth >= 2:
                continue
            for rel in reverse.get(current, []):
                source = rel["source"]
                if source in seen:
                    continue
                seen.add(source)
                affected_ids.add(source)
                queue.append((source, depth + 1))

        # If node is inside a file, also bridge from its containing file
        parent_file_id = f"file:{node.get('path', '')}"
        if node["type"] != "File" and parent_file_id in reverse:
            for rel in reverse.get(parent_file_id, []):
                src = rel["source"]
                if src not in seen:
                    seen.add(src)
                    affected_ids.add(src)

        affected_nodes = [node_lookup[item] for item in affected_ids if item in node_lookup]
        affected_files = sorted({item.get("path") for item in affected_nodes if item.get("path")})
        
        affected_apis = sorted({item["label"] for item in affected_nodes if item["type"] == "API"})
        for fp in affected_files:
            for a in file_to_apis.get(fp, []):
                if a not in affected_apis:
                    affected_apis.append(a)

        affected_tests = sorted({item.get("path") for item in affected_nodes if item.get("is_test")})
        
        risk = "Low"
        if len(affected_files) >= 5 or len(affected_apis) >= 3:
            risk = "High"
        elif len(affected_files) >= 2 or len(affected_apis) >= 1 or len(affected_tests) >= 1:
            risk = "Medium"

        impact[node["id"]] = {
            "label": node["label"],
            "type": node["type"],
            "path": node.get("path"),
            "affected_files": affected_files[:50],
            "affected_apis": affected_apis[:25],
            "affected_tests": affected_tests[:25],
            "risk": risk,
        }
    return impact


def _human_component_name(path_part: str) -> str:
    if path_part == "root":
        return "Root Application"
    return path_part.replace("_", " ").replace("-", " ").title()


def _component_responsibility(path_part: str) -> str:
    lower = path_part.lower()
    if any(term in lower for term in ["api", "route", "controller"]):
        return "HTTP routing and request handling"
    if any(term in lower for term in ["service", "domain", "usecase"]):
        return "Business logic and orchestration"
    if any(term in lower for term in ["model", "db", "data", "repository"]):
        return "Persistence and data access"
    if any(term in lower for term in ["test", "spec"]):
        return "Automated verification"
    if any(term in lower for term in ["component", "page", "frontend", "client", "web"]):
        return "User interface"
    return "Repository module"


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _parent_rel(rel_path: str) -> str:
    parent = Path(rel_path).parent
    return "" if str(parent) == "." else parent.as_posix()


def _file_id(rel_path: str) -> str:
    return f"file:{rel_path}"


def _symbol_id(kind: str, rel_path: str, name: str, line: int) -> str:
    digest = hashlib.sha1(f"{kind}:{rel_path}:{name}:{line}".encode("utf-8")).hexdigest()[:10]
    return f"{kind}:{digest}"


def _api_id(rel_path: str, method: str, route: str) -> str:
    digest = hashlib.sha1(f"{rel_path}:{method}:{route}".encode("utf-8")).hexdigest()[:10]
    return f"api:{digest}"


def _is_test_file(rel_path: str) -> bool:
    lowered = rel_path.lower()
    name = Path(rel_path).name.lower()
    return lowered.startswith("tests/") or lowered.startswith("test/") or name.startswith("test_") or name.endswith((".test.ts", ".test.js", ".spec.ts", ".spec.js"))


def analyze_with_treesitter(root_path: str | Path, db: Database | None = None) -> dict[str, Any]:
    """Scans and analyzes a repository using Tree-sitter AST parsing, semantic chunking, and scoped resolution."""
    root = Path(root_path).resolve()
    scan_result = walk_repository(root)
    repo_id = scan_result.repository.id

    parsed_files: list[FileParseResult] = []
    file_contents: dict[str, str] = {}

    for file_rec in scan_result.files:
        full_path = root / file_rec.path
        try:
            code_bytes = full_path.read_bytes()
            code_text = code_bytes.decode("utf-8", errors="replace")
        except OSError:
            continue

        file_contents[file_rec.path] = code_text
        result = extract_file(
            rel_path=file_rec.path,
            code_bytes=code_bytes,
            language=file_rec.language,
        )
        parsed_files.append(result)

    # 1. Scoped resolution
    resolver = ScopedResolver(repo_id=repo_id, parsed_files=parsed_files)
    relationships = resolver.resolve_relationships()
    entity_records = to_entity_records(repo_id=repo_id, parsed_files=parsed_files)

    # 2. AST-Aware Semantic Chunking
    all_chunks: list[SearchChunkRecord] = []
    for parsed in parsed_files:
        code_text = file_contents.get(parsed.rel_path, "")
        file_id = f"file:{parsed.rel_path}"
        chunks = create_semantic_chunks(
            repo_id=repo_id,
            file_id=file_id,
            rel_path=parsed.rel_path,
            code_text=code_text,
            entities=parsed.entities,
        )
        all_chunks.extend(chunks)

    # 3. Downstream Impact Analysis
    impact_analyzer = GraphImpactAnalyzer(
        files=scan_result.files,
        entities=entity_records,
        relationships=relationships,
    )
    impact_index = impact_analyzer.build_impact_index()

    # 4. Persist in SQLite if database is provided
    if db is not None:
        repo_dal = RepositoryDAL(db)
        file_dal = FileDAL(db)
        entity_dal = EntityDAL(db)
        rel_dal = RelationshipDAL(db)
        chunk_dal = SearchChunkDAL(db)

        repo_dal.upsert_repository(scan_result.repository)
        file_dal.upsert_files(scan_result.files)
        file_dal.delete_missing_files(repo_id, {f.path for f in scan_result.files})

        for parsed in parsed_files:
            file_id = f"file:{parsed.rel_path}"
            file_ents = [e for e in entity_records if e.file_id == file_id]
            entity_dal.replace_entities_for_file(repo_id, file_id, file_ents)

            file_chunks = [c for c in all_chunks if c.file_id == file_id]
            chunk_dal.replace_chunks_for_file(repo_id, file_id, file_chunks)

        rel_dal.replace_relationships_for_repo(repo_id, relationships)

    all_apis = [
        e for p in parsed_files for e in p.entities if e.kind == "API"
    ]

    return {
        "repository": {
            "id": repo_id,
            "name": scan_result.repository.name,
            "root_path": str(root),
        },
        "stats": {
            "files": len(scan_result.files),
            "classes": sum(len([e for e in p.entities if e.kind == "Class"]) for p in parsed_files),
            "functions": sum(len([e for e in p.entities if e.kind in {"Function", "Method"}]) for p in parsed_files),
            "apis": len(all_apis),
            "relationships": len(relationships),
            "chunks": len(all_chunks),
            "lines": scan_result.stats["total_lines"],
        },
        "apis": [
            {
                "method": a.metadata.get("method", "GET"),
                "path": a.metadata.get("path", "/"),
                "file": a.id.split(":")[1] if ":" in a.id else "",
                "line": a.start_line,
            }
            for a in all_apis
        ],
        "entities_count": len(entity_records),
        "relationships_count": len(relationships),
        "chunks_count": len(all_chunks),
        "impact_index": impact_index,
    }

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
import tree_sitter

from codecompass.extractor.models import (
    FileParseResult,
    RawCall,
    RawEntity,
    RawImport,
    RawInheritance,
)

HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}


class TypeScriptExtractor:
    def __init__(self, rel_path: str, code_bytes: bytes, is_tsx: bool = False) -> None:
        self.rel_path = rel_path
        self.code_bytes = code_bytes
        self.is_tsx = is_tsx
        self.entities: list[RawEntity] = []
        self.imports: list[RawImport] = []
        self.calls: list[RawCall] = []
        self.inheritances: list[RawInheritance] = []

    def extract(self, root_node: tree_sitter.Node) -> FileParseResult:
        self._visit_node(root_node, scope=None)
        self._check_nextjs_route()
        return FileParseResult(
            rel_path=self.rel_path,
            language="TypeScript" if (self.rel_path.endswith((".ts", ".tsx"))) else "JavaScript",
            entities=self.entities,
            imports=self.imports,
            calls=self.calls,
            inheritances=self.inheritances,
        )

    def _text(self, node: tree_sitter.Node | None) -> str:
        if node is None:
            return ""
        return self.code_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="replace")

    def _visit_node(self, node: tree_sitter.Node, scope: str | None) -> None:
        node_type = node.type

        if node_type == "import_statement":
            self._parse_import_statement(node)
            return
        elif node_type in {"class_declaration", "class"}:
            self._parse_class_declaration(node, scope)
            return
        elif node_type == "function_declaration":
            self._parse_function_declaration(node, scope)
            return
        elif node_type in {"lexical_declaration", "variable_declaration"}:
            self._parse_variable_declaration(node, scope)
            return
        elif node_type == "call_expression":
            self._parse_call_expression(node, scope)

        for child in node.children:
            self._visit_node(child, scope)

    def _parse_import_statement(self, node: tree_sitter.Node) -> None:
        source_node = node.child_by_field_name("source")
        if not source_node:
            return

        raw_mod = self._text(source_node).strip("'\"`")
        is_rel = raw_mod.startswith(("./", "../"))
        rel_level = 0
        if is_rel:
            rel_level = 1 if raw_mod.startswith("./") else 2

        symbols: list[tuple[str, str | None]] = []
        import_clause = node.child_by_field_name("import")
        if import_clause:
            for child in import_clause.children:
                if child.type == "identifier":
                    symbols.append((self._text(child), None))
                elif child.type == "named_imports":
                    for spec in child.children:
                        if spec.type == "import_specifier":
                            name_node = spec.child_by_field_name("name")
                            alias_node = spec.child_by_field_name("alias")
                            if name_node:
                                name = self._text(name_node)
                                alias = self._text(alias_node) if alias_node else None
                                symbols.append((name, alias))

        self.imports.append(
            RawImport(
                module=raw_mod,
                is_relative=is_rel,
                relative_level=rel_level,
                symbols=symbols,
                line=node.start_point[0] + 1,
            )
        )

    def _parse_class_declaration(self, node: tree_sitter.Node, scope: str | None) -> None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return
        class_name = self._text(name_node)
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1

        # Heritage (extends / implements)
        bases: list[str] = []
        for child in node.children:
            if child.type == "class_heritage":
                for sub in child.children:
                    if sub.type == "extends_clause":
                        for base_child in sub.children:
                            if base_child.type in {"identifier", "type_identifier", "nested_identifier"}:
                                bases.append(self._text(base_child))

        if bases:
            self.inheritances.append(RawInheritance(class_name=class_name, base_names=bases, line=start_line))

        entity = RawEntity.create(
            rel_path=self.rel_path,
            kind="Class",
            name=class_name,
            start_line=start_line,
            end_line=end_line,
            start_byte=node.start_byte,
            end_byte=node.end_byte,
            scope=scope,
            signature=f"class {class_name} extends {', '.join(bases)}" if bases else f"class {class_name}",
            metadata={"bases": bases},
        )
        self.entities.append(entity)

        # Visit class body methods
        new_scope = f"{scope}.{class_name}" if scope else class_name
        body_node = node.child_by_field_name("body")
        if body_node:
            for child in body_node.children:
                if child.type == "method_definition":
                    self._parse_method_definition(child, new_scope)
                else:
                    self._visit_node(child, new_scope)

    def _parse_method_definition(self, node: tree_sitter.Node, scope: str) -> None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return
        method_name = self._text(name_node)
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1

        params_node = node.child_by_field_name("parameters")
        params_str = self._text(params_node) if params_node else "()"

        entity = RawEntity.create(
            rel_path=self.rel_path,
            kind="Method",
            name=method_name,
            start_line=start_line,
            end_line=end_line,
            start_byte=node.start_byte,
            end_byte=node.end_byte,
            scope=scope,
            signature=f"{method_name}{params_str}",
        )
        self.entities.append(entity)

        # Visit body for calls
        new_scope = f"{scope}.{method_name}"
        body_node = node.child_by_field_name("body")
        if body_node:
            for child in body_node.children:
                self._visit_node(child, new_scope)

    def _parse_function_declaration(self, node: tree_sitter.Node, scope: str | None) -> None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return
        func_name = self._text(name_node)
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1

        params_node = node.child_by_field_name("parameters")
        params_str = self._text(params_node) if params_node else "()"
        return_type_node = node.child_by_field_name("return_type")
        return_str = f": {self._text(return_type_node)}" if return_type_node else ""

        entity = RawEntity.create(
            rel_path=self.rel_path,
            kind="Function",
            name=func_name,
            start_line=start_line,
            end_line=end_line,
            start_byte=node.start_byte,
            end_byte=node.end_byte,
            scope=scope,
            signature=f"function {func_name}{params_str}{return_str}",
        )
        self.entities.append(entity)

        new_scope = f"{scope}.{func_name}" if scope else func_name
        body_node = node.child_by_field_name("body")
        if body_node:
            for child in body_node.children:
                self._visit_node(child, new_scope)

    def _parse_variable_declaration(self, node: tree_sitter.Node, scope: str | None) -> None:
        for child in node.children:
            if child.type == "variable_declarator":
                name_node = child.child_by_field_name("name")
                value_node = child.child_by_field_name("value")
                if not name_node or not value_node:
                    continue

                # CommonJS require: const x = require('./x')
                if value_node.type == "call_expression":
                    func_n = value_node.child_by_field_name("function")
                    args_n = value_node.child_by_field_name("arguments")
                    if func_n and self._text(func_n) == "require" and args_n:
                        for arg in args_n.children:
                            if arg.type == "string":
                                raw_mod = self._text(arg).strip("'\"`")
                                self.imports.append(
                                    RawImport(
                                        module=raw_mod,
                                        alias=self._text(name_node),
                                        is_relative=raw_mod.startswith(("./", "../")),
                                        line=node.start_point[0] + 1,
                                    )
                                )

                # Arrow function: const myFunc = (x) => ...
                if value_node.type == "arrow_function":
                    func_name = self._text(name_node)
                    start_line = node.start_point[0] + 1
                    end_line = node.end_point[0] + 1
                    params_node = value_node.child_by_field_name("parameters")
                    params_str = self._text(params_node) if params_node else "()"

                    entity = RawEntity.create(
                        rel_path=self.rel_path,
                        kind="Function",
                        name=func_name,
                        start_line=start_line,
                        end_line=end_line,
                        start_byte=node.start_byte,
                        end_byte=node.end_byte,
                        scope=scope,
                        signature=f"const {func_name} = {params_str} => ...",
                    )
                    self.entities.append(entity)

                    new_scope = f"{scope}.{func_name}" if scope else func_name
                    body_node = value_node.child_by_field_name("body")
                    if body_node:
                        self._visit_node(body_node, new_scope)

    def _parse_call_expression(self, node: tree_sitter.Node, scope: str | None) -> None:
        func_node = node.child_by_field_name("function")
        if not func_node:
            return

        caller = scope or "module"
        line = node.start_point[0] + 1

        if func_node.type == "identifier":
            callee_name = self._text(func_node)
            self.calls.append(RawCall(caller_scope=caller, callee_name=callee_name, line=line))
        elif func_node.type == "member_expression":
            prop_node = func_node.child_by_field_name("property")
            obj_node = func_node.child_by_field_name("object")
            if prop_node:
                callee_name = self._text(prop_node)
                callee_owner = self._text(obj_node) if obj_node else None
                self.calls.append(
                    RawCall(
                        caller_scope=caller,
                        callee_name=callee_name,
                        callee_owner=callee_owner,
                        line=line,
                    )
                )

                # Express route check: app.get('/path', handler) or router.post(...)
                if callee_owner and callee_owner.lower() in {"app", "router", "server"} and callee_name.upper() in HTTP_METHODS:
                    args_node = node.child_by_field_name("arguments")
                    if args_node and len(args_node.children) >= 2:
                        first_arg = args_node.children[1]  # index 0 is '(', index 1 is first arg
                        if first_arg.type == "string":
                            route_path = self._text(first_arg).strip("'\"`")
                            api_entity = RawEntity.create(
                                rel_path=self.rel_path,
                                kind="API",
                                name=f"{callee_name.upper()} {route_path}",
                                start_line=line,
                                end_line=line,
                                start_byte=node.start_byte,
                                end_byte=node.end_byte,
                                scope=scope,
                                metadata={"method": callee_name.upper(), "path": route_path, "line": line},
                            )
                            self.entities.append(api_entity)

    def _check_nextjs_route(self) -> None:
        p = Path(self.rel_path)
        parts = list(p.parts)
        if "api" in parts and p.name in {"route.ts", "route.js", "route.tsx", "route.jsx"}:
            api_idx = parts.index("api")
            route_parts = parts[api_idx + 1 : -1]
            route_str = "/" + "/".join(route_parts)
            route_str = route_str.replace("[", ":").replace("]", "")

            # Check if entities have GET, POST functions exported
            for entity in self.entities:
                if entity.kind == "Function" and entity.name.upper() in HTTP_METHODS:
                    api_entity = RawEntity.create(
                        rel_path=self.rel_path,
                        kind="API",
                        name=f"{entity.name.upper()} {route_str or '/'}",
                        start_line=entity.start_line,
                        end_line=entity.end_line,
                        start_byte=entity.start_byte,
                        end_byte=entity.end_byte,
                        scope=None,
                        metadata={"method": entity.name.upper(), "path": route_str or "/", "line": entity.start_line},
                    )
                    self.entities.append(api_entity)


from __future__ import annotations

import ast
import re
from typing import Any
import tree_sitter

from codecompass.extractor.models import (
    FileParseResult,
    RawCall,
    RawEntity,
    RawImport,
    RawInheritance,
)

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head"}


class PythonExtractor:
    def __init__(self, rel_path: str, code_bytes: bytes) -> None:
        self.rel_path = rel_path
        self.code_bytes = code_bytes
        self.entities: list[RawEntity] = []
        self.imports: list[RawImport] = []
        self.calls: list[RawCall] = []
        self.inheritances: list[RawInheritance] = []

    def extract(self, root_node: tree_sitter.Node) -> FileParseResult:
        self._visit_node(root_node, scope=None)
        return FileParseResult(
            rel_path=self.rel_path,
            language="Python",
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
        elif node_type == "import_from_statement":
            self._parse_import_from_statement(node)
            return
        elif node_type == "class_definition":
            self._parse_class_definition(node, scope, decorators=[])
            return
        elif node_type == "function_definition":
            self._parse_function_definition(node, scope, decorators=[])
            return
        elif node_type == "decorated_definition":
            self._parse_decorated_definition(node, scope)
            return
        elif node_type == "call":
            self._parse_call(node, scope)

        for child in node.children:
            self._visit_node(child, scope)

    def _parse_import_statement(self, node: tree_sitter.Node) -> None:
        for child in node.children:
            if child.type == "dotted_name":
                mod_name = self._text(child)
                self.imports.append(RawImport(module=mod_name, line=node.start_point[0] + 1))
            elif child.type == "aliased_import":
                name_node = child.child_by_field_name("name")
                alias_node = child.child_by_field_name("alias")
                if name_node:
                    mod_name = self._text(name_node)
                    alias = self._text(alias_node) if alias_node else None
                    self.imports.append(RawImport(module=mod_name, alias=alias, line=node.start_point[0] + 1))

    def _parse_import_from_statement(self, node: tree_sitter.Node) -> None:
        module_name = ""
        is_relative = False
        rel_level = 0
        symbols: list[tuple[str, str | None]] = []

        for child in node.children:
            if child.type == "relative_import":
                is_relative = True
                rel_text = self._text(child)
                rel_level = rel_text.count(".")
                remainder = rel_text.lstrip(".")
                if remainder:
                    module_name = remainder
            elif child.type == "dotted_name" and not module_name:
                module_name = self._text(child)
            elif child.type in {"dotted_name", "identifier"}:
                symbols.append((self._text(child), None))
            elif child.type == "aliased_import":
                orig = self._text(child.child_by_field_name("name"))
                alias_node = child.child_by_field_name("alias")
                alias = self._text(alias_node) if alias_node else None
                symbols.append((orig, alias))

        if module_name or is_relative or symbols:
            self.imports.append(
                RawImport(
                    module=module_name,
                    is_relative=is_relative,
                    relative_level=rel_level,
                    symbols=symbols,
                    line=node.start_point[0] + 1,
                )
            )

    def _parse_class_definition(self, node: tree_sitter.Node, scope: str | None, decorators: list[str]) -> None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return
        class_name = self._text(name_node)
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1

        # Superclasses
        superclasses_node = node.child_by_field_name("superclasses")
        bases: list[str] = []
        if superclasses_node:
            for child in superclasses_node.children:
                if child.type in {"identifier", "attribute"}:
                    bases.append(self._text(child))

        if bases:
            self.inheritances.append(RawInheritance(class_name=class_name, base_names=bases, line=start_line))

        # Body & docstring
        body_node = node.child_by_field_name("body")
        docstring = self._extract_docstring(body_node)

        entity = RawEntity.create(
            rel_path=self.rel_path,
            kind="Class",
            name=class_name,
            start_line=start_line,
            end_line=end_line,
            start_byte=node.start_byte,
            end_byte=node.end_byte,
            scope=scope,
            docstring=docstring,
            signature=f"class {class_name}({', '.join(bases)})" if bases else f"class {class_name}",
            metadata={"bases": bases, "decorators": decorators},
        )
        self.entities.append(entity)

        # Visit class body methods with class scope
        new_scope = f"{scope}.{class_name}" if scope else class_name
        if body_node:
            for child in body_node.children:
                if child.type == "function_definition":
                    self._parse_function_definition(child, new_scope, decorators=[])
                elif child.type == "decorated_definition":
                    self._parse_decorated_definition(child, new_scope)
                else:
                    self._visit_node(child, new_scope)

    def _parse_function_definition(self, node: tree_sitter.Node, scope: str | None, decorators: list[str]) -> None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return
        func_name = self._text(name_node)
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1

        params_node = node.child_by_field_name("parameters")
        params_str = self._text(params_node) if params_node else "()"
        return_type_node = node.child_by_field_name("return_type")
        return_type_str = f" -> {self._text(return_type_node)}" if return_type_node else ""
        signature = f"def {func_name}{params_str}{return_type_str}"

        body_node = node.child_by_field_name("body")
        docstring = self._extract_docstring(body_node)

        kind = "Method" if scope else "Function"
        entity = RawEntity.create(
            rel_path=self.rel_path,
            kind=kind,
            name=func_name,
            start_line=start_line,
            end_line=end_line,
            start_byte=node.start_byte,
            end_byte=node.end_byte,
            scope=scope,
            docstring=docstring,
            signature=signature,
            metadata={"decorators": decorators},
        )
        self.entities.append(entity)

        # Check decorators for API routes
        for dec in decorators:
            api_info = self._parse_api_decorator(dec, start_line)
            if api_info:
                api_entity = RawEntity.create(
                    rel_path=self.rel_path,
                    kind="API",
                    name=f"{api_info['method']} {api_info['path']}",
                    start_line=start_line,
                    end_line=end_line,
                    start_byte=node.start_byte,
                    end_byte=node.end_byte,
                    scope=scope,
                    metadata=api_info,
                )
                self.entities.append(api_entity)

        # Visit function body for calls
        new_scope = f"{scope}.{func_name}" if scope else func_name
        if body_node:
            for child in body_node.children:
                self._visit_node(child, new_scope)

    def _parse_decorated_definition(self, node: tree_sitter.Node, scope: str | None) -> None:
        decorators: list[str] = []
        definition_node: tree_sitter.Node | None = None

        for child in node.children:
            if child.type == "decorator":
                decorators.append(self._text(child))
            elif child.type in {"function_definition", "class_definition"}:
                definition_node = child

        if definition_node:
            if definition_node.type == "function_definition":
                self._parse_function_definition(definition_node, scope, decorators)
            elif definition_node.type == "class_definition":
                self._parse_class_definition(definition_node, scope, decorators)

    def _parse_call(self, node: tree_sitter.Node, scope: str | None) -> None:
        func_node = node.child_by_field_name("function")
        if not func_node:
            return

        caller = scope or "module"
        line = node.start_point[0] + 1

        if func_node.type == "identifier":
            callee_name = self._text(func_node)
            self.calls.append(RawCall(caller_scope=caller, callee_name=callee_name, line=line))
        elif func_node.type == "attribute":
            attr_node = func_node.child_by_field_name("attribute")
            obj_node = func_node.child_by_field_name("object")
            if attr_node:
                callee_name = self._text(attr_node)
                callee_owner = self._text(obj_node) if obj_node else None
                self.calls.append(
                    RawCall(
                        caller_scope=caller,
                        callee_name=callee_name,
                        callee_owner=callee_owner,
                        line=line,
                    )
                )

    def _extract_docstring(self, body_node: tree_sitter.Node | None) -> str | None:
        if not body_node:
            return None
        for child in body_node.children:
            if child.type == "expression_statement":
                for sub in child.children:
                    if sub.type == "string":
                        raw = self._text(sub)
                        # Strip python triple or single quotes
                        for quote in ('"""', "'''", '"', "'"):
                            if raw.startswith(quote) and raw.endswith(quote) and len(raw) >= 2 * len(quote):
                                return raw[len(quote) : -len(quote)].strip()
                        return raw.strip()
            elif child.type not in {"comment"}:
                break
        return None

    def _parse_api_decorator(self, dec_text: str, line: int) -> dict[str, Any] | None:
        # Matches e.g. @app.get("/users") or @router.post("/items", response_model=...)
        match = re.search(r"@\w+\.(get|post|put|patch|delete|options|head)\s*\(\s*['\"]([^'\"]+)['\"]", dec_text, re.IGNORECASE)
        if match:
            return {"method": match.group(1).upper(), "path": match.group(2), "line": line}

        # Matches Flask @app.route("/path", methods=["POST"])
        route_match = re.search(r"@\w+\.route\s*\(\s*['\"]([^'\"]+)['\"](?:.*methods=\[([^\]]+)\])?", dec_text, re.IGNORECASE)
        if route_match:
            path = route_match.group(1)
            methods_raw = route_match.group(2)
            method = "GET"
            if methods_raw:
                found_methods = re.findall(r"['\"]([A-Za-z]+)['\"]", methods_raw)
                if found_methods:
                    method = found_methods[0].upper()
            return {"method": method, "path": path, "line": line}
        return None


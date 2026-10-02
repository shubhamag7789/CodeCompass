import unittest
from codecompass.parser.engine import (
    EXTENSION_MAP,
    JS_LANGUAGE,
    PY_LANGUAGE,
    TS_LANGUAGE,
    TSX_LANGUAGE,
    get_parser_engine,
)


class ParserEngineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = get_parser_engine()

    def test_extension_detection(self) -> None:
        self.assertEqual(self.engine.detect_language(".py"), "Python")
        self.assertEqual(self.engine.detect_language(".js"), "JavaScript")
        self.assertEqual(self.engine.detect_language(".jsx"), "JavaScript")
        self.assertEqual(self.engine.detect_language(".ts"), "TypeScript")
        self.assertEqual(self.engine.detect_language(".tsx"), "TSX")
        self.assertIsNone(self.engine.detect_language(".unknown"))

    def test_parse_python(self) -> None:
        code = b"def greet(name: str) -> str:\n    return f'Hello, {name}'\n"
        tree = self.engine.parse(code, "Python")
        self.assertIsNotNone(tree)
        self.assertEqual(tree.root_node.type, "module")
        self.assertFalse(tree.root_node.has_error)

    def test_parse_typescript(self) -> None:
        code = b"interface User { id: number; name: string; }\nfunction getUser(): User { return { id: 1, name: 'Alice' }; }\n"
        tree = self.engine.parse(code, "TypeScript")
        self.assertIsNotNone(tree)
        self.assertEqual(tree.root_node.type, "program")
        self.assertFalse(tree.root_node.has_error)

    def test_parse_tsx(self) -> None:
        code = b"export const Button = ({ label }: { label: string }) => <button>{label}</button>;\n"
        tree = self.engine.parse(code, "TSX")
        self.assertIsNotNone(tree)
        self.assertEqual(tree.root_node.type, "program")
        self.assertFalse(tree.root_node.has_error)

    def test_error_tolerance_broken_code(self) -> None:
        # Tree-sitter must not throw an exception on syntax errors; it handles partial ASTs
        code = b"def incomplete_function(\n"
        tree = self.engine.parse(code, "Python")
        self.assertIsNotNone(tree)
        self.assertTrue(tree.root_node.has_error)


if __name__ == "__main__":
    unittest.main()


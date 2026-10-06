import unittest
from codecompass.extractor import extract_file


class ExtractorTest(unittest.TestCase):
    def test_extract_python_classes_functions_and_docstrings(self) -> None:
        code = b'''"""Module docstring."""

from .auth import AuthService
import os

class UserManager:
    """Manages system users."""
    def __init__(self, db: str):
        self.db = db

    def get_user(self, user_id: int) -> dict:
        """Fetch user by id."""
        return self._lookup(user_id)

    def _lookup(self, uid: int):
        pass

def calculate_tax(amount: float) -> float:
    return amount * 0.2
'''
        result = extract_file("services/users.py", code, "Python")

        self.assertEqual(result.language, "Python")
        self.assertEqual(len(result.imports), 2)

        # Check relative import
        rel_imp = [i for i in result.imports if i.is_relative]
        self.assertEqual(len(rel_imp), 1)
        self.assertEqual(rel_imp[0].symbols[0][0], "AuthService")

        # Check class
        classes = [e for e in result.entities if e.kind == "Class"]
        self.assertEqual(len(classes), 1)
        self.assertEqual(classes[0].name, "UserManager")
        self.assertEqual(classes[0].docstring, "Manages system users.")

        # Check methods
        methods = [e for e in result.entities if e.kind == "Method"]
        self.assertEqual(len(methods), 3)
        method_names = {m.name for m in methods}
        self.assertIn("get_user", method_names)
        self.assertIn("_lookup", method_names)

        # Check top-level function
        functions = [e for e in result.entities if e.kind == "Function"]
        self.assertEqual(len(functions), 1)
        self.assertEqual(functions[0].name, "calculate_tax")

        # Check calls
        calls = [c for c in result.calls if c.callee_name == "_lookup"]
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].callee_owner, "self")

    def test_extract_python_fastapi_and_flask_routes(self) -> None:
        code = b'''
from fastapi import FastAPI
app = FastAPI()

@app.get("/items/{item_id}")
async def read_item(item_id: int):
    return {"item_id": item_id}

@app.post("/items")
def create_item():
    pass
'''
        result = extract_file("main.py", code, "Python")
        apis = [e for e in result.entities if e.kind == "API"]
        self.assertEqual(len(apis), 2)

        api_routes = {(a.metadata["method"], a.metadata["path"]) for a in apis}
        self.assertIn(("GET", "/items/{item_id}"), api_routes)
        self.assertIn(("POST", "/items"), api_routes)

    def test_extract_typescript_classes_and_arrow_functions(self) -> None:
        code = b'''
import { Request, Response } from 'express';
import { BaseService } from '../base';

export class PaymentService extends BaseService {
    charge(amount: number): boolean {
        return this.process(amount);
    }
}

export const formatCurrency = (val: number): string => {
    return "$" + val.toFixed(2);
};
'''
        result = extract_file("src/services/payment.ts", code, "TypeScript")

        classes = [e for e in result.entities if e.kind == "Class"]
        self.assertEqual(len(classes), 1)
        self.assertEqual(classes[0].name, "PaymentService")

        # Inheritance
        self.assertEqual(len(result.inheritances), 1)
        self.assertEqual(result.inheritances[0].class_name, "PaymentService")
        self.assertEqual(result.inheritances[0].base_names, ["BaseService"])

        # Arrow function
        functions = [e for e in result.entities if e.kind == "Function"]
        self.assertEqual(len(functions), 1)
        self.assertEqual(functions[0].name, "formatCurrency")

        # Import with relative path
        rel_imp = [i for i in result.imports if i.is_relative]
        self.assertEqual(len(rel_imp), 1)
        self.assertEqual(rel_imp[0].module, "../base")

    def test_extract_express_api_routes(self) -> None:
        code = b'''
import express from 'express';
const app = express();

app.get('/api/users', (req, res) => {
    res.json([]);
});

router.post('/api/login', handleLogin);
'''
        result = extract_file("src/server.js", code, "JavaScript")
        apis = [e for e in result.entities if e.kind == "API"]
        self.assertEqual(len(apis), 2)

        routes = {(a.metadata["method"], a.metadata["path"]) for a in apis}
        self.assertIn(("GET", "/api/users"), routes)
        self.assertIn(("POST", "/api/login"), routes)


if __name__ == "__main__":
    unittest.main()


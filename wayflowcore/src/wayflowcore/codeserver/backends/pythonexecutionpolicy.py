# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""Python source validation and worker namespace policies."""

from __future__ import annotations

import ast
import builtins
from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping, Sequence


class PythonExecutionPolicy(ABC):
    """Policy controlling Python source execution inside a worker."""

    @abstractmethod
    def validate_script(self, source_code: str) -> None:
        """Validate source code intended for script execution."""
        raise NotImplementedError

    @abstractmethod
    def validate_function(self, source_code: str, function_name: str) -> None:
        """Validate source code and entry point for function execution."""
        raise NotImplementedError

    @abstractmethod
    def build_namespace(self) -> dict[str, object]:
        """Build the initial namespace for a worker execution."""
        raise NotImplementedError


class StrictPythonExecutionPolicy(PythonExecutionPolicy):
    """Restrict Python syntax, imports, builtins, and attribute access."""

    def __init__(self, allowed_imports: Iterable[str] = ()) -> None:
        """Initialize the policy with the permitted top-level modules."""
        self.allowed_imports = tuple(allowed_imports)
        self._allowed_imports = set(self.allowed_imports)

    def validate_script(self, source_code: str) -> None:
        """Reject unsafe syntax in a script before execution starts."""
        tree = ast.parse(source_code)
        _AstValidator(self._allowed_imports).visit(tree)

    def validate_function(self, source_code: str, function_name: str) -> None:
        """Validate one named synchronous function and its body."""
        tree = ast.parse(source_code)
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
        if len(tree.body) != 1 or len(functions) != 1:
            raise ValueError("Function source must define exactly one function")
        if functions[0].name != function_name:
            raise ValueError(f"Function '{function_name}' is not defined")
        _AstValidator(self._allowed_imports, allow_function=function_name).visit(tree)

    def build_namespace(self) -> dict[str, object]:
        """Build a namespace with restricted builtins and host integration."""
        old_import = builtins.__import__

        def limited_import(
            name: str,
            globals: Mapping[str, object] | None = None,
            locals: Mapping[str, object] | None = None,
            fromlist: Sequence[str] = (),
            level: int = 0,
        ) -> object:
            top_level = name.split(".")[0]
            if top_level not in self._allowed_imports:
                raise ImportError(f"Import of module '{top_level}' is not allowed")
            return old_import(name, globals, locals, fromlist, level)

        allowed = {
            name: getattr(builtins, name)
            for name in (
                "print",
                "range",
                "int",
                "float",
                "str",
                "len",
                "sum",
                "min",
                "max",
                "abs",
                "enumerate",
                "list",
                "dict",
                "set",
                "tuple",
                "Exception",
                "ValueError",
                "TypeError",
                "ZeroDivisionError",
                "RuntimeError",
            )
        }
        allowed["__import__"] = limited_import
        return {"__builtins__": allowed, "host": None}


class _AstValidator(ast.NodeVisitor):
    """Validate the restricted Python AST used by the strict policy."""

    forbidden_attrs = {"encode", "decode", "format", "format_map", "mro", "__subclasses__"}

    def __init__(self, allowed_imports: set[str], allow_function: str | None = None) -> None:
        self.allowed_imports = allowed_imports
        self.allow_function = allow_function
        self.function_count = 0

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if self.allow_function != node.name or self.function_count != 0:
            raise ValueError("Defining functions is not allowed")
        self.function_count += 1
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        raise ValueError("Async functions are not allowed")

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        raise ValueError("Defining classes is not allowed")

    def visit_Lambda(self, node: ast.Lambda) -> None:
        raise ValueError("Lambdas are not allowed")

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith("__") or node.attr in self.forbidden_attrs:
            raise ValueError(f"Attribute '{node.attr}' is not allowed")
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name is not None:
            raise ValueError("Exception binding is not allowed")
        self.generic_visit(node)

    def visit_Yield(self, node: ast.Yield) -> None:
        raise ValueError("Yield is not allowed")

    def visit_YieldFrom(self, node: ast.YieldFrom) -> None:
        raise ValueError("YieldFrom is not allowed")

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        raise ValueError("Walrus operator is not allowed")

    def visit_ListComp(self, node: ast.ListComp) -> None:
        raise ValueError("Comprehensions are not allowed")

    def visit_SetComp(self, node: ast.SetComp) -> None:
        raise ValueError("Comprehensions are not allowed")

    def visit_DictComp(self, node: ast.DictComp) -> None:
        raise ValueError("Comprehensions are not allowed")

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        raise ValueError("Generator expressions are not allowed")

    def visit_Global(self, node: ast.Global) -> None:
        raise ValueError("Global is not allowed")

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        raise ValueError("Nonlocal is not allowed")

    def visit_Name(self, node: ast.Name) -> None:
        if node.id.startswith("__"):
            raise ValueError("Dunder names are not allowed")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id in {
            "exec",
            "eval",
            "compile",
            "open",
            "__import__",
            "dir",
        }:
            raise ValueError(f"Calling '{node.func.id}' is not allowed")
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name.split(".")[0] not in self.allowed_imports:
                raise ValueError(f"Import of module '{alias.name.split('.')[0]}' is not allowed")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level > 0:
            raise ValueError("Relative imports are not allowed")
        module = node.module or ""
        top_level = module.split(".")[0]
        if top_level and top_level not in self.allowed_imports:
            raise ValueError(f"Import from module '{module}' is not allowed")
        self.generic_visit(node)

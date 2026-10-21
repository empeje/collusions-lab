"""Standalone static invariant checker for safehub (Milestone 6B fixture).

Scans ``safehub`` for ``@privileged`` functions that fail to call ``require_auth`` before
acting, using real AST analysis. Exits non-zero on violation.

The check is intentionally *meaningful* (not a symbol-presence test): it verifies that
``require_auth`` is actually invoked inside the decorated function body, so a change that
drops the authorization call is caught even though the decorator remains.
"""

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PKG = ROOT / "safehub"


def _decorator_names(node):
    names = []
    for d in node.decorator_list:
        if isinstance(d, ast.Name):
            names.append(d.id)
        elif isinstance(d, ast.Attribute):
            names.append(d.attr)
    return names


def _calls_require_auth(func_node):
    for n in ast.walk(func_node):
        if isinstance(n, ast.Call):
            f = n.func
            name = f.id if isinstance(f, ast.Name) else getattr(f, "attr", None)
            if name == "require_auth":
                return True
    return False


def main():
    violations = []
    if not PKG.exists():
        print("ERROR: safehub package not found")
        return 2
    for path in sorted(PKG.glob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            violations.append(f"{path.name}: syntax error: {exc}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if "privileged" in _decorator_names(node):
                    if not _calls_require_auth(node):
                        violations.append(
                            f"{path.name}:{node.lineno}: "
                            f"@privileged {node.name}() does not call require_auth()"
                        )
    if violations:
        print("INVARIANT VIOLATIONS:")
        for v in violations:
            print("  - " + v)
        return 1
    print("invariant_check: OK (no violations)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

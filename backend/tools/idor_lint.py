"""Static IDOR / cross-tenant leak check (threat-model §T1).

Why
---
Multi-tenant isolation in this codebase is enforced *only* at the application
layer: every query against an org-scoped table must constrain by
``<Model>.org_id == <caller's org>``. There is no Postgres row-level security to
catch a mistake. The residual risk (threat-model §T1) is that a newly-added
query forgets its ``org_id`` predicate and silently returns another tenant's
rows.

What this does
--------------
Parses ``app/routers`` with the ``ast`` module and flags any
``select(<OrgScopedModel>)`` whose enclosing function never references
``org_id``. It is intentionally a *coarse* function-level heuristic — cheap,
zero-dependency, and false-positive-free on the current tree — rather than full
dataflow analysis.

Legitimately org-independent queries (scoped instead by a primary key that is
itself the caller's identity, or by a signed token) are exempted with an inline
``# idor-safe: <reason>`` marker on the ``select(...)`` statement. The marker
forces the author to state *why* a query is safe without an ``org_id`` filter.

Usage
-----
    python -m tools.idor_lint          # from the backend/ directory
Exits non-zero and prints each offending site if any are found. Also imported
by ``tests/test_idor_lint.py`` so the check runs in the normal test suite.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

# Resolve paths relative to the backend/ root regardless of the cwd.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_MODELS_DIR = _BACKEND_ROOT / "app" / "models"
_ROUTERS_DIR = _BACKEND_ROOT / "app" / "routers"

_SUPPRESS_MARKER = "idor-safe"


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    model: str
    function: str

    def __str__(self) -> str:
        return (
            f"{self.path}:{self.line}: select({self.model}) in {self.function}() "
            f"has no org_id predicate and no '# {_SUPPRESS_MARKER}: <reason>' marker"
        )


def org_scoped_models(models_dir: Path = _MODELS_DIR) -> set[str]:
    """Return the set of ORM class names that inherit from ``OrgScoped``."""
    names: set[str] = set()
    for path in models_dir.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and any(
                isinstance(base, ast.Name) and base.id == "OrgScoped"
                for base in node.bases
            ):
                names.add(node.name)
    return names


def _suppressed(source_lines: list[str], call: ast.Call) -> bool:
    """True if the select() statement carries an inline ``# idor-safe`` marker.

    Scans the physical lines the call spans plus up to three lines immediately
    above it, so the justification comment can sit on the ``select(...)`` line,
    anywhere in a multi-line ``select(...).where(...)`` chain, or in a short
    comment block directly above the enclosing statement.
    """
    start = max(1, call.lineno - 3)
    end = getattr(call, "end_lineno", call.lineno)
    for lineno in range(start, end + 1):
        line = source_lines[lineno - 1] if lineno - 1 < len(source_lines) else ""
        if "#" in line and _SUPPRESS_MARKER in line.split("#", 1)[1]:
            return True
    return False


def _function_references_org_id(func: ast.AST) -> bool:
    for node in ast.walk(func):
        if isinstance(node, ast.Name) and node.id == "org_id":
            return True
        if isinstance(node, ast.Attribute) and node.attr == "org_id":
            return True
    return False


def _display_path(path: Path) -> str:
    """Path relative to backend/ when possible, else the raw path (temp files)."""
    try:
        return str(path.relative_to(_BACKEND_ROOT))
    except ValueError:
        return str(path)


def scan_file(path: Path, models: set[str]) -> list[Finding]:
    source = path.read_text(encoding="utf-8")
    source_lines = source.splitlines()
    tree = ast.parse(source)
    findings: list[Finding] = []

    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if _function_references_org_id(func):
            continue
        for node in ast.walk(func):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "select"
                and node.args
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id in models
                and not _suppressed(source_lines, node)
            ):
                findings.append(
                    Finding(
                        path=_display_path(path),
                        line=node.lineno,
                        model=node.args[0].id,
                        function=func.name,
                    )
                )
    return findings


def scan(routers_dir: Path = _ROUTERS_DIR) -> list[Finding]:
    models = org_scoped_models()
    findings: list[Finding] = []
    for path in sorted(routers_dir.rglob("*.py")):
        findings.extend(scan_file(path, models))
    return findings


def main() -> int:
    findings = scan()
    if not findings:
        print("idor_lint: OK — every org-scoped select() is org-filtered or marked idor-safe.")
        return 0
    print("idor_lint: potential cross-tenant (IDOR) queries found:")
    for finding in findings:
        print(f"  {finding}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

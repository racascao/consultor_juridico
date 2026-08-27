"""Proteção mínima da independência de frameworks no domínio v0.2."""

import ast
from pathlib import Path

FORBIDDEN_ROOTS = {"httpx", "langgraph", "rich", "sqlalchemy", "typer"}


def test_domain_does_not_import_frameworks():
    domain = Path("src/consultor_juridico/domain")
    violations: list[str] = []
    for path in sorted(domain.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                if name.split(".", maxsplit=1)[0] in FORBIDDEN_ROOTS:
                    violations.append(f"{path}:{node.lineno}:{name}")

    assert violations == []

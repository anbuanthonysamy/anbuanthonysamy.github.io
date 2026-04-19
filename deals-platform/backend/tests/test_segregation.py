"""Segregation test — the public-only modules (CS1 origination, CS2 carve-outs)
must not import from client-only modules (post_deal, working_capital), and the
other way around is also forbidden.
"""
from __future__ import annotations

import ast
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"

PUBLIC_MODULES = (
    APP / "modules" / "origination",
    APP / "modules" / "carve_outs",
)
CLIENT_MODULES = (
    APP / "modules" / "post_deal",
    APP / "modules" / "working_capital",
)


def _imports(py: Path) -> list[str]:
    tree = ast.parse(py.read_text())
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            out.append(node.module)
        elif isinstance(node, ast.Import):
            for a in node.names:
                out.append(a.name)
    return out


def _walk(paths: tuple[Path, ...]) -> list[Path]:
    out: list[Path] = []
    for p in paths:
        out.extend([f for f in p.rglob("*.py")])
    return out


def test_public_modules_do_not_import_client_modules():
    bad: list[str] = []
    for py in _walk(PUBLIC_MODULES):
        for m in _imports(py):
            if m.startswith("app.modules.post_deal") or m.startswith("app.modules.working_capital"):
                bad.append(f"{py} imports {m}")
    assert not bad, "Public-only module imports client-only module:\n" + "\n".join(bad)


def test_client_modules_do_not_import_public_modules():
    # They may read public-scope Evidence rows via shared APIs, but they must
    # not import from the public-only modules directly.
    bad: list[str] = []
    for py in _walk(CLIENT_MODULES):
        for m in _imports(py):
            if m.startswith("app.modules.origination") or m.startswith("app.modules.carve_outs"):
                bad.append(f"{py} imports {m}")
    assert not bad, "Client-only module imports public-only module:\n" + "\n".join(bad)

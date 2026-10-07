"""Boundaries that keep the plugin system honest."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICE_SOURCES = [
    *ROOT.glob("services/*_service/src/**/*.py"),
    *ROOT.glob("services/devkit_common/src/**/*.py"),
]
# Deprecated compatibility shim; removed with the ingestion rework (#15).
ALLOWED = {ROOT / "services/rag_service/src/rag_service/pdf.py"}


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_services_get_implementations_from_the_registry_only() -> None:
    assert SERVICE_SOURCES
    offenders = {
        str(path.relative_to(ROOT)): sorted(
            m for m in _imported_modules(path) if m.startswith("ldk_plugin_")
        )
        for path in SERVICE_SOURCES
        if path not in ALLOWED
    }
    assert {path: mods for path, mods in offenders.items() if mods} == {}


def test_core_depends_on_no_service_or_plugin() -> None:
    for path in ROOT.glob("services/core/src/ldk_core/**/*.py"):
        forbidden = {
            m
            for m in _imported_modules(path)
            if m.startswith(
                (
                    "ldk_plugin_",
                    "devkit_common",
                    "llm_service",
                    "rag_service",
                    "mcp_service",
                    "fastapi",
                )
            )
        }
        assert not forbidden, f"{path.relative_to(ROOT)} imports {forbidden}"

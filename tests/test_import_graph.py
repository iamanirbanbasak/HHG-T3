"""NFR-013 / FR-054: dependency direction and environment access.

Frozen contract from agent-prompts/02-architecture-execution.md section 2.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "facechain"


def imports_of(path: Path) -> set[str]:
    """Top-level project modules imported by a file.

    Collects MODULE names only, never the imported symbol names -- `from .errors import
    FaceChainError` is a dependency on `errors`, not on `FaceChainError`.
    """
    out: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ImportFrom):
            if node.level:  # relative: from .errors import X / from ..face.embed import Y
                mod = (node.module or "").split(".")[0]
            elif (node.module or "").startswith("facechain"):
                parts = (node.module or "").split(".")
                mod = parts[1] if len(parts) > 1 else ""
            else:
                continue
            if mod:
                out.add(mod)
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name.startswith("facechain."):
                    parts = a.name.split(".")
                    if len(parts) > 1:
                        out.add(parts[1])
    return out


@pytest.mark.parametrize("leaf", ["config.py", "errors.py"])
def test_leaves_import_nothing_from_the_project(leaf):
    """config and errors are the bottom of the graph."""
    imports = imports_of(SRC / leaf)
    assert imports <= {"errors"}, f"{leaf} imports {imports}"


@pytest.mark.parametrize("layer", [
    "face/detect.py", "face/embed.py", "face/similarity.py",
    "search/lens.py", "search/uploader.py", "search/candidates.py", "search/fetch.py",
    "evidence.py", "chain/registry.py", "chain/compile.py",
])
def test_lower_layers_never_import_pipeline_or_cli(layer):
    imports = imports_of(SRC / layer)
    assert "pipeline" not in imports, f"{layer} imports pipeline"
    assert "cli" not in imports, f"{layer} imports cli"


def test_evidence_does_not_import_face_or_search():
    """evidence receives plain data; it must not reach into the face or search layers."""
    imports = imports_of(SRC / "evidence.py")
    assert "face" not in imports and "search" not in imports


def _reads_environment(path: Path) -> bool:
    """True if the file actually accesses the environment.

    Checked via AST rather than a text grep: a comment or docstring that mentions os.environ --
    for instance one explaining why a module must not touch it -- is documentation, not a
    violation.
    """
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Attribute) and node.attr == "environ":
            if isinstance(node.value, ast.Name) and node.value.id == "os":
                return True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in ("getenv", "putenv") and isinstance(node.func.value, ast.Name):
                if node.func.value.id == "os":
                    return True
    return False


def test_only_config_reads_the_environment():
    # cli.py is permitted: it loads .env into the environment at the boundary before load_config.
    # __init__.py is permitted: it sets ORT_DISABLE_TELEMETRY, which must be in the environment
    # before onnxruntime is imported. That is a third-party kill switch, not project configuration.
    offenders = [
        f.relative_to(SRC).as_posix()
        for f in SRC.rglob("*.py")
        if _reads_environment(f) and f.name not in ("config.py", "cli.py", "__init__.py")
    ]
    assert offenders == [], f"environment access outside config.py: {offenders}"


def test_similarity_is_dependency_free():
    """The most-tested, least-coupled module in the project. Keep it that way."""
    assert imports_of(SRC / "face" / "similarity.py") <= {"errors"}

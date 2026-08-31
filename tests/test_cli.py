"""CLI behaviour, exit codes, and output discipline."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest
from typer.testing import CliRunner

from facechain.cli import EXIT_MISMATCH, EXIT_NO_FACE, EXIT_NO_MATCH, EXIT_OK, app

runner = CliRunner()
FX = Path(__file__).parent / "fixtures"

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


class TestCommandSurface:
    @pytest.mark.parametrize("cmd", ["scan", "search", "run", "verify", "deploy", "anchor"])
    def test_every_command_has_help(self, cmd):
        r = runner.invoke(app, [cmd, "--help"])
        assert r.exit_code == 0

    def test_root_help_lists_all_six(self):
        r = runner.invoke(app, ["--help"])
        assert r.exit_code == 0
        for cmd in ("scan", "search", "run", "verify", "deploy", "anchor"):
            assert cmd in r.output


class TestScan:
    def test_scan_reports_a_real_detection(self):
        r = runner.invoke(app, ["scan", "--image", str(FX / "faces_multi.jpg")])
        assert r.exit_code == EXIT_OK
        assert "faces detected" in r.output
        assert "512-d" in r.output

    def test_no_face_exits_with_dedicated_code(self):
        r = runner.invoke(app, ["scan", "--image", str(FX / "face_none.jpg")])
        assert r.exit_code == EXIT_NO_FACE
        assert "NoFaceDetectedError" in r.output

    def test_malformed_image_does_not_traceback(self):
        r = runner.invoke(app, ["scan", "--image", str(FX / "malformed.jpg")])
        assert r.exit_code == EXIT_NO_FACE
        assert "Traceback" not in r.output


def _executable_source(path: Path) -> str:
    """Source with docstrings and comments stripped.

    The discipline checks below must scan code that RENDERS output, not prose that forbids the
    practice -- several modules carry docstrings explicitly warning against percentage wording,
    and those are the opposite of a violation.
    """
    import ast, io, tokenize

    tree = ast.parse(path.read_text())
    doc_lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            d = ast.get_docstring(node, clean=False)
            if d is not None and node.body:
                s = node.body[0]
                doc_lines.update(range(s.lineno, (s.end_lineno or s.lineno) + 1))

    out = []
    for i, line in enumerate(path.read_text().splitlines(), 1):
        if i in doc_lines:
            continue
        out.append(line)
    code = "\n".join(out)
    # strip trailing comments
    stripped = []
    for line in code.splitlines():
        try:
            toks = list(tokenize.generate_tokens(io.StringIO(line).readline))
            line = "".join(
                t.string for t in toks if t.type not in (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE)
            )
        except (tokenize.TokenError, IndentationError):
            line = line.split("#")[0]
        stripped.append(line)
    return "\n".join(stripped)


class TestOutputDiscipline:
    """HC-19: a cosine similarity is never rendered as a percentage or 'confidence'."""

    def test_no_percentage_next_to_similarity_in_executable_code(self):
        src = Path(__file__).resolve().parents[1] / "src" / "facechain"
        bad = re.compile(
            r"(cosine|similarity|score)[^\n]{0,40}[%]|[%][^\n]{0,20}(cosine|similarity)", re.I
        )
        hits = [
            (f.name, m.group(0))
            for f in src.rglob("*.py")
            for m in bad.finditer(_executable_source(f))
        ]
        assert hits == [], f"similarity rendered as a percentage: {hits}"

    def test_no_confidence_wording_in_executable_code(self):
        src = Path(__file__).resolve().parents[1] / "src" / "facechain"
        hits = [
            (f.name, line.strip()[:80])
            for f in src.rglob("*.py")
            for line in _executable_source(f).splitlines()
            if "confidence" in line.lower()
        ]
        assert hits == [], f"'confidence' used to describe a score: {hits}"

    def test_scan_output_contains_no_percent_sign_on_scores(self):
        r = runner.invoke(app, ["scan", "--image", str(FX / "faces_multi.jpg")])
        assert "%" not in r.output


class TestVerifyCli:
    def test_verify_requires_a_contract_address(self, written_run, monkeypatch):
        monkeypatch.delenv("CONTRACT_ADDRESS", raising=False)
        monkeypatch.chdir(written_run.parent)
        r = runner.invoke(app, ["verify", "--record-id", "0", "--run-dir", str(written_run)])
        assert r.exit_code == EXIT_MISMATCH
        assert "contract_address" in r.output

    def test_missing_run_dir_is_rejected(self):
        r = runner.invoke(app, ["verify", "--record-id", "0", "--run-dir", "/nonexistent"])
        assert r.exit_code != EXIT_OK

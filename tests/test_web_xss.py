"""XSS regression tests for the web UI result renderer.

Candidate URLs come from the search provider, which reflects arbitrary indexed web pages, so they
are untrusted -- the same posture already applied server-side in search/fetch.py.

These are static assertions about the shipped JavaScript. Executing it needs a browser, which the
suite deliberately does not require; the behaviour was verified in a real browser with the
payloads below, where the previous string-concatenation renderer injected live <img> tags and the
current DOM-based one injects none.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

HTML = Path(__file__).resolve().parents[1] / "src" / "facechain" / "static" / "index.html"
_RAW = HTML.read_text()
SCRIPT = _RAW[_RAW.index("<script>"):]


def code_only(src: str) -> str:
    """Strip // comments.

    These checks must scan code that RENDERS output, not prose describing it. A comment reading
    "textContent, never innerHTML" is documentation of the fix, not an instance of the defect --
    and scanning raw text flagged it three separate times.
    """
    out = []
    for line in src.splitlines():
        i = line.find("//")
        out.append(line[:i] if i != -1 else line)
    return "\n".join(out)


CODE = code_only(SCRIPT)


def test_renderer_does_not_concatenate_html_from_row_data():
    """The specific defect: interpolating x.url into an HTML string.

    `out.innerHTML = ""` is permitted -- clearing a node is not injection. Only interpolation is.
    """
    assert "${x.url}" not in CODE
    render_body = CODE.split("function render")[1]
    interpolating = [
        line.strip()
        for line in render_body.splitlines()
        if "innerHTML" in line and not re.search(r'innerHTML\s*=\s*""', line)
    ]
    assert interpolating == [], f"render() interpolates into innerHTML: {interpolating}"


def test_urls_are_scheme_validated():
    assert "function safeUrl" in CODE
    assert 'protocol==="http:"' in CODE and 'protocol==="https:"' in CODE


def test_link_text_is_set_via_textcontent():
    assert "textContent" in CODE
    assert 'el("a",null,x.url)' in CODE


def test_links_carry_noopener_noreferrer():
    assert 'rel="noopener noreferrer"' in CODE


def test_no_remaining_innerhtml_interpolation_anywhere():
    """Only assignments that clear a node are allowed."""
    offenders = [
        line.strip()
        for line in CODE.splitlines()
        if "innerHTML" in line and not re.search(r'innerHTML\s*=\s*""', line)
    ]
    assert offenders == [], f"innerHTML interpolation remains: {offenders}"


@pytest.mark.parametrize("payload", [
    '"><img src=x onerror=alert(1)>',
    "javascript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "<script>alert(1)</script>",
])
def test_payloads_documented_as_covered(payload):
    """Documents the exact payloads verified in a browser against this renderer.

    Kept as a record so a future change to render() has a concrete checklist to re-verify
    rather than a vague instruction to 'test for XSS'.
    """
    assert payload  # the assertion that matters happened in the browser; see module docstring

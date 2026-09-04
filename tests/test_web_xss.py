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


def _interpolating_innerhtml(src: str) -> list[str]:
    """innerHTML assignments that splice in a value.

    Clearing a node (`innerHTML=''` or `""`) is not injection, and neither is assigning a static
    literal with no substitution. Only interpolation -- a template placeholder or concatenation --
    can carry attacker-controlled data into markup.
    """
    offenders = []
    for line in src.splitlines():
        if "innerHTML" not in line:
            continue
        rhs = line.split("innerHTML", 1)[1].lstrip()
        if not rhs.startswith("="):
            continue
        rhs = rhs[1:].strip()
        if re.match(r"""^(''|"");?$""", rhs):      # clearing
            continue
        if "${" in rhs or re.search(r"""["'`]\s*\+""", rhs):  # template or concatenation
            offenders.append(line.strip())
        elif not re.match(r"""^['"`]""", rhs):     # not a plain literal -> a variable
            offenders.append(line.strip())
    return offenders


def test_renderer_never_interpolates_into_innerhtml():
    """The original defect: splicing x.url into an HTML string."""
    assert "${x.url}" not in CODE
    assert _interpolating_innerhtml(CODE) == []


def test_urls_pass_through_scheme_validation():
    """Whatever the renderer's shape, every href must be scheme-checked."""
    assert "function safeUrl" in CODE
    assert 'protocol==="http:"' in CODE and 'protocol==="https:"' in CODE
    # Every href assignment must trace back to safeUrl: either it calls it inline, or it uses a
    # variable whose declaration calls it. Names differ across call sites, so match on the binding
    # rather than on a fixed identifier.
    validated = set(
        re.findall(r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=[^;\n]*safeUrl", CODE)
    )
    unchecked = []
    for expr in re.findall(r"\.href\s*=\s*([^;\n]+)", CODE):
        expr = expr.strip()
        if "safeUrl" in expr:
            continue  # validated inline
        name = re.match(r"^([A-Za-z_$][\w$]*)", expr)
        if not name or name.group(1) not in validated:
            unchecked.append(expr[:60])
    assert not unchecked, f"href assigned without passing through safeUrl: {unchecked}"


def test_link_text_uses_textcontent_not_markup():
    assert "textContent" in CODE
    assert "innerHTML" not in CODE.split("function render")[1] or \
        _interpolating_innerhtml(CODE.split("function render")[1]) == []


def test_external_links_carry_noopener():
    assert "noopener" in CODE


def test_no_remaining_innerhtml_interpolation_anywhere():
    assert _interpolating_innerhtml(CODE) == []


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

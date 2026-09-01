"""Security regression tests for the local web server.

Two findings this file locks down, both confirmed exploitable before the fix:

1. Arbitrary local file access. `/api/run` accepted any path. Because the pipeline UPLOADS the
   probe image to a public host to run the search, naming a file outside the project turned local
   file disclosure into exfiltration.
2. No CSRF defence. A cross-origin POST returned 200, so any page open in the browser could start
   a run -- including `capture: true`, which switches on the camera.

"It only binds to localhost" is not a defence for either: any page in the browser, and any local
process, can reach 127.0.0.1.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from facechain.errors import FaceChainError
from facechain.web import ALLOWED_SUFFIXES, PROJECT_ROOT, CSRF_TOKEN, safe_image_path


class TestPathConfinement:
    @pytest.mark.parametrize("path", [
        "/etc/hosts",
        "/etc/passwd",
        "../../../../etc/passwd",
        "~/Pictures/private.jpg",
        "/tmp/whatever.jpg",
    ])
    def test_paths_outside_the_project_are_rejected(self, path):
        with pytest.raises(FaceChainError) as e:
            safe_image_path(path)
        assert "project directory" in str(e.value) or "not found" in str(e.value)

    def test_empty_path_rejected(self):
        with pytest.raises(FaceChainError):
            safe_image_path("")

    def test_non_image_suffix_rejected(self, tmp_path, monkeypatch):
        f = PROJECT_ROOT / "_sec_probe.txt"
        f.write_text("x")
        try:
            with pytest.raises(FaceChainError) as e:
                safe_image_path("_sec_probe.txt")
            assert "unsupported image type" in str(e.value)
        finally:
            f.unlink(missing_ok=True)

    def test_missing_file_inside_project_rejected(self):
        with pytest.raises(FaceChainError) as e:
            safe_image_path("definitely_not_here.jpg")
        assert "not found" in str(e.value)

    def test_valid_relative_image_accepted(self):
        p = safe_image_path("tests/fixtures/faces_multi.jpg")
        assert p.is_file()
        assert p.resolve().is_relative_to(PROJECT_ROOT)

    def test_allowed_suffixes_are_images_only(self):
        assert ".txt" not in ALLOWED_SUFFIXES and ".py" not in ALLOWED_SUFFIXES
        assert ".jpg" in ALLOWED_SUFFIXES and ".heic" in ALLOWED_SUFFIXES


class TestCsrf:
    def test_token_is_generated_and_long(self):
        assert len(CSRF_TOKEN) >= 32

    def test_page_carries_the_placeholder_for_injection(self):
        html = (Path(__file__).resolve().parents[1]
                / "src" / "facechain" / "static" / "index.html").read_text()
        assert "__CSRF_TOKEN__" in html, "page must receive a per-process token"
        assert "x-csrf-token" in html, "page must send the token on API writes"


class TestEndpoints:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient

        from facechain.web import create_app

        return TestClient(create_app())

    def test_post_without_token_is_forbidden(self, client):
        r = client.post("/api/run", json={"image": "me.jpg"})
        assert r.status_code == 403

    def test_post_with_wrong_token_is_forbidden(self, client):
        r = client.post("/api/run", json={"image": "me.jpg"},
                        headers={"x-csrf-token": "nope"})
        assert r.status_code == 403

    def test_cross_origin_is_forbidden_even_with_a_valid_token(self, client):
        r = client.post("/api/run", json={"image": "me.jpg"},
                        headers={"x-csrf-token": CSRF_TOKEN,
                                 "origin": "https://evil.example.com"})
        assert r.status_code == 403

    def test_valid_token_is_accepted(self, client):
        r = client.post("/api/run", json={"image": "tests/fixtures/faces_multi.jpg"},
                        headers={"x-csrf-token": CSRF_TOKEN})
        assert r.status_code == 200 and "job" in r.json()

    def test_index_injects_the_token(self, client):
        body = client.get("/").text
        assert "__CSRF_TOKEN__" not in body
        assert CSRF_TOKEN in body

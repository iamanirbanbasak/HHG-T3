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


class TestConfigEndpoint:
    """Regression: /api/config raised NameError because a careless edit injected
    `result.provider` into it, where no `result` exists. Every endpoint is now smoke-tested."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient

        from facechain.web import create_app

        return TestClient(create_app())

    def test_config_returns_200_and_expected_keys(self, client):
        r = client.get("/api/config")
        assert r.status_code == 200
        assert set(r.json()) >= {
            "provider", "network", "threshold", "has_serpapi", "has_imgbb", "has_facecheck",
        }

    def test_config_never_leaks_key_values(self, client):
        body = r'{}'.format(client.get("/api/config").text)
        assert "has_serpapi" in body
        for v in ("sk-", "live_", "3ef94e"):
            assert v not in body

    def test_index_returns_200(self, client):
        assert client.get("/").status_code == 200

    def test_unknown_job_returns_404_not_500(self, client):
        assert client.get("/api/job/deadbeef").status_code == 404


class TestTamperIsOperatorTriggered:
    """The tamper test must not run on its own.

    Flipping a byte of evidence is the one destructive-looking thing this tool does. It used to
    happen automatically at the end of every run, which meant an operator watched their evidence
    get altered without asking. It is now a separate, explicit request.
    """

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient

        from facechain.web import create_app

        return TestClient(create_app())

    def test_run_no_longer_performs_the_tamper_test(self):
        """The run path must not reference tamper=True anywhere."""
        src = (Path(__file__).resolve().parents[1]
               / "src" / "facechain" / "web.py").read_text()
        run_body = src[src.index("def _run_job"):src.index("def create_app")]
        assert "tamper=True" not in run_body

    def test_tamper_endpoint_requires_csrf(self, client):
        r = client.post("/api/tamper", json={"run_dir": "artifacts/x", "record_id": 0})
        assert r.status_code == 403

    def test_tamper_endpoint_rejects_cross_origin(self, client):
        r = client.post("/api/tamper", json={"run_dir": "artifacts/x", "record_id": 0},
                        headers={"x-csrf-token": CSRF_TOKEN,
                                 "origin": "https://evil.example.com"})
        assert r.status_code == 403

    @pytest.mark.parametrize("path", ["/etc", "../../etc", "/tmp", "uploads"])
    def test_run_dir_confined_to_artifacts(self, path):
        from facechain.web import safe_run_dir

        with pytest.raises(FaceChainError):
            safe_run_dir(path)

    def test_missing_run_dir_rejected(self):
        from facechain.web import safe_run_dir

        with pytest.raises(FaceChainError):
            safe_run_dir("artifacts/does-not-exist")

    def test_empty_run_dir_rejected(self):
        from facechain.web import safe_run_dir

        with pytest.raises(FaceChainError):
            safe_run_dir("")

    def test_bad_record_id_is_a_400_not_a_500(self, client):
        r = client.post("/api/tamper",
                        json={"run_dir": "artifacts", "record_id": "not-an-int"},
                        headers={"x-csrf-token": CSRF_TOKEN})
        assert r.status_code == 400


class TestNetworkDefault:
    """Regression: the web layer forced network="local", so a configured testnet in .env was
    ignored and runs anchored to a throwaway in-process chain while the UI showed the real
    contract address."""

    def test_configured_network_is_respected(self, monkeypatch):
        from facechain.web import _cfg

        monkeypatch.setenv("NETWORK", "sepolia")
        assert _cfg({}).network == "sepolia"

    def test_explicit_request_network_still_wins(self, monkeypatch):
        from facechain.web import _cfg

        monkeypatch.setenv("NETWORK", "sepolia")
        assert _cfg({"network": "local"}).network == "local"

    def test_defaults_to_local_when_nothing_configured(self, monkeypatch):
        """With no request value and no environment value, local is the fallback.

        _cfg loads .env, which sets NETWORK, so the loader is stubbed out here -- otherwise the
        test asserts against the developer's own configuration rather than the default.
        """
        import facechain.cli
        from facechain.web import _cfg

        # _cfg imports _load_dotenv from facechain.cli at call time, so patch it at the source.
        monkeypatch.setattr(facechain.cli, "_load_dotenv", lambda: None)
        monkeypatch.delenv("NETWORK", raising=False)
        assert _cfg({}).network == "local"

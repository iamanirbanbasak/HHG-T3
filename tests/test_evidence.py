"""Evidence determinism tests.

With test_verify_tamper.py, these are the two suites that protect the actual claim made to
judges. They are written before the pipeline they validate exists.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from facechain.errors import FaceChainError
from facechain.evidence import (
    POST_TEXT,
    canonicalise,
    evidence_hash,
    rebuild_from_artifacts,
    sha256_file,
    similarity_bps,
)

GOLDEN = Path(__file__).parent / "fixtures" / "golden_bundle.json"
GOLDEN_HASH = Path(__file__).parent / "fixtures" / "golden_hash.txt"


class TestCanonicalJson:
    def test_key_order_does_not_change_bytes(self):
        a = {"b": 1, "a": {"z": 2, "y": 3}}
        b = {"a": {"y": 3, "z": 2}, "b": 1}
        assert canonicalise(a) == canonicalise(b)

    def test_uses_tight_separators(self):
        assert canonicalise({"a": 1, "b": 2}) == b'{"a":1,"b":2}'

    def test_ascii_escaped(self):
        assert b"\\u00e9" in canonicalise({"name": "café"})

    def test_stable_across_repeated_calls(self, bundle):
        assert canonicalise(bundle) == canonicalise(bundle)


class TestGolden:
    def test_golden_hash_has_not_drifted(self):
        """If this fails, find out why. Never regenerate the golden file to make it pass."""
        golden = json.loads(GOLDEN.read_text())
        expected = GOLDEN_HASH.read_text().strip()
        assert evidence_hash(golden).hex() == expected

    def test_hash_stable_in_a_fresh_interpreter(self):
        """Guards against PYTHONHASHSEED or dict-ordering influencing the digest."""
        code = (
            "import json,sys;from facechain.evidence import evidence_hash;"
            f"print(evidence_hash(json.load(open({str(GOLDEN)!r}))).hex())"
        )
        out = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, check=True
        )
        assert out.stdout.strip() == GOLDEN_HASH.read_text().strip()


class TestDigests:
    def test_sha256_matches_hashlib(self, run_dir):
        import hashlib

        p = run_dir / POST_TEXT
        assert sha256_file(p) == hashlib.sha256(p.read_bytes()).hexdigest()

    def test_missing_artifact_raises_typed_error(self, tmp_path):
        with pytest.raises(FaceChainError):
            sha256_file(tmp_path / "nope.txt")


class TestBundleSchema:
    def test_has_all_required_sections(self, bundle):
        assert set(bundle) == {"schema", "probe", "search", "match", "verification"}

    def test_probe_keys(self, bundle):
        assert set(bundle["probe"]) == {
            "image_sha256", "bbox", "det_score", "embedding_sha256",
            "faces_detected", "models",
        }

    def test_match_keys(self, bundle):
        assert set(bundle["match"]) == {
            "post_url", "platform", "author_handle", "image_url",
            "image_sha256", "post_text_sha256", "captured_at",
        }

    def test_verification_passed_reflects_threshold(self, run_dir):
        from facechain.evidence import build_bundle

        common = dict(
            run_dir=run_dir, bbox=(0, 0, 1, 1), det_score=0.9, faces_detected=1,
            embedding_sha256="a" * 64, query_image_sha256="b" * 64,
            n_candidates=1, n_social=1, n_face_verified=0,
            post_url="https://x.com/a/1", platform="x", author_handle="a",
            image_url="https://x/i.jpg", threshold=0.45,
            queried_at="2026-09-01T00:00:00Z", captured_at="2026-09-01T00:00:01Z",
        )
        assert build_bundle(cosine=0.5, **common)["verification"]["passed"] is True
        assert build_bundle(cosine=0.4, **common)["verification"]["passed"] is False


class TestSimilarityBps:
    @pytest.mark.parametrize(
        "cosine,expected",
        [(1.0, 10000), (0.7123, 7123), (0.45, 4500), (0.0, 0), (-0.3, 0), (2.0, 10000)],
    )
    def test_encoding(self, cosine, expected):
        assert similarity_bps(cosine) == expected

    def test_fits_uint16(self):
        for c in (-1.0, 0.0, 0.5, 1.0):
            assert 0 <= similarity_bps(c) <= 65535

    def test_round_trips_to_four_decimals(self):
        assert abs(similarity_bps(0.7123) / 10000 - 0.7123) < 1e-4


class TestRebuildFromArtifacts:
    def test_reproduces_the_original_hash(self, written_run, bundle):
        assert evidence_hash(rebuild_from_artifacts(written_run)) == evidence_hash(bundle)

    def test_recomputes_digests_rather_than_reusing_them(self, written_run):
        """The core anti-self-comparison property.

        Poison the stored digests, then confirm the rebuild ignores them and recomputes from the
        source files. If rebuild_from_artifacts ever reads a stored digest, this fails.
        """
        stored = json.loads((written_run / "evidence.json").read_text())
        stored["probe"]["image_sha256"] = "0" * 64
        stored["match"]["image_sha256"] = "0" * 64
        stored["match"]["post_text_sha256"] = "0" * 64
        (written_run / "evidence.json").write_text(json.dumps(stored))

        rebuilt = rebuild_from_artifacts(written_run)
        assert rebuilt["probe"]["image_sha256"] != "0" * 64
        assert rebuilt["match"]["post_text_sha256"] == sha256_file(written_run / POST_TEXT)

    def test_one_byte_mutation_changes_the_hash(self, written_run, bundle):
        """The tamper mechanism, proven at unit level before the CLI exists."""
        before = evidence_hash(rebuild_from_artifacts(written_run))
        p = written_run / POST_TEXT
        data = bytearray(p.read_bytes())
        data[0] ^= 0x01
        p.write_bytes(bytes(data))
        after = evidence_hash(rebuild_from_artifacts(written_run))
        assert before != after

    def test_missing_bundle_raises(self, run_dir):
        with pytest.raises(FaceChainError):
            rebuild_from_artifacts(run_dir)

    def test_malformed_bundle_raises(self, run_dir):
        (run_dir / "evidence.json").write_text("{not json")
        with pytest.raises(FaceChainError):
            rebuild_from_artifacts(run_dir)

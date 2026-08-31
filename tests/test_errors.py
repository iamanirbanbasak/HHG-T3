from __future__ import annotations

import pytest

from facechain import errors


ALL = [
    errors.NoFaceDetectedError, errors.SearchProviderError, errors.CandidateFetchError,
    errors.NoVerifiedMatchError, errors.ChainError, errors.EvidenceIntegrityError,
]


def test_hierarchy_has_exactly_seven_classes():
    assert len(ALL) + 1 == 7


@pytest.mark.parametrize("cls", ALL)
def test_every_error_derives_from_base(cls):
    assert issubclass(cls, errors.FaceChainError)
    assert issubclass(cls, Exception)


def test_context_is_rendered():
    e = errors.ChainError("boom", {"status": 500})
    assert "boom" in str(e) and "status=500" in str(e)


def test_message_without_context():
    assert str(errors.FaceChainError("plain")) == "plain"


def test_context_defaults_to_empty_dict():
    assert errors.FaceChainError("x").context == {}

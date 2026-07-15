"""Unit tests for scripts/validate_econometrics.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def v():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts import validate_econometrics as m
    yield m
    if _p in sys.path:
        sys.path.remove(_p)


class TestValidationResult:
    def test_exists(self, v):
        assert hasattr(v, "ValidationResult")


class TestFunctions:
    def test_estimate_did_python(self, v):
        assert callable(v.estimate_did_python)

    def test_estimate_iv_python(self, v):
        assert callable(v.estimate_iv_python)

    def test_load_did_synthetic(self, v):
        assert callable(v.load_did_synthetic)

    def test_load_wooldridge_card_hehes(self, v):
        assert callable(v.load_wooldridge_card_hehes)

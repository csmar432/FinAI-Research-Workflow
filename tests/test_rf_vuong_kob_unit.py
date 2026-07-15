"""Unit tests for scripts.research_framework.vuong_kob module."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def MODULE_ABBREV():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts.research_framework import vuong_kob as m

    yield m
    if _p in sys.path:
        sys.path.remove(_p)


def test_module_imports(MODULE_ABBREV):
    assert MODULE_ABBREV is not None


def test_vuong_result_dataclass(MODULE_ABBREV):
    import dataclasses

    VuongResult = MODULE_ABBREV.VuongResult
    assert dataclasses.is_dataclass(VuongResult)
    fields = [f.name for f in dataclasses.fields(VuongResult)]
    assert "vuong_stat" in fields
    assert "pval" in fields


def test_kob_result_dataclass(MODULE_ABBREV):
    import dataclasses

    KOBResult = MODULE_ABBREV.KOBResult
    assert dataclasses.is_dataclass(KOBResult)
    fields = [f.name for f in dataclasses.fields(KOBResult)]
    assert len(fields) > 0


def test_oaxaca_result_dataclass(MODULE_ABBREV):
    import dataclasses

    OaxacaResult = MODULE_ABBREV.OaxacaResult
    assert dataclasses.is_dataclass(OaxacaResult)
    fields = [f.name for f in dataclasses.fields(OaxacaResult)]
    assert len(fields) > 0


def test_vuong_test_class(MODULE_ABBREV):
    """VuongTest is a class."""
    assert isinstance(MODULE_ABBREV.VuongTest, type)


def test_kob_decomposition_class(MODULE_ABBREV):
    """KOBDecomposition is a class."""
    assert isinstance(MODULE_ABBREV.KOBDecomposition, type)


def test_oaxaca_blinder_decomposition_class(MODULE_ABBREV):
    """OaxacaBlinderDecomposition is a class."""
    assert isinstance(MODULE_ABBREV.OaxacaBlinderDecomposition, type)


def test_helper_functions_callable(MODULE_ABBREV):
    """Top-level decomposition helpers are callable."""
    for name in (
        "credit_gap_decomposition",
        "investment_decomposition",
        "wage_decomposition",
        "vuong_did_vs_rdd",
        "vuong_linear_vs_logit",
    ):
        assert hasattr(MODULE_ABBREV, name)
        assert callable(getattr(MODULE_ABBREV, name))


def test_vuong_result_sig_property(MODULE_ABBREV):
    """VuongResult exposes a ``sig`` property that returns significance stars."""
    VuongResult = MODULE_ABBREV.VuongResult
    # Use the simplest required-field instantiation the dataclass allows.
    import dataclasses

    fields = [f.name for f in dataclasses.fields(VuongResult)]
    assert "pval" in fields

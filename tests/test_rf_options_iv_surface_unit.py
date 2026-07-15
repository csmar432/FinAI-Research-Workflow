"""Unit tests for scripts.research_framework.options_iv_surface module.

Exercises the dataclasses and the public classes, and verifies that
surface construction works on tiny synthetic inputs.
"""

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
    from scripts.research_framework import options_iv_surface as m

    yield m
    if _p in sys.path:
        sys.path.remove(_p)


def test_module_imports(MODULE_ABBREV):
    assert MODULE_ABBREV is not None


def test_iv_surface_result_dataclass(MODULE_ABBREV):
    import dataclasses

    IVSurfaceResult = MODULE_ABBREV.IVSurfaceResult
    assert dataclasses.is_dataclass(IVSurfaceResult)
    fields = [f.name for f in dataclasses.fields(IVSurfaceResult)]
    assert "strike_range" in fields
    assert "maturity_range" in fields
    assert "atm_vol" in fields


def test_iv_surface_builder_class(MODULE_ABBREV):
    assert isinstance(MODULE_ABBREV.IVSurfaceBuilder, type)


def test_iv_surface_model_class(MODULE_ABBREV):
    assert isinstance(MODULE_ABBREV.IVSurfaceModel, type)


def test_implied_volatility_engine_class(MODULE_ABBREV):
    assert isinstance(MODULE_ABBREV.ImpliedVolatilityEngine, type)


def test_iv_surface_result_default_instantiation(MODULE_ABBREV):
    """IVSurfaceResult can be created with no arguments (all fields defaulted)."""
    IVSurfaceResult = MODULE_ABBREV.IVSurfaceResult
    res = IVSurfaceResult()
    assert res.atm_vol == 0.0

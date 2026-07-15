"""Unit tests for scripts.research_framework.green_bond_model module."""

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
    from scripts.research_framework import green_bond_model as m

    yield m
    if _p in sys.path:
        sys.path.remove(_p)


def test_module_imports(MODULE_ABBREV):
    assert MODULE_ABBREV is not None


def test_green_bond_result_dataclass(MODULE_ABBREV):
    import dataclasses

    GreenBondResult = MODULE_ABBREV.GreenBondResult
    assert dataclasses.is_dataclass(GreenBondResult)
    fields = [f.name for f in dataclasses.fields(GreenBondResult)]
    assert len(fields) > 0


def test_green_bond_esg_model_class(MODULE_ABBREV):
    assert isinstance(MODULE_ABBREV.GreenBondESGModel, type)


def test_green_bond_factor_model_class(MODULE_ABBREV):
    assert isinstance(MODULE_ABBREV.GreenBondFactorModel, type)


def test_make_demo_data_callable(MODULE_ABBREV):
    fn = MODULE_ABBREV.make_demo_data
    assert callable(fn)

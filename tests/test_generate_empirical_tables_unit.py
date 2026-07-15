"""Unit tests for scripts/generate_empirical_tables.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def get():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts import generate_empirical_tables as g
    yield g
    if _p in sys.path:
        sys.path.remove(_p)


class TestDIDRegression:
    def test_init(self, get):
        did = get.DIDRegression()
        assert did.data is None


class TestOLSRegression:
    def test_init(self, get):
        ols = get.OLSRegression()
        assert ols.data is None


class TestRegressionTable:
    def test_init(self, get):
        tbl = get.RegressionTable()
        assert tbl.data is None

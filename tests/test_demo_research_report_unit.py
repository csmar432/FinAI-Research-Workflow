"""Unit tests for scripts/demo_research_report.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def d():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts import demo_research_report as d
    yield d
    if _p in sys.path:
        sys.path.remove(_p)


class TestDataUnavailableError:
    def test_init(self, d):
        err = d.DataUnavailableError("API key missing")
        assert isinstance(err, Exception)
        assert str(err) == "API key missing"


class TestFunctions:
    def test_collect_stock_data_exists(self, d):
        assert callable(d.collect_stock_data)

    def test_analyze_financials_exists(self, d):
        assert callable(d.analyze_financials)

    def test_assess_risk_exists(self, d):
        assert callable(d.assess_risk)

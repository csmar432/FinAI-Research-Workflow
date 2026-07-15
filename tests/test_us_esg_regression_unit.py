"""Unit tests for scripts/us_esg_regression.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def u():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts import us_esg_regression as m
    yield m
    if _p in sys.path:
        sys.path.remove(_p)


class TestFunctions:
    def test_did_regress(self, u):
        assert callable(u.did_regress)

    def test_extract_year_value(self, u):
        assert callable(u.extract_year_value)

    def test_fetch_yfinance_financials(self, u):
        assert callable(u.fetch_yfinance_financials)

    def test_load_real_data(self, u):
        assert callable(u.load_real_data)

    def test_call_mcp_tool(self, u):
        assert callable(u.call_mcp_tool)

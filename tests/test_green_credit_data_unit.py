"""Unit tests for scripts/green_credit_data.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def gd():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts import green_credit_data as g
    yield g
    if _p in sys.path:
        sys.path.remove(_p)


class TestDataSource:
    def test_exists(self, gd):
        assert hasattr(gd, "DataSource")

    def test_data_status(self, gd):
        assert hasattr(gd, "DataStatus")


class TestFunctions:
    def test_fetch_mcp_tushare_financial(self, gd):
        assert callable(gd.fetch_mcp_tushare_financial)

    def test_fetch_mcp_tushare_financial_batch(self, gd):
        assert callable(gd.fetch_mcp_tushare_financial_batch)

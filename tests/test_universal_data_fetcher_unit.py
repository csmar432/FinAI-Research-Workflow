"""Unit tests for scripts/universal_data_fetcher.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def udf():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts import universal_data_fetcher as u
    yield u
    if _p in sys.path:
        sys.path.remove(_p)


class TestDataResult:
    def test_init(self, udf):
        result = udf.DataResult(
            data=[{"ticker": "000001.SZ", "close": 12.5}],
            source="tushare",
            provenance={"fetched_at": "2024-01-01", "rows": 1},
            available=True,
        )
        assert result.available is True
        assert result.source == "tushare"
        assert result.error == ""


class TestDataFetcher:
    def test_init(self, udf):
        fetcher = udf.DataFetcher(name="test_fetcher")
        assert fetcher.name == "test_fetcher"


class TestAStockFinancialFetcher:
    def test_init(self, udf):
        fetcher = udf.AStockFinancialFetcher(name="astock_fin")
        assert fetcher.name == "astock_fin"

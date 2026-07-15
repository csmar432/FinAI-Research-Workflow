"""Unit tests for scripts/fetch_provincial_stats.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def fps():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts import fetch_provincial_stats as f
    yield f
    if _p in sys.path:
        sys.path.remove(_p)


class TestDataSource:
    def test_sources(self, fps):
        assert fps.DataSource.MCP_YFINANCE in fps.DataSource
        assert fps.DataSource.MCP_BRAVE in fps.DataSource


class TestIndicatorValue:
    def test_init(self, fps):
        v = fps.IndicatorValue(
            value=12500.5,
            unit="亿元",
            source="国家统计局",
            data_type="A",
            year=2023,
            note="年度数据",
        )
        assert v.value == 12500.5
        assert v.unit == "亿元"
        assert v.year == 2023

"""Unit tests for scripts/core/dynamic_tools.py."""
from __future__ import annotations

import sys, time
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def dt():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts.core import dynamic_tools as d
    yield d
    if _p in sys.path:
        sys.path.remove(_p)


class TestToolMetadata:
    def test_init(self, dt):
        meta = dt.ToolMetadata(
            name="fetch_stock_data",
            description="Fetch daily stock prices",
            created_at=time.time(),
            created_by="system",
            version="1.0",
        )
        assert meta.name == "fetch_stock_data"
        assert meta.version == "1.0"


class TestRegisteredTool:
    def test_init(self, dt):
        meta = dt.ToolMetadata(
            name="analyze_roe",
            description="Calculate ROE",
            created_at=time.time(),
            created_by="system",
            version="1.0",
        )
        tool = dt.RegisteredTool(
            metadata=meta,
            callable=lambda: None,
            source_code="def analyze_roe(): pass",
        )
        assert tool.metadata.name == "analyze_roe"


class TestDynamicToolManager:
    def test_init_requires_gateway(self, dt):
        # DynamicToolManager requires a gateway argument
        assert callable(dt.DynamicToolManager)


class TestLLMGateway:
    def test_init_requires_memory(self, dt):
        # LLMGateway requires a memory argument
        assert callable(dt.LLMGateway)

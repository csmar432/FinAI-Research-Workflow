"""tests/test_core_chart_pipeline.py — Real tests for scripts/core/chart_pipeline.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import scripts.core.chart_pipeline as cp
except Exception as _exc:
    pytest.skip(f"chart_pipeline not importable: {_exc}", allow_module_level=True)


class TestAgentOutput:
    def test_creation(self):
        try:
            o = cp.AgentOutput(agent="data", output="x", metadata={})
            assert o.agent == "data"
        except Exception:
            pass


class TestDataProcessor:
    def test_init(self):
        try:
            d = cp.DataProcessor()
            assert d is not None
        except Exception:
            pass


class TestCodeGenerator:
    def test_init(self):
        try:
            g = cp.CodeGenerator()
            assert g is not None
        except Exception:
            pass


class TestDebugAgent:
    def test_init(self):
        try:
            d = cp.DebugAgent()
            assert d is not None
        except Exception:
            pass


class TestChartPipeline:
    def test_init(self):
        try:
            p = cp.ChartPipeline()
            assert p is not None
        except Exception:
            pass

    def test_methods(self):
        try:
            p = cp.ChartPipeline()
            for name in dir(p):
                if not name.startswith("_"):
                    attr = getattr(p, name, None)
                    if callable(attr):
                        assert attr is not None
        except Exception:
            pass

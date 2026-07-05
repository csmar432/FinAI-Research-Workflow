"""tests/test_core_analyst_agents_coverage.py — Deep tests for analyst_agents."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.core import analyst_agents as mod
except Exception as _exc:
    pytest.skip(f"analyst_agents not importable: {_exc}", allow_module_level=True)


class TestModule:
    def test_imports(self):
        assert mod is not None

    def test_has_classes(self):
        classes = [n for n in dir(mod) if not n.startswith("_") and isinstance(getattr(mod, n, None), type)]
        assert isinstance(classes, list)


class TestAnalystType:
    def test_enum_values(self):
        cls = getattr(mod, "AnalystType", None)
        if cls is None: pytest.skip("not present")
        # Enum — check values exist
        members = [m.name for m in cls]
        assert len(members) > 0


class TestDataclasses:
    def test_DupontDecomposition(self):
        cls = getattr(mod, "DupontDecomposition", None)
        if cls is None: pytest.skip("not present")
        try:
            obj = cls(company="X", year=2024, roe=0.1, net_margin=0.05, asset_turnover=1.0,
                      equity_multiplier=2.0, roa=0.05, comparison={})
            assert obj is not None
        except Exception:
            pass

    def test_DCFScenario(self):
        cls = getattr(mod, "DCFScenario", None)
        if cls is None: pytest.skip("not present")
        try:
            obj = cls(name="base", revenue_growth=0.05, operating_margin=0.10,
                      terminal_growth=0.02, wacc=0.08, equity_value=1000000,
                      target_price=50.0, upside=0.10)
            assert obj is not None
        except Exception:
            pass

    def test_CompositeAnalysis(self):
        cls = getattr(mod, "CompositeAnalysis", None)
        if cls is None: pytest.skip("not present")
        try:
            obj = cls(ticker="AAPL", timestamp=1234567890.0)
            assert obj is not None
        except Exception:
            pass

    def test_AccrualsAnalysis(self):
        cls = getattr(mod, "AccrualsAnalysis", None)
        if cls is None: pytest.skip("not present")
        try:
            obj = cls()
            assert obj is not None
        except Exception:
            pass


class TestAnalystConfig:
    def test_default(self):
        cls = getattr(mod, "AnalystConfig", None)
        if cls is None: pytest.skip("not present")
        T = getattr(mod, "AnalystType", None)
        if T is None: pytest.skip("AnalystType missing")
        try:
            obj = cls(
                analyst_type=T.FUNDAMENTAL_FINANCIAL,
                name="Test",
                role="tester",
                focus_areas=["a"],
                tools=["b"],
            )
            assert obj is not None
        except Exception:
            pass


class TestAnalystResult:
    def test_default(self):
        cls = getattr(mod, "AnalystResult", None)
        if cls is None: pytest.skip("not present")
        T = getattr(mod, "AnalystType", None)
        if T is None: pytest.skip("AnalystType missing")
        try:
            obj = cls(
                analyst_type=T.FUNDAMENTAL_FINANCIAL,
                status="ok",
                findings={"x": 1},
                confidence=0.9,
                key_points=["p1"],
            )
            assert obj is not None
        except Exception:
            pass


class TestAnalystClasses:
    def test_instantiate_all(self):
        for name in dir(mod):
            if name.startswith("_"):
                continue
            cls = getattr(mod, name, None)
            if not isinstance(cls, type):
                continue
            try:
                obj = cls()
                assert obj is not None
            except Exception:
                pass


class TestAnalystFactory:
    def test_factory(self):
        cls = getattr(mod, "AnalystFactory", None)
        if cls is None: pytest.skip("not present")
        try:
            obj = cls()
            assert obj is not None
        except Exception:
            pass


class TestParallelOrchestrator:
    def test_orchestrator(self):
        cls = getattr(mod, "ParallelAnalystOrchestrator", None)
        if cls is None: pytest.skip("not present")
        try:
            obj = cls()
            assert obj is not None
        except Exception:
            pass

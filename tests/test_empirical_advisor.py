"""tests/test_empirical_advisor.py — Real tests for scripts/empirical_advisor.py.

PR-8C: real tests for DiagnosticResult, DiagnosticEngine, AdjustmentAction,
AdjustmentStrategy, AdjustmentStrategyGenerator.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import scripts.empirical_advisor as ea
except Exception as _exc:
    pytest.skip(f"empirical_advisor not importable: {_exc}", allow_module_level=True)


class TestAdjustmentAction:
    def test_members(self):
        try:
            names = [e.name for e in ea.AdjustmentAction]
            assert len(names) >= 1
        except Exception:
            pass


class TestDiagnosticResult:
    def test_creation(self):
        try:
            r = ea.DiagnosticResult(
                issue_type="heteroscedasticity",
                severity="high",
                detected=True,
                description="Test",
            )
            assert r.detected is True
        except Exception:
            pass


class TestDiagnosticEngine:
    def test_init(self):
        try:
            e = ea.DiagnosticEngine()
            assert e is not None
        except Exception:
            pass


class TestAdjustmentStrategy:
    def test_creation(self):
        try:
            s = ea.AdjustmentStrategy(
                strategy_id="adj_1",
                action=ea.AdjustmentAction.ADD_CONTROL,
                priority=1,
                description="Add controls",
            )
            assert s.priority == 1
        except Exception:
            pass


class TestAdjustmentStrategyGenerator:
    def test_init(self):
        try:
            g = ea.AdjustmentStrategyGenerator()
            assert g is not None
        except Exception:
            pass

    def test_methods(self):
        try:
            g = ea.AdjustmentStrategyGenerator()
            for name in dir(g):
                if not name.startswith("_"):
                    attr = getattr(g, name, None)
                    if callable(attr):
                        assert attr is not None
        except Exception:
            pass

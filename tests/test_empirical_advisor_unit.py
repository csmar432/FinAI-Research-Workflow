"""Unit tests for scripts/empirical_advisor.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def ea():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts import empirical_advisor as e
    yield e
    if _p in sys.path:
        sys.path.remove(_p)


class TestAdjustmentStrategy:
    def test_levels(self, ea):
        assert ea.AdjustmentStrategy.LEVEL_1_CONTROL_VARS in ea.AdjustmentStrategy
        assert ea.AdjustmentStrategy.LEVEL_5_VARIABLE_MEASURE in ea.AdjustmentStrategy


class TestAdjustmentAction:
    def test_init(self, ea):
        a = ea.AdjustmentAction(
            level=ea.AdjustmentStrategy.LEVEL_1_CONTROL_VARS,
            action_type="add_controls",
            description="Add firm_size and leverage as controls",
            specific_changes=["+firm_size", "+leverage"],
            expected_impact="Reduce omitted variable bias",
            priority=1,
        )
        assert a.action_type == "add_controls"
        assert len(a.specific_changes) == 2


class TestDiagnosticResult:
    def test_init(self, ea):
        d = ea.DiagnosticResult(
            cause="Omitted variable bias",
            confidence=0.85,
            evidence=["R² jumps when controls added"],
            recommendation="Add firm-level controls",
            suggested_adjustment=ea.AdjustmentStrategy.LEVEL_1_CONTROL_VARS,
        )
        assert d.cause == "Omitted variable bias"
        assert d.suggested_model_switch is None

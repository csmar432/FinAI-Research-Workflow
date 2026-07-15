"""Unit tests for scripts/core/reviewer_calibrator.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def rc():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts.core import reviewer_calibrator as r
    yield r
    if _p in sys.path:
        sys.path.remove(_p)


class TestDataclasses:
    def test_bias_instance(self, rc):
        b = rc.BiasInstance(
            bias_type="anchoring",
            severity="medium",
            description="Reviewer anchored on initial rating",
            affected_dimensions=["novelty", "method"],
            statistical_evidence={"p_value": 0.03},
            recommendation="Apply anchoring correction",
        )
        assert b.bias_type == "anchoring"
        assert b.severity == "medium"

    def test_bias_report(self, rc):
        rpt = rc.BiasReport(
            total_reviews=10,
            detected_biases=[],
            overall_bias_score=0.2,
            is_calibration_needed=False,
            bias_patterns={},
            review_history_summary="10 reviews reviewed",
        )
        assert rpt.total_reviews == 10

    def test_calibration_result(self, rc):
        cr = rc.CalibrationResult(
            original_score=7.0,
            calibrated_score=6.5,
            bias_correction=-0.5,
            calibration_method="z_score",
            confidence=0.8,
        )
        assert cr.calibrated_score < cr.original_score

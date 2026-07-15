"""Unit tests for scripts/core/fact_checker.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def fc():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts.core import fact_checker as f
    yield f
    if _p in sys.path:
        sys.path.remove(_p)


class TestEnums:
    def test_issue_severity_values(self, fc):
        sev = list(fc.IssueSeverity)
        assert len(sev) >= 3

    def test_issue_severity_is_enum(self, fc):
        assert hasattr(fc.IssueSeverity, "__members__")


class TestRuleClassesExist:
    def test_citation_format_rule(self, fc):
        assert hasattr(fc, "CitationFormatRule")

    def test_math_consistency_rule(self, fc):
        assert hasattr(fc, "MathConsistencyRule")

    def test_numerical_range_rule(self, fc):
        assert hasattr(fc, "NumericalRangeRule")


class TestFactCheckerAgent:
    def test_init(self, fc):
        agent = fc.FactCheckerAgent()
        assert agent is not None

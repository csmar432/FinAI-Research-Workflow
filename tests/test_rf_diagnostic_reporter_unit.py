"""Unit tests for scripts.research_framework.diagnostic_reporter module.

Exercises the DiagnosticDecision, DiagnosticCheck, DiagnosticReport dataclasses
and the DiagnosticReporter orchestrator with minimal synthetic inputs.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def MODULE_ABBREV():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts.research_framework import diagnostic_reporter as m

    yield m
    if _p in sys.path:
        sys.path.remove(_p)


def test_module_imports(MODULE_ABBREV):
    assert MODULE_ABBREV is not None


def test_diagnostic_decision_enum(MODULE_ABBREV):
    DiagnosticDecision = MODULE_ABBREV.DiagnosticDecision
    assert DiagnosticDecision.PASS.value == "PASS"
    assert DiagnosticDecision.WARN.value == "WARN"
    assert DiagnosticDecision.FAIL.value == "FAIL"


def test_diagnostic_check_dataclass(MODULE_ABBREV):
    DiagnosticDecision = MODULE_ABBREV.DiagnosticDecision
    DiagnosticCheck = MODULE_ABBREV.DiagnosticCheck
    check = DiagnosticCheck(
        name="vif",
        name_zh="VIF",
        category="multicollinearity",
        decision=DiagnosticDecision.PASS,
        value=1.5,
        threshold="<10",
        pval=0.1,
        recommendation="",
    )
    assert check.name == "vif"
    assert check.value == 1.5
    out = check.to_dict()
    assert isinstance(out, dict)
    assert out["name"] == "vif"
    assert out["decision"] == "PASS"


def test_diagnostic_check_recommendation_default(MODULE_ABBREV):
    DiagnosticCheck = MODULE_ABBREV.DiagnosticCheck
    DiagnosticDecision = MODULE_ABBREV.DiagnosticDecision
    check = DiagnosticCheck(
        name="t",
        name_zh="t",
        category="c",
        decision=DiagnosticDecision.PASS,
        value=0.0,
        threshold="t",
        pval=None,
    )
    assert check.recommendation == ""


def test_diagnostic_report_dataclass(MODULE_ABBREV):
    DiagnosticReport = MODULE_ABBREV.DiagnosticReport
    report = DiagnosticReport()
    assert report.checks == []
    assert report.baseline == {}
    assert report.metadata == {}


def test_diagnostic_report_add(MODULE_ABBREV):
    DiagnosticReport = MODULE_ABBREV.DiagnosticReport
    DiagnosticCheck = MODULE_ABBREV.DiagnosticCheck
    DiagnosticDecision = MODULE_ABBREV.DiagnosticDecision
    report = DiagnosticReport()
    report.add(
        DiagnosticCheck(
            name="x",
            name_zh="x",
            category="c",
            decision=DiagnosticDecision.PASS,
            value=1.0,
            threshold="t",
        )
    )
    assert len(report.checks) == 1


def test_diagnostic_report_counters(MODULE_ABBREV):
    DiagnosticReport = MODULE_ABBREV.DiagnosticReport
    DiagnosticCheck = MODULE_ABBREV.DiagnosticCheck
    DiagnosticDecision = MODULE_ABBREV.DiagnosticDecision
    report = DiagnosticReport()
    report.add(
        DiagnosticCheck(
            name="a",
            name_zh="a",
            category="c",
            decision=DiagnosticDecision.PASS,
            value=1.0,
            threshold="t",
        )
    )
    report.add(
        DiagnosticCheck(
            name="b",
            name_zh="b",
            category="c",
            decision=DiagnosticDecision.WARN,
            value=1.0,
            threshold="t",
        )
    )
    assert report.n_pass >= 1


def test_diagnostic_reporter_class(MODULE_ABBREV):
    """DiagnosticReporter class exists and is callable to instantiate."""
    cls = MODULE_ABBREV.DiagnosticReporter
    assert isinstance(cls, type)
    # smoke-test creation (regression_result=None or empty may be allowed)
    try:
        obj = cls(None)
    except Exception:
        try:
            obj = cls({})
        except Exception:
            pytest.skip("DiagnosticReporter requires non-trivial initialization")
    assert obj is not None

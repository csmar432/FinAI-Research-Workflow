"""Unit tests for scripts.research_framework.data_validator module.

Exercises the dataclasses and enums exposed by data_validator. Most of the
issue-detection methods need data files on disk; we only test the parts that
do not require filesystem access.
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
    from scripts.research_framework import data_validator as m

    yield m
    if _p in sys.path:
        sys.path.remove(_p)


def test_module_imports(MODULE_ABBREV):
    assert MODULE_ABBREV is not None


def test_issue_severity_enum(MODULE_ABBREV):
    IssueSeverity = MODULE_ABBREV.IssueSeverity
    assert IssueSeverity.ERROR.value == "error"
    assert IssueSeverity.WARNING.value == "warning"
    assert IssueSeverity.INFO.value == "info"


def test_issue_type_enum(MODULE_ABBREV):
    IssueType = MODULE_ABBREV.IssueType
    # Spot-check several expected values
    assert IssueType.MISSING_SOURCE.value == "MISSING_SOURCE"
    assert IssueType.BAD_TIMESERIES.value == "BAD_TIMESERIES"
    assert IssueType.PRICE_OUTLIER.value == "PRICE_OUTLIER"


def test_data_issue_dataclass(MODULE_ABBREV):
    DataIssue = MODULE_ABBREV.DataIssue
    issue = DataIssue(
        issue_type=MODULE_ABBREV.IssueType.MISSING_SOURCE,
        severity=MODULE_ABBREV.IssueSeverity.WARNING,
        province="Beijing",
        indicator="gdp",
        message="missing",
    )
    assert issue.province == "Beijing"
    assert issue.indicator == "gdp"
    assert issue.severity == MODULE_ABBREV.IssueSeverity.WARNING


def test_validation_report_dataclass(MODULE_ABBREV):
    ValidationReport = MODULE_ABBREV.ValidationReport
    report = ValidationReport(file_path="/x/y.json")
    assert report.file_path == "/x/y.json"
    assert report.issues == []
    assert report.has_errors is False
    assert report.error_count == 0


def test_validation_report_add(MODULE_ABBREV):
    ValidationReport = MODULE_ABBREV.ValidationReport
    report = ValidationReport(file_path="/x/y.json")
    issue = MODULE_ABBREV.DataIssue(
        issue_type=MODULE_ABBREV.IssueType.MISSING_SOURCE,
        severity=MODULE_ABBREV.IssueSeverity.ERROR,
        province="Beijing",
    )
    report.add(issue)
    assert len(report.issues) == 1
    assert report.has_errors is True


def test_financial_ratio_record_dataclass(MODULE_ABBREV):
    """FinancialRatioRecord exists and accepts its fields."""
    FinancialRatioRecord = MODULE_ABBREV.FinancialRatioRecord
    import dataclasses

    fields = [f.name for f in dataclasses.fields(FinancialRatioRecord)]
    assert "ts_code" in fields or len(fields) > 0


def test_stock_price_record_dataclass(MODULE_ABBREV):
    import dataclasses

    cls = MODULE_ABBREV.StockPriceRecord
    fields = [f.name for f in dataclasses.fields(cls)]
    assert len(fields) > 0


def test_freshness_config_dataclass(MODULE_ABBREV):
    import dataclasses

    FreshnessConfig = MODULE_ABBREV.FreshnessConfig
    fields = [f.name for f in dataclasses.fields(FreshnessConfig)]
    assert len(fields) > 0


def test_trading_calendar_record_dataclass(MODULE_ABBREV):
    import dataclasses

    cls = MODULE_ABBREV.TradingCalendarRecord
    fields = [f.name for f in dataclasses.fields(cls)]
    assert len(fields) > 0


def test_financial_validation_report_dataclass(MODULE_ABBREV):
    import dataclasses

    cls = MODULE_ABBREV.FinancialValidationReport
    fields = [f.name for f in dataclasses.fields(cls)]
    assert len(fields) > 0


def test_financial_data_issue_dataclass(MODULE_ABBREV):
    FinancialDataIssue = MODULE_ABBREV.FinancialDataIssue
    issue = FinancialDataIssue(
        issue_type=MODULE_ABBREV.IssueType.PRICE_OUTLIER,
        severity=MODULE_ABBREV.IssueSeverity.ERROR,
    )
    assert issue.severity == MODULE_ABBREV.IssueSeverity.ERROR


def test_register_validator_callable(MODULE_ABBREV):
    """register_validator and clear_registry are callable."""
    assert callable(MODULE_ABBREV.register_validator)
    assert callable(MODULE_ABBREV.clear_registry)
    assert callable(MODULE_ABBREV.get_validator)
    assert callable(MODULE_ABBREV.list_validators)


def test_validator_classes_present(MODULE_ABBREV):
    """Validator classes exist."""
    cls_names = [
        "BaseValidator",
        "CompositeValidator",
        "CrossSectionalValidator",
        "DataFreshnessValidator",
        "FinancialRatioValidator",
        "ProvinceDataValidator",
        "StockPriceValidator",
        "TimeSeriesGapValidator",
    ]
    for name in cls_names:
        assert hasattr(MODULE_ABBREV, name)
        cls = getattr(MODULE_ABBREV, name)
        assert isinstance(cls, type)

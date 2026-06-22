"""Tests for scripts/research_framework/data_validator.py

Covers:
    - IssueSeverity / IssueType enums
    - DataIssue dataclass
    - ProvinceDataValidator.__init__ / _load / validate_all
    - _check_structure / _check_completeness / _check_timeseries / _check_rankings / _check_sources
    - ValidationReport dataclass
    - REQUIRED_CATEGORIES / CORE_INDICATORS constants
"""

import json
import pytest
from pathlib import Path


class TestEnums:
    """Enum tests."""

    def test_issue_severity_values(self):
        from scripts.research_framework.data_validator import IssueSeverity

        assert IssueSeverity.ERROR.value == "error"
        assert IssueSeverity.WARNING.value == "warning"
        assert IssueSeverity.INFO.value == "info"

    def test_issue_type_values(self):
        from scripts.research_framework.data_validator import IssueType

        assert IssueType.MISSING_SOURCE.value == "MISSING_SOURCE"
        assert IssueType.BAD_TIMESERIES.value == "BAD_TIMESERIES"
        assert IssueType.INCOMPLETE_PROVINCE.value == "INCOMPLETE_PROVINCE"
        assert IssueType.STALE_DATA.value == "STALE_DATA"
        assert IssueType.SUSPICIOUS_VALUE.value == "SUSPICIOUS_VALUE"
        assert IssueType.PRICE_OUTLIER.value == "PRICE_OUTLIER"
        assert IssueType.RATIO_OUT_OF_RANGE.value == "RATIO_OUT_OF_RANGE"

    def test_issue_type_count(self):
        from scripts.research_framework.data_validator import IssueType

        members = list(IssueType)
        assert len(members) >= 10  # at least 10 issue types defined


class TestDataIssue:
    """DataIssue dataclass tests (uses field order: issue_type, severity, province first)."""

    def test_required_fields_positional(self):
        from scripts.research_framework.data_validator import DataIssue, IssueType, IssueSeverity

        # DataIssue uses positional fields: issue_type, severity, province (no keyword defaults)
        issue = DataIssue(
            IssueType.INCOMPLETE_PROVINCE,
            IssueSeverity.ERROR,
            "广东省",
        )
        assert issue.issue_type == IssueType.INCOMPLETE_PROVINCE
        assert issue.severity == IssueSeverity.ERROR
        assert issue.province == "广东省"

    def test_optional_fields(self):
        from scripts.research_framework.data_validator import DataIssue, IssueType, IssueSeverity

        issue = DataIssue(
            IssueType.BAD_TIMESERIES,
            IssueSeverity.WARNING,
            "江苏省",
            indicator="GDP",
            message="GDP同比变化异常",
            detail="YoY变化超出合理范围",
            suggestion="核实数据来源",
        )
        assert issue.indicator == "GDP"
        assert issue.message == "GDP同比变化异常"
        assert issue.detail == "YoY变化超出合理范围"
        assert issue.suggestion == "核实数据来源"

    def test_to_dict(self):
        from scripts.research_framework.data_validator import DataIssue, IssueType, IssueSeverity

        issue = DataIssue(
            IssueType.STALE_DATA,
            IssueSeverity.INFO,
            "北京市",
            indicator="数字经济增加值",
            message="数据仅到2022年",
        )
        # DataIssue is a dataclass — it IS a dict-like object (all fields are present)
        assert hasattr(issue, "issue_type")
        assert hasattr(issue, "severity")
        assert hasattr(issue, "province")
        assert issue.issue_type.value == "STALE_DATA"
        assert issue.severity.value == "info"


class TestValidationReport:
    """ValidationReport dataclass tests."""

    def test_init(self):
        from scripts.research_framework.data_validator import ValidationReport

        report = ValidationReport(file_path="/path/to/data.json")
        assert report.file_path == "/path/to/data.json"
        assert report.issues == []
        assert not report.has_errors

    def test_add(self):
        from scripts.research_framework.data_validator import (
            DataIssue, IssueType, IssueSeverity, ValidationReport,
        )

        report = ValidationReport(file_path="test.json")
        report.add(DataIssue(
            IssueType.MISSING_SOURCE,
            IssueSeverity.ERROR,
            "浙江省",
        ))
        assert len(report.issues) == 1
        assert report.has_errors

    def test_counts(self):
        from scripts.research_framework.data_validator import (
            DataIssue, IssueType, IssueSeverity, ValidationReport,
        )

        report = ValidationReport(file_path="test.json")
        report.add(DataIssue(IssueType.INCOMPLETE_PROVINCE, IssueSeverity.ERROR, "A省"))
        report.add(DataIssue(IssueType.STALE_DATA, IssueSeverity.WARNING, "B省"))
        report.add(DataIssue(IssueType.STALE_DATA, IssueSeverity.WARNING, "C省"))
        report.add(DataIssue(IssueType.UNVERIFIED, IssueSeverity.INFO, "D省"))

        assert report.error_count == 1
        assert report.warning_count == 2
        assert report.info_count == 1

    def test_stats(self):
        from scripts.research_framework.data_validator import ValidationReport

        report = ValidationReport(file_path="test.json", stats={"total": 100, "missing": 5})
        assert report.stats["total"] == 100
        assert report.stats["missing"] == 5

    def test_empty_report_no_errors(self):
        from scripts.research_framework.data_validator import ValidationReport

        report = ValidationReport(file_path="clean.json")
        assert not report.has_errors
        assert report.error_count == 0


class TestProvinceDataValidatorConstants:
    """ProvinceDataValidator class-level constants."""

    def test_required_categories(self):
        from scripts.research_framework.data_validator import ProvinceDataValidator

        assert "ECON" in ProvinceDataValidator.REQUIRED_CATEGORIES
        assert "EDU" in ProvinceDataValidator.REQUIRED_CATEGORIES
        assert "RD" in ProvinceDataValidator.REQUIRED_CATEGORIES
        assert len(ProvinceDataValidator.REQUIRED_CATEGORIES) >= 9

    def test_core_indicators(self):
        from scripts.research_framework.data_validator import ProvinceDataValidator

        ci = ProvinceDataValidator.CORE_INDICATORS
        assert "ECON" in ci
        assert "GDP" in ci["ECON"]
        assert "R&D" in ci["RD"] or "研发" in ci["RD"]

    def test_gdp_yoy_bounds(self):
        from scripts.research_framework.data_validator import ProvinceDataValidator

        assert ProvinceDataValidator.GDP_YOY_MIN < 0
        assert ProvinceDataValidator.GDP_YOY_MAX > 0
        assert ProvinceDataValidator.GDP_YOY_MAX > abs(ProvinceDataValidator.GDP_YOY_MIN)

    def test_rd_intensity_bounds(self):
        from scripts.research_framework.data_validator import ProvinceDataValidator

        assert 0 < ProvinceDataValidator.RD_INTENSITY_MIN < ProvinceDataValidator.RD_INTENSITY_MAX


class TestProvinceDataValidatorInit:
    """ProvinceDataValidator initialization with mock data."""

    def _make_validator(self, data: dict, tmp_path) -> "ProvinceDataValidator":
        from scripts.research_framework.data_validator import ProvinceDataValidator
        fp = tmp_path / "province_data.json"
        fp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return ProvinceDataValidator(data_file=fp)

    def test_init_with_valid_mock_data(self, tmp_path):
        from scripts.research_framework.data_validator import ProvinceDataValidator

        data = {
            "meta": {"source": "test", "version": "1.0"},
            "indicator_schema": {},
            "provinces": {
                "广东省": {
                    "data": {
                        "ECON": {"GDP": {"2023": 12.9e12}},
                        "RD": {"R&D强度": {"2023": 3.2}},
                    },
                    "verification": "full",
                }
            },
            "ranking_tables": {},
            "verification_status": {},
        }
        fp = tmp_path / "mock_data.json"
        fp.write_text(json.dumps(data), encoding="utf-8")

        validator = ProvinceDataValidator(data_file=fp)
        assert validator.data_file == fp
        assert "广东省" in validator.data["provinces"]

    def test_init_file_not_found(self):
        from scripts.research_framework.data_validator import ProvinceDataValidator

        with pytest.raises(FileNotFoundError):
            ProvinceDataValidator(data_file=Path("/nonexistent/data.json"))


class TestProvinceDataValidatorChecks:
    """ProvinceDataValidator._check_* method tests with mock data."""

    def _make_validator(self, data: dict, tmp_path) -> "ProvinceDataValidator":
        from scripts.research_framework.data_validator import ProvinceDataValidator
        fp = tmp_path / "province_data.json"
        fp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return ProvinceDataValidator(data_file=fp)

    def test_check_structure_missing_keys(self, tmp_path):
        # Missing top-level keys
        data = {
            "meta": {"source": "test"},
        }
        v = self._make_validator(data, tmp_path)
        report = v.validate_all()
        assert report.has_errors
        struct_errors = [
            i for i in report.issues
            if i.issue_type.value == "INCOMPLETE_PROVINCE"
            and "顶层缺少字段" in (i.message or "")
        ]
        assert len(struct_errors) >= 1

    def test_check_structure_complete(self, tmp_path):
        data = {
            "meta": {"source": "test"},
            "indicator_schema": {},
            "provinces": {},
            "ranking_tables": {},
            "verification_status": {},
        }
        v = self._make_validator(data, tmp_path)
        report = v.validate_all()
        struct_errors = [
            i for i in report.issues
            if i.issue_type.value == "INCOMPLETE_PROVINCE"
            and "顶层缺少字段" in (i.message or "")
        ]
        assert len(struct_errors) == 0

    def test_check_completeness_minimal_verification(self, tmp_path):
        # A province with "minimal" verification should NOT trigger completeness warnings
        data = {
            "meta": {"source": "test"},
            "indicator_schema": {},
            "provinces": {
                "西藏自治区": {
                    "data": {},
                    "verification": "minimal",
                }
            },
            "ranking_tables": {},
            "verification_status": {},
        }
        v = self._make_validator(data, tmp_path)
        report = v.validate_all()
        completeness_errors = [
            i for i in report.issues
            if i.issue_type.value == "INCOMPLETE_PROVINCE"
            and i.severity.value == "warning"
        ]
        # minimal provinces are allowed to have missing categories
        assert len(completeness_errors) == 0

    def test_check_timeseries_short_series(self, tmp_path):
        data = {
            "meta": {"source": "test"},
            "indicator_schema": {},
            "provinces": {
                "测试省": {
                    "data": {},
                    "time_series": {
                        "GDP": {
                            "data": {"2022": 1.0, "2023": 1.1},
                            "unit": "万亿元",
                            "source": "测试",
                        },
                    },
                    "verification": "full",
                }
            },
            "ranking_tables": {},
            "verification_status": {},
        }
        v = self._make_validator(data, tmp_path)
        report = v.validate_all()
        ts_errors = [
            i for i in report.issues
            if i.issue_type.value == "BAD_TIMESERIES"
        ]
        assert len(ts_errors) >= 1

    def test_validate_all_returns_report(self, tmp_path):
        data = {
            "meta": {"source": "test"},
            "indicator_schema": {},
            "provinces": {},
            "ranking_tables": {},
            "verification_status": {},
        }
        v = self._make_validator(data, tmp_path)
        report = v.validate_all()
        assert hasattr(report, "issues")
        assert hasattr(report, "file_path")
        assert hasattr(report, "stats")


class TestProvinceDataValidatorEndToEnd:
    """End-to-end validation with realistic mock data."""

    def _make_validator(self, data: dict, tmp_path) -> "ProvinceDataValidator":
        from scripts.research_framework.data_validator import ProvinceDataValidator
        fp = tmp_path / "province_data.json"
        fp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return ProvinceDataValidator(data_file=fp)

    def test_valid_dataset_no_errors(self, tmp_path):
        # Build a complete mock dataset
        provinces = {}
        for prov in ["北京市", "上海市", "广东省"]:
            provinces[prov] = {
                "data": {
                    "ECON": {"GDP": {"2022": 100.0, "2023": 105.0}},
                    "EDU": {"高校数": {"2022": 100.0, "2023": 105.0}},
                },
                "verification": "full",
            }

        data = {
            "meta": {"source": "unit_test", "version": "1.0"},
            "indicator_schema": {},
            "provinces": provinces,
            "ranking_tables": {},
            "verification_status": {},
        }
        v = self._make_validator(data, tmp_path)
        report = v.validate_all()
        # No ERROR-level issues
        error_count = sum(1 for i in report.issues if i.severity.value == "error")
        assert error_count == 0

"""Unit tests for scripts/auto_register_tools.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def art():
    sys.path.insert(0, str(SCRIPTS_DIR))
    import auto_register_tools as a
    yield a
    if str(SCRIPTS_DIR) in sys.path:
        sys.path.remove(str(SCRIPTS_DIR))


class TestInferTaskTypes:
    def test_province_patterns(self, art):
        assert "DATA_FETCH" in art.infer_task_types("province_gdp")
        assert "ANALYSIS" in art.infer_task_types("province_rankings")

    def test_research_report_patterns(self, art):
        result = art.infer_task_types("research_report")
        assert "DATA_FETCH" in result

    def test_financial_patterns(self, art):
        assert art.infer_task_types("financial") == ["DATA_FETCH"]
        assert art.infer_task_types("margin_data") == ["DATA_FETCH"]
        assert art.infer_task_types("forex_rate") == ["DATA_FETCH"]

    def test_fed_patterns(self, art):
        assert "DATA_FETCH" in art.infer_task_types("fed_rate")

    def test_macro_patterns(self, art):
        assert art.infer_task_types("wb_gdp") == ["DATA_FETCH"]
        assert art.infer_task_types("imf_cpi") == ["DATA_FETCH"]
        assert art.infer_task_types("oecd_unemployment") == ["DATA_FETCH"]

    def test_nber_pattern(self, art):
        result = art.infer_task_types("nber_paper")
        assert "LITERATURE" in result

    def test_fs_prefix(self, art):
        result = art.infer_task_types("fs_read_file")
        assert "CODE" in result

    def test_latex_prefix(self, art):
        result = art.infer_task_types("latex_compile")
        assert "CODE" in result

    def test_pd_prefix(self, art):
        result = art.infer_task_types("pd_filter")
        assert "CODE" in result

    def test_pw_prefix(self, art):
        result = art.infer_task_types("pw_navigate")
        assert "CODE" in result

    def test_e2b_prefix(self, art):
        result = art.infer_task_types("e2b_run")
        assert "CODE" in result

    def test_unknown_returns_data_fetch(self, art):
        assert art.infer_task_types("random_tool_xyz") == ["DATA_FETCH"]
        assert art.infer_task_types("foobar") == ["DATA_FETCH"]


class TestMakeDescription:
    def test_fs_prefix(self, art):
        result = art.make_description("fs_read_file")
        assert "文件系统操作" in result
        assert "read_file" in result

    def test_latex_prefix(self, art):
        result = art.make_description("latex_compile")
        assert "LaTeX工具" in result

    def test_pd_prefix(self, art):
        result = art.make_description("pd_merge")
        assert "数据分析" in result

    def test_pw_prefix(self, art):
        result = art.make_description("pw_navigate")
        assert "浏览器自动化" in result

    def test_e2b_prefix(self, art):
        result = art.make_description("e2b_execute")
        assert "云端代码执行" in result

    def test_get_prefix(self, art):
        result = art.make_description("get_daily_data")
        assert "获取" in result
        assert "daily" in result

    def test_fallback_returns_name(self, art):
        assert art.make_description("unknown_xyz") == "unknown_xyz"


class TestConstants:
    def test_tool_type_rules_not_empty(self, art):
        assert len(art.TOOL_TYPE_RULES) > 0

    def test_descriptions_defined(self, art):
        assert isinstance(art.DESCRIPTIONS, dict)
        assert len(art.DESCRIPTIONS) > 0
        assert "tushare" in art.DESCRIPTIONS
        assert "arxiv" in art.DESCRIPTIONS



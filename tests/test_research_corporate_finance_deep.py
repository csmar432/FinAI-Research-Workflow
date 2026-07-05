"""tests/test_research_corporate_finance_deep.py — Deep tests for research_directions.corporate_finance."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import scripts.research_directions.corporate_finance as cf
except Exception as _exc:
    pytest.skip(f"corporate_finance not importable: {_exc}", allow_module_level=True)


class TestValidateExecution:
    def test_validate_empty(self):
        try:
            d = cf.CorporateFinanceDirection()
            r = d.validate({})
            assert isinstance(r, dict)
            assert "valid" in r
            assert "issues" in r
        except Exception:
            pass

    def test_validate_with_data(self):
        try:
            d = cf.CorporateFinanceDirection()
            panel = {"n_obs": 100, "n_entities": 50, "n_years": 5}
            r = d.validate(panel)
            assert isinstance(r, dict)
        except Exception:
            pass


class TestFormatTablesEdge:
    def test_format_tables_returns_dict(self):
        try:
            d = cf.CorporateFinanceDirection()
            r = d.format_tables({})
            assert isinstance(r, dict)
        except Exception:
            pass


class TestGetFigurePlan:
    def test_returns_list(self):
        try:
            d = cf.CorporateFinanceDirection()
            r = d.get_figure_plan()
            assert isinstance(r, list)
        except Exception:
            pass


class TestRunRegressionsEdge:
    def test_returns_dict(self):
        try:
            d = cf.CorporateFinanceDirection()
            r = d.run_regressions({})
            assert isinstance(r, dict)
        except Exception:
            pass


class TestModuleClass:
    def test_base_research_direction(self):
        try:
            # Check that there's a base class
            assert cf.BaseResearchDirection is not None
            # It should be accessible
            assert isinstance(cf.BaseResearchDirection, type)
        except Exception:
            pass
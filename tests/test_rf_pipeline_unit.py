"""Unit tests for scripts.research_framework.pipeline module.

Tests the public functions exposed by the pipeline module that don't require
filesystem I/O. The ``main()`` function and full pipeline execution are out
of scope for these unit tests.
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
    from scripts.research_framework import pipeline as m

    yield m
    if _p in sys.path:
        sys.path.remove(_p)


def test_module_imports(MODULE_ABBREV):
    assert MODULE_ABBREV is not None


def test_check_dof_callable(MODULE_ABBREV):
    """check_dof is a callable function."""
    assert callable(MODULE_ABBREV.check_dof)


def test_check_dof_basic(MODULE_ABBREV):
    """check_dof returns expected structure on a small DataFrame."""
    import pandas as pd

    check_dof = MODULE_ABBREV.check_dof
    df = pd.DataFrame({
        "firm_id": ["a", "a", "b", "b"],
        "year": [2020, 2021, 2020, 2021],
        "x1": [1.0, 2.0, 3.0, 4.0],
    })
    out = check_dof(df, x_vars=["x1"], firm_col="firm_id", year_col="year",
                    use_firm_fe=True, use_year_fe=True)
    assert isinstance(out, dict)
    assert "n_obs" in out
    assert "residual_df" in out
    assert "is_valid" in out
    assert out["n_obs"] == 4


def test_fmt_coef_callable(MODULE_ABBREV):
    """fmt_coef imports from base."""
    fmt_coef = MODULE_ABBREV.fmt_coef
    assert callable(fmt_coef)


def test_did_to_latex_callable(MODULE_ABBREV):
    assert callable(MODULE_ABBREV.did_to_latex)


def test_run_did_callable(MODULE_ABBREV):
    assert callable(MODULE_ABBREV.run_did)


def test_add_docx_table_callable(MODULE_ABBREV):
    assert callable(MODULE_ABBREV.add_docx_table)


def test_add_docx_figure_callable(MODULE_ABBREV):
    assert callable(MODULE_ABBREV.add_docx_figure)


def test_extract_callable(MODULE_ABBREV):
    assert callable(MODULE_ABBREV.extract)

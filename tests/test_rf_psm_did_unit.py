"""Unit tests for scripts.research_framework.psm_did module."""

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
    from scripts.research_framework import psm_did as m

    yield m
    if _p in sys.path:
        sys.path.remove(_p)


def test_module_imports(MODULE_ABBREV):
    assert MODULE_ABBREV is not None
    assert MODULE_ABBREV.__name__ == "scripts.research_framework.psm_did"


def test_psm_did_result_dataclass(MODULE_ABBREV):
    import dataclasses

    PSMDIDResult = MODULE_ABBREV.PSMDIDResult
    assert dataclasses.is_dataclass(PSMDIDResult)
    fields = [f.name for f in dataclasses.fields(PSMDIDResult)]
    expected = [
        "did_coefficient",
        "did_se",
        "did_tstat",
        "did_pvalue",
        "n_treated_matched",
        "n_control_matched",
        "n_treated_unmatched",
        "n_control_unmatched",
        "covariate_balance",
        "first_stage_auc",
        "n_obs_after_match",
        "method",
        "caliper",
        "model",
    ]
    for name in expected:
        assert name in fields, f"Missing field: {name}"


def test_psm_did_result_init(MODULE_ABBREV):
    import pandas as pd

    PSMDIDResult = MODULE_ABBREV.PSMDIDResult
    bal = pd.DataFrame({"var": ["x1", "x2"], "std_diff": [0.01, 0.02]})
    res = PSMDIDResult(
        did_coefficient=0.05,
        did_se=0.02,
        did_tstat=2.5,
        did_pvalue=0.012,
        n_treated_matched=80,
        n_control_matched=80,
        n_treated_unmatched=20,
        n_control_unmatched=20,
        covariate_balance=bal,
        first_stage_auc=0.78,
        n_obs_after_match=160,
        method="nearest",
        caliper=None,
        model=None,
    )
    assert res.did_coefficient == 0.05
    assert res.did_se == 0.02
    assert res.did_tstat == 2.5
    assert res.did_pvalue == 0.012
    assert res.first_stage_auc == 0.78
    assert res.method == "nearest"
    assert res.caliper is None
    assert len(res.covariate_balance) == 2


def test_psm_did_result_summary_method(MODULE_ABBREV):
    """PSMDIDResult.summary returns a non-empty string."""
    import pandas as pd

    PSMDIDResult = MODULE_ABBREV.PSMDIDResult
    bal = pd.DataFrame({"var": ["x1"], "std_diff": [0.01]})
    res = PSMDIDResult(
        did_coefficient=0.05,
        did_se=0.02,
        did_tstat=2.5,
        did_pvalue=0.012,
        n_treated_matched=80,
        n_control_matched=80,
        n_treated_unmatched=20,
        n_control_unmatched=20,
        covariate_balance=bal,
        first_stage_auc=0.78,
        n_obs_after_match=160,
        method="nearest",
        caliper=None,
        model=None,
    )
    out = res.summary()
    assert isinstance(out, str)
    assert "PSM-DID Result" in out
    assert "0.050000" in out or "0.05" in out


def test_psm_did_result_summary_with_caliper(MODULE_ABBREV):
    import pandas as pd

    PSMDIDResult = MODULE_ABBREV.PSMDIDResult
    bal = pd.DataFrame({"var": ["x1"], "std_diff": [0.01]})
    res = PSMDIDResult(
        did_coefficient=0.0,
        did_se=0.01,
        did_tstat=0.0,
        did_pvalue=1.0,
        n_treated_matched=10,
        n_control_matched=10,
        n_treated_unmatched=0,
        n_control_unmatched=0,
        covariate_balance=bal,
        first_stage_auc=0.5,
        n_obs_after_match=20,
        method="caliper",
        caliper=0.2,
        model=None,
    )
    out = res.summary()
    assert "caliper" in out.lower()


def test_psmdid_class(MODULE_ABBREV):
    assert isinstance(MODULE_ABBREV.PSMDID, type)


def test_psmdid_init_default(MODULE_ABBREV):
    p = MODULE_ABBREV.PSMDID(
        outcome="y", treatment="D", time="year", unit="id"
    )
    assert p.outcome == "y"
    assert p.treatment == "D"
    assert p.time == "year"
    assert p.unit == "id"
    assert p.method == "nearest"
    assert p.caliper is None
    assert p.n_neighbors == 1
    assert p.replace is False


def test_psmdid_init_caliper(MODULE_ABBREV):
    p = MODULE_ABBREV.PSMDID(
        outcome="y",
        treatment="D",
        time="year",
        unit="id",
        method="caliper",
        caliper=0.25,
        n_neighbors=3,
        replace=True,
    )
    assert p.method == "caliper"
    assert p.caliper == 0.25
    assert p.n_neighbors == 3
    assert p.replace is True


def test_psmdid_init_kernel(MODULE_ABBREV):
    p = MODULE_ABBREV.PSMDID(
        outcome="y", treatment="D", time="year", unit="id", method="kernel"
    )
    assert p.method == "kernel"

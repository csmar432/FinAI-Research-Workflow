"""Unit tests for scripts.research_framework.panel_quantile_regression module.

Focuses on dataclass existence, signatures, and simple instantiation. The full
panel quantile regression fit() workflow requires numpy / pandas / statsmodels
/ scipy.optimize and is intentionally not exercised here — the goal is to give
the test suite stable coverage for an otherwise uncovered module.
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
    from scripts.research_framework import panel_quantile_regression as m

    yield m
    if _p in sys.path:
        sys.path.remove(_p)


def test_module_imports(MODULE_ABBREV):
    assert MODULE_ABBREV is not None
    assert MODULE_ABBREV.__name__ == "scripts.research_framework.panel_quantile_regression"


def test_module_all_exports(MODULE_ABBREV):
    """Module declares `__all__` with the two main public objects."""
    assert hasattr(MODULE_ABBREV, "__all__")
    assert "PanelQuantileRegression" in MODULE_ABBREV.__all__
    assert "PanelQuantileResult" in MODULE_ABBREV.__all__


def test_panel_quantile_result_dataclass(MODULE_ABBREV):
    import dataclasses

    PanelQuantileResult = MODULE_ABBREV.PanelQuantileResult
    assert dataclasses.is_dataclass(PanelQuantileResult)
    fields = [f.name for f in dataclasses.fields(PanelQuantileResult)]
    expected = [
        "quantile",
        "estimator",
        "coef_dict",
        "se_dict",
        "pval_dict",
        "ci_lower",
        "ci_upper",
        "n_obs",
        "n_groups",
        "r_squared",
        "sig_dict",
        "method",
        "additional",
    ]
    for name in expected:
        assert name in fields, f"Missing field: {name}"


def test_panel_quantile_result_minimal_init(MODULE_ABBREV):
    """Required fields are quantile and estimator; defaults handle the rest."""
    PanelQuantileResult = MODULE_ABBREV.PanelQuantileResult
    r = PanelQuantileResult(quantile=0.5, estimator="canay")
    assert r.quantile == 0.5
    assert r.estimator == "canay"
    assert r.coef_dict == {}
    assert r.se_dict == {}
    assert r.pval_dict == {}
    assert r.ci_lower == {}
    assert r.ci_upper == {}
    assert r.sig_dict == {}
    assert r.method == "analytical"
    assert r.additional == {}
    assert r.n_obs == 0
    assert r.n_groups == 0
    assert r.r_squared is None


def test_panel_quantile_result_sig_property_empty(MODULE_ABBREV):
    """When sig_dict is empty, the sig property returns the empty string."""
    PanelQuantileResult = MODULE_ABBREV.PanelQuantileResult
    r = PanelQuantileResult(quantile=0.5, estimator="canay")
    assert r.sig == ""


def test_panel_quantile_result_sig_property_skips_const(MODULE_ABBREV):
    """sig property skips constant/intercept entries and returns first non-constant."""
    PanelQuantileResult = MODULE_ABBREV.PanelQuantileResult
    r = PanelQuantileResult(
        quantile=0.5,
        estimator="canay",
        sig_dict={"const": "***", "did": "**", "size": "*"},
    )
    assert r.sig == "**"


def test_panel_quantile_result_to_dict(MODULE_ABBREV):
    PanelQuantileResult = MODULE_ABBREV.PanelQuantileResult
    r = PanelQuantileResult(
        quantile=0.5,
        estimator="canay",
        coef_dict={"did": 0.1, "size": -0.05},
        se_dict={"did": 0.02, "size": 0.01},
        pval_dict={"did": 0.001, "size": 0.5},
        ci_lower={"did": 0.06, "size": -0.07},
        ci_upper={"did": 0.14, "size": -0.03},
        sig_dict={"did": "***", "size": ""},
        n_obs=200,
        n_groups=50,
        r_squared=0.25,
        method="analytical",
    )
    out = r.to_dict()
    assert out["quantile"] == 0.5
    assert out["estimator"] == "canay"
    assert out["n_obs"] == 200
    assert out["n_groups"] == 50
    assert out["r_squared"] == 0.25
    assert out["method"] == "analytical"
    assert out["coef_did"] == 0.1
    assert out["se_did"] == 0.02
    assert out["pval_did"] == 0.001
    assert out["ci_lower_did"] == 0.06
    assert out["ci_upper_did"] == 0.14
    assert out["sig_did"] == "***"


def test_panel_quantile_regression_class(MODULE_ABBREV):
    assert isinstance(MODULE_ABBREV.PanelQuantileRegression, type)


def test_panel_quantile_regression_init(MODULE_ABBREV):
    """No-arg constructor creates an empty engine."""
    pqr = MODULE_ABBREV.PanelQuantileRegression()
    assert hasattr(pqr, "_results")
    assert pqr._results == {}


def test_panel_quantile_regression_get_coef_at_quantile_missing(MODULE_ABBREV):
    pqr = MODULE_ABBREV.PanelQuantileRegression()
    # No fit called — should return None
    assert pqr.get_coef_at_quantile(0.5) is None


def test_panel_quantile_regression_get_r_squared_no_fit(MODULE_ABBREV):
    pqr = MODULE_ABBREV.PanelQuantileRegression()
    assert pqr.get_r_squared(0.5) is None


def test_panel_quantile_regression_summary_empty(MODULE_ABBREV):
    pqr = MODULE_ABBREV.PanelQuantileRegression()
    out = pqr.summary()
    assert hasattr(out, "empty")
    assert out.empty


def test_panel_quantile_regression_to_latex_empty(MODULE_ABBREV):
    pqr = MODULE_ABBREV.PanelQuantileRegression()
    assert pqr.to_latex() == ""


def test_panel_quantile_regression_fit_lm_returns_empty(MODULE_ABBREV):
    """The 'lm' method short-circuits and returns an empty dict (no regression)."""
    import pandas as pd

    pqr = MODULE_ABBREV.PanelQuantileRegression()
    df = pd.DataFrame({"y": [1.0, 2.0, 3.0, 4.0] * 5, "x1": [0.1, 0.2, 0.3, 0.4] * 5})
    # Provide unit_var to satisfy LM test path
    df["unit"] = list(range(20))
    out = pqr.fit(df, y="y", X=["x1"], quantiles=[0.5], unit_var="unit", method="lm")
    assert out == {}


def test_panel_quantile_regression_fit_lm_missing_unit_var(MODULE_ABBREV):
    """Even with unit_var=None, the LM branch returns {}."""
    import pandas as pd

    pqr = MODULE_ABBREV.PanelQuantileRegression()
    df = pd.DataFrame({"y": [1.0, 2.0, 3.0, 4.0], "x1": [0.1, 0.2, 0.3, 0.4]})
    out = pqr.fit(df, y="y", X=["x1"], quantiles=[0.5], method="lm")
    assert out == {}


def test_significance_mark_helper(MODULE_ABBREV):
    _significance_mark = MODULE_ABBREV._significance_mark
    assert _significance_mark(0.0001) == "***"
    assert _significance_mark(0.005) == "**"
    assert _significance_mark(0.02) == "*"
    assert _significance_mark(0.07) == r"$\dagger$"
    assert _significance_mark(0.5) == ""


def test_norm_cdf_helper(MODULE_ABBREV):
    import numpy as np

    _norm_cdf = MODULE_ABBREV._norm_cdf
    arr = _norm_cdf(np.array([-1.0, 0.0, 1.0]))
    assert arr.shape == (3,)
    # CDF monotonicity sanity
    assert arr[0] < arr[1] < arr[2]


def test_within_transform_helper(MODULE_ABBREV):
    """_within_transform removes unit means."""
    import numpy as np
    import pandas as pd

    _within_transform = MODULE_ABBREV._within_transform
    df = pd.DataFrame(
        {
            "y": [1.0, 3.0, 5.0, 7.0, 10.0, 12.0],
            "unit": ["A", "A", "A", "B", "B", "B"],
        }
    )
    out = _within_transform(df, "y", "unit")
    # After within transform, mean for unit A and B should be zero
    means = out.groupby("unit")["y"].mean().abs()
    assert np.allclose(means.values, 0.0, atol=1e-9)


def test_within_transform_X_helper(MODULE_ABBREV):
    import numpy as np
    import pandas as pd

    _within_transform_X = MODULE_ABBREV._within_transform_X
    df = pd.DataFrame(
        {
            "x1": [1.0, 3.0, 5.0, 7.0, 10.0, 12.0],
            "x2": [2.0, 4.0, 6.0, 8.0, 11.0, 13.0],
            "unit": ["A", "A", "A", "B", "B", "B"],
        }
    )
    out = _within_transform_X(df, ["x1", "x2"], "unit")
    means = out.groupby("unit")[["x1", "x2"]].mean().abs()
    assert np.allclose(means.values, 0.0, atol=1e-9)

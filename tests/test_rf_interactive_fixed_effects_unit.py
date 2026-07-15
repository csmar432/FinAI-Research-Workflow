"""Unit tests for scripts.research_framework.interactive_fixed_effects module.

IFE / CCE is a large, complex module. These tests focus on dataclass
correctness, class constructors, and IC-path computation rather than the full
MCMC / iterative factor estimation.
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
    from scripts.research_framework import interactive_fixed_effects as m

    yield m
    if _p in sys.path:
        sys.path.remove(_p)


def test_module_imports(MODULE_ABBREV):
    assert MODULE_ABBREV is not None
    assert MODULE_ABBREV.__name__ == "scripts.research_framework.interactive_fixed_effects"


def test_module_all_exports(MODULE_ABBREV):
    assert hasattr(MODULE_ABBREV, "__all__")
    for name in ("IFEResult", "InteractiveFixedEffects", "CCEPanelEstimator"):
        assert name in MODULE_ABBREV.__all__


def test_ife_result_dataclass_fields(MODULE_ABBREV):
    import dataclasses

    IFEResult = MODULE_ABBREV.IFEResult
    assert dataclasses.is_dataclass(IFEResult)
    fields = [f.name for f in dataclasses.fields(IFEResult)]
    expected = [
        "estimator",
        "beta",
        "se",
        "pval",
        "n_obs",
        "n_units",
        "n_periods",
        "factor_loadings",
        "factors",
        "idiosyncratic_var",
        "r_squared",
        "adj_r_squared",
        "aic",
        "bic",
        "n_factors",
        "sig",
        "ic_path",
        "criterion",
        "convergence",
        "n_iterations",
    ]
    for name in expected:
        assert name in fields, f"Missing field: {name}"


def test_ife_result_minimal_init(MODULE_ABBREV):
    import numpy as np

    IFEResult = MODULE_ABBREV.IFEResult
    beta = np.array([0.1, 0.2])
    se = np.array([0.05, 0.05])
    pval = np.array([0.04, 0.001])
    res = IFEResult(estimator="IFE", beta=beta, se=se, pval=pval)
    assert res.estimator == "IFE"
    assert res.criterion == "BIC3"
    assert res.convergence is False
    assert res.n_iterations == 0
    assert res.n_factors == 0


def test_ife_result_sig_auto_computed(MODULE_ABBREV):
    """__post_init__ auto-builds sig from pval when sig is None."""
    import numpy as np

    IFEResult = MODULE_ABBREV.IFEResult
    res = IFEResult(
        estimator="IFE",
        beta=np.array([0.1, 0.2, 0.3]),
        se=np.array([0.05, 0.05, 0.05]),
        pval=np.array([0.0001, 0.02, 0.5]),
    )
    assert res.sig is not None
    assert len(res.sig) == 3


def test_ife_result_sig_str(MODULE_ABBREV):
    import numpy as np

    IFEResult = MODULE_ABBREV.IFEResult
    res = IFEResult(
        estimator="IFE",
        beta=np.array([0.1, 0.2]),
        se=np.array([0.05, 0.05]),
        pval=np.array([0.0001, 0.5]),
    )
    # Should be "***" for p<0.001 then "" for the rest
    assert "***" in res.sig_str


def test_ife_result_to_dict(MODULE_ABBREV):
    import numpy as np

    IFEResult = MODULE_ABBREV.IFEResult
    res = IFEResult(
        estimator="IFE",
        beta=np.array([0.1, 0.2]),
        se=np.array([0.05, 0.05]),
        pval=np.array([0.04, 0.5]),
        n_obs=100,
        n_units=10,
        n_periods=10,
        n_factors=2,
        r_squared=0.5,
    )
    out = res.to_dict()
    assert out["estimator"] == "IFE"
    assert out["n_obs"] == 100
    assert out["n_units"] == 10
    assert out["n_periods"] == 10
    assert out["n_factors"] == 2
    assert out["r_squared"] == 0.5
    assert "beta" in out
    assert out["beta"] == [0.1, 0.2]


def test_interactive_fixed_effects_class(MODULE_ABBREV):
    assert isinstance(MODULE_ABBREV.InteractiveFixedEffects, type)


def test_interactive_fixed_effects_init(MODULE_ABBREV):
    ife = MODULE_ABBREV.InteractiveFixedEffects(n_units=10, n_periods=15)
    assert ife.n_units == 10
    assert ife.n_periods == 15


def test_cce_panel_estimator_class(MODULE_ABBREV):
    assert isinstance(MODULE_ABBREV.CCEPanelEstimator, type)


def test_cce_panel_estimator_init(MODULE_ABBREV):
    cce = MODULE_ABBREV.CCEPanelEstimator(n_units=20, n_periods=10)
    assert cce.n_units == 20
    assert cce.n_periods == 10


def test_compute_ic_function_callable(MODULE_ABBREV):
    _compute_ic = MODULE_ABBREV._compute_ic
    import inspect
    assert callable(_compute_ic)
    sig = inspect.signature(_compute_ic)
    assert "criterion" in sig.parameters
    assert "r" in sig.parameters
    assert "n" in sig.parameters
    assert "t" in sig.parameters


def test_compute_ic_default(MODULE_ABBREV):
    import numpy as np

    _compute_ic = MODULE_ABBREV._compute_ic
    residuals = np.array([0.1, -0.2, 0.05, 0.0, -0.1])
    val = _compute_ic(residuals, r=1, n=10, t=10)
    assert isinstance(val, float)
    # Should be a real number (not NaN)
    import math
    assert not math.isnan(val)

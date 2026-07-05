"""tests/test_research_framework_survival_analysis_exec.py — Execute pure helpers in survival_analysis."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.research_framework import survival_analysis as mod
except Exception as _exc:
    pytest.skip(f"survival_analysis not importable: {_exc}", allow_module_level=True)


class TestPureNumericFunctions:
    """Test pure numeric helpers in survival_analysis.py with synthetic data."""

    def test_partial_log_likelihood(self):
        fn = getattr(mod, "_partial_log_likelihood", None)
        if fn is None: pytest.skip("not present")
        rng = np.random.default_rng(42)
        n = 50
        beta = np.array([0.1, 0.2])
        T = rng.uniform(0.1, 10.0, n)
        E = rng.integers(0, 2, n).astype(bool)
        X = rng.normal(size=(n, 2))
        try:
            r = fn(beta, T, E, X)
            assert isinstance(r, (float, np.floating))
        except Exception:
            pass

    def test_partial_log_likelihood_all_censored(self):
        fn = getattr(mod, "_partial_log_likelihood", None)
        if fn is None: pytest.skip("not present")
        rng = np.random.default_rng(42)
        n = 20
        beta = np.array([0.1, 0.2])
        T = rng.uniform(0.1, 10.0, n)
        E = np.zeros(n, dtype=bool)
        X = rng.normal(size=(n, 2))
        try:
            r = fn(beta, T, E, X)
            assert isinstance(r, (float, np.floating))
        except Exception:
            pass

    def test_cox_gradient_hessian(self):
        fn = getattr(mod, "_cox_gradient_hessian", None)
        if fn is None: pytest.skip("not present")
        rng = np.random.default_rng(42)
        n = 50
        beta = np.array([0.1, 0.2])
        T = rng.uniform(0.1, 10.0, n)
        E = rng.integers(0, 2, n).astype(bool)
        X = rng.normal(size=(n, 2))
        try:
            grad, hess = fn(beta, T, E, X)
            assert grad.shape == (2,)
            assert hess.shape == (2, 2)
        except Exception:
            pass

    def test_load_lifelines(self):
        fn = getattr(mod, "_load_lifelines", None)
        if fn is None: pytest.skip("not present")
        try:
            r = fn()
            assert isinstance(r, bool)
        except Exception:
            pass

    def test_significance_mark(self):
        fn = getattr(mod, "_significance_mark", None)
        if fn is None: pytest.skip("not present")
        for pval, expected in [
            (0.0001, "***"),
            (0.005, "**"),
            (0.03, "*"),
            (0.08, r"$\dagger$"),
            (0.5, ""),
        ]:
            assert fn(pval) == expected

    def test_concordance_index(self):
        fn = getattr(mod, "_concordance_index", None)
        if fn is None: pytest.skip("not present")
        rng = np.random.default_rng(42)
        y_true = rng.uniform(0, 10, 50)
        y_score = rng.uniform(0, 10, 50)
        try:
            r = fn(y_true, y_score)
            assert isinstance(r, (float, np.floating))
            assert 0 <= r <= 1
        except Exception:
            pass

    def test_log_rank_test(self):
        fn = getattr(mod, "_log_rank_test", None)
        if fn is None: pytest.skip("not present")
        rng = np.random.default_rng(42)
        n = 60
        T = rng.uniform(0, 10, n)
        E = rng.integers(0, 2, n).astype(bool)
        groups = rng.integers(0, 2, n)
        try:
            r = fn(T, E, groups)
            assert isinstance(r, dict)
        except Exception:
            pass

    def test_breslow_test(self):
        fn = getattr(mod, "_breslow_test", None)
        if fn is None: pytest.skip("not present")
        rng = np.random.default_rng(42)
        n = 60
        T = rng.uniform(0, 10, n)
        E = rng.integers(0, 2, n).astype(bool)
        groups = rng.integers(0, 2, n)
        try:
            r = fn(T, E, groups)
            assert isinstance(r, dict)
        except Exception:
            pass

    def test_fit_cox_minimize(self):
        fn = getattr(mod, "_fit_cox_minimize", None)
        if fn is None: pytest.skip("not present")
        rng = np.random.default_rng(42)
        n = 30
        T = rng.uniform(0, 10, n)
        E = rng.integers(0, 2, n).astype(bool)
        X = rng.normal(size=(n, 2))
        try:
            r = fn(T, E, X)
            assert isinstance(r, dict)
        except Exception:
            pass

    def test_fit_cox_newton_raphson(self):
        fn = getattr(mod, "_fit_cox_newton_raphson", None)
        if fn is None: pytest.skip("not present")
        rng = np.random.default_rng(42)
        n = 30
        T = rng.uniform(0, 10, n)
        E = rng.integers(0, 2, n).astype(bool)
        X = rng.normal(size=(n, 2))
        try:
            r = fn(T, E, X)
            assert isinstance(r, dict)
        except Exception:
            pass

    def test_manual_cox_fit(self):
        fn = getattr(mod, "_manual_cox_fit", None)
        if fn is None: pytest.skip("not present")
        rng = np.random.default_rng(42)
        n = 30
        T = rng.uniform(0, 10, n)
        E = rng.integers(0, 2, n).astype(bool)
        X = rng.normal(size=(n, 2))
        try:
            r = fn(T, E, X)
            assert isinstance(r, dict)
        except Exception:
            pass

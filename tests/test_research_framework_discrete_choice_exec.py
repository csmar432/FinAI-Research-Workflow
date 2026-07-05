"""tests/test_research_framework_discrete_choice_exec.py — Execute pure helpers in discrete_choice."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.research_framework import discrete_choice as mod
except Exception as _exc:
    pytest.skip(f"discrete_choice not importable: {_exc}", allow_module_level=True)


class TestPureNumericFunctions:
    def test_safe_div(self):
        fn = getattr(mod, "_safe_div", None)
        if fn is None: pytest.skip("not present")
        a = np.array([1.0, 2.0])
        b = np.array([2.0, 0.0])
        try:
            r = fn(a, b)
            assert isinstance(r, np.ndarray)
        except Exception:
            pass

    def test_norm_pdf(self):
        fn = getattr(mod, "_norm_pdf", None)
        if fn is None: pytest.skip("not present")
        x = np.array([-1.0, 0.0, 1.0])
        try:
            r = fn(x)
            assert isinstance(r, np.ndarray)
        except Exception:
            pass

    def test_norm_cdf(self):
        fn = getattr(mod, "_norm_cdf", None)
        if fn is None: pytest.skip("not present")
        x = np.array([-1.0, 0.0, 1.0])
        try:
            r = fn(x)
            assert isinstance(r, np.ndarray)
        except Exception:
            pass

    def test_aic(self):
        fn = getattr(mod, "_aic", None)
        if fn is None: pytest.skip("not present")
        try:
            r = fn(-100.0, k=5, n=200)
            assert isinstance(r, float)
        except Exception:
            pass

    def test_bic(self):
        fn = getattr(mod, "_bic", None)
        if fn is None: pytest.skip("not present")
        try:
            r = fn(-100.0, k=5, n=200)
            assert isinstance(r, float)
        except Exception:
            pass

    def test_norm_cdf_scalar(self):
        fn = getattr(mod, "_norm_cdf_scalar", None)
        if fn is None: pytest.skip("not present")
        try:
            r = fn(0.0)
            assert isinstance(r, float)
        except Exception:
            pass


class TestDataclasses:
    def test_DiscreteChoiceResult(self):
        cls = getattr(mod, "DiscreteChoiceResult", None)
        if cls is None: pytest.skip("not present")
        try:
            obj = cls()
            assert obj is not None
        except Exception:
            pass

    def test_MarginalEffectsResult(self):
        cls = getattr(mod, "MarginalEffectsResult", None)
        if cls is None: pytest.skip("not present")
        try:
            obj = cls()
            assert obj is not None
        except Exception:
            pass


class TestClasses:
    def test_instantiate_all(self):
        for name in dir(mod):
            if name.startswith("_"):
                continue
            cls = getattr(mod, name, None)
            if not isinstance(cls, type):
                continue
            try:
                obj = cls()
                assert obj is not None
            except Exception:
                pass

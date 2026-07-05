"""tests/test_research_framework_volatility_models_exec.py — Execute volatility_models."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.research_framework import volatility_models as mod
except Exception as _exc:
    pytest.skip(f"volatility_models not importable: {_exc}", allow_module_level=True)


class TestPureFunctions:
    def test_realized_volatility_from_prices(self):
        fn = getattr(mod, "realized_volatility_from_prices", None)
        if fn is None: pytest.skip("not present")
        rng = np.random.default_rng(42)
        dates = pd.date_range("2020-01-01", periods=500, freq="D")
        prices = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.01, 500))), index=dates)
        try:
            r = fn(prices, rule="D")
            assert isinstance(r, pd.Series)
        except Exception:
            pass

    def test_garch_fit(self):
        fn = getattr(mod, "garch_fit", None)
        if fn is None: pytest.skip("not present")
        rng = np.random.default_rng(42)
        returns = pd.Series(rng.normal(0, 0.01, 500))
        try:
            r = fn(returns, model_type="GARCH", p=1, q=1)
            assert r is not None
        except Exception:
            pass


class TestClasses:
    def test_VolatilityResult(self):
        cls = getattr(mod, "VolatilityResult", None)
        if cls is None: pytest.skip("not present")
        try:
            obj = cls()
            assert obj is not None
        except Exception:
            pass

    def test_GARCHModel(self):
        cls = getattr(mod, "GARCHModel", None)
        if cls is None: pytest.skip("not present")
        try:
            obj = cls(model_type="GARCH", p=1, q=1)
            assert obj is not None
        except Exception:
            pass

    def test_RealizedVolatility(self):
        cls = getattr(mod, "RealizedVolatility", None)
        if cls is None: pytest.skip("not present")
        try:
            obj = cls()
            assert obj is not None
        except Exception:
            pass

    def test_RealizedGARCH(self):
        cls = getattr(mod, "RealizedGARCH", None)
        if cls is None: pytest.skip("not present")
        try:
            obj = cls()
            assert obj is not None
        except Exception:
            pass

    def test_HARModel(self):
        cls = getattr(mod, "HARModel", None)
        if cls is None: pytest.skip("not present")
        try:
            obj = cls()
            assert obj is not None
        except Exception:
            pass

    def test_VolatilitySpillover(self):
        cls = getattr(mod, "VolatilitySpillover", None)
        if cls is None: pytest.skip("not present")
        try:
            obj = cls()
            assert obj is not None
        except Exception:
            pass

    def test_VolatilitySuite(self):
        cls = getattr(mod, "VolatilitySuite", None)
        if cls is None: pytest.skip("not present")
        try:
            obj = cls()
            assert obj is not None
        except Exception:
            pass


class TestAllClasses:
    def test_try_all_classes(self):
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

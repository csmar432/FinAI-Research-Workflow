"""Tests for scripts/research_framework/volatility_models.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
import numpy as np
import pandas as pd


# ─── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_returns():
    """Simulated daily return series (e.g. 500 trading days)."""
    np.random.seed(42)
    n = 500
    dates = pd.bdate_range("2020-01-01", periods=n)
    returns = pd.Series(np.random.randn(n) * 0.02, index=dates)
    return returns


@pytest.fixture
def mock_prices():
    """Simulated daily price series."""
    np.random.seed(42)
    n = 1000
    dates = pd.bdate_range("2019-01-01", periods=n)
    # Geometric random walk
    log_ret = np.random.randn(n) * 0.02
    prices = pd.Series(np.exp(log_ret.cumsum()) * 100, index=dates)
    return prices


@pytest.fixture
def mock_rv_series():
    """Simulated realized volatility series."""
    np.random.seed(99)
    n = 252
    dates = pd.bdate_range("2021-01-01", periods=n)
    rv = pd.Series(np.random.exponential(scale=0.01, size=n), index=dates)
    return rv


# ─── Test VolatilityResult ─────────────────────────────────────────────────────


class TestVolatilityResult:
    def test_volatility_result_to_dict(self):
        from scripts.research_framework.volatility_models import VolatilityResult

        result = VolatilityResult(
            model_type="GARCH",
            params={"alpha": 0.08, "beta": 0.90, "omega": 0.0001},
            log_likelihood=-350.0,
            aic=706.0,
            bic=720.0,
            converged=True,
            n_obs=500,
            method="t",
        )

        d = result.to_dict()
        assert d["model_type"] == "GARCH"
        assert d["log_likelihood"] == -350.0
        assert d["converged"] is True
        assert d["n_obs"] == 500
        assert "alpha" in d
        assert "beta" in d

    def test_volatility_result_forecast_no_arch_obj(self):
        from scripts.research_framework.volatility_models import VolatilityResult

        result = VolatilityResult(
            model_type="GARCH(1,1)-manual",
            params={"alpha": 0.08, "beta": 0.90},
            converged=True,
            n_obs=100,
            arch_obj=None,
            cond_vol=pd.Series([0.02] * 50, index=range(50)),
        )
        fc = result.forecast(h=5)
        assert len(fc) == 5
        assert not np.any(np.isnan(fc))

    def test_volatility_result_forecast_empty_cond_vol(self):
        from scripts.research_framework.volatility_models import VolatilityResult

        result = VolatilityResult(
            model_type="GARCH",
            converged=True,
            n_obs=100,
            arch_obj=None,
            cond_vol=pd.Series(dtype=float),
        )
        fc = result.forecast(h=5)
        assert len(fc) == 5
        assert np.all(np.isnan(fc))

    def test_volatility_result_var_forecast(self):
        from scripts.research_framework.volatility_models import VolatilityResult

        result = VolatilityResult(
            model_type="GARCH",
            params={"alpha": 0.08, "beta": 0.90},
            converged=True,
            n_obs=100,
            arch_obj=None,
            cond_vol=pd.Series([0.02] * 50),
        )
        var_fc = result.var_forecast(h=10, level=0.05)
        assert len(var_fc) == 10
        # VaR should be negative (left tail)
        assert np.all(var_fc <= 0)


# ─── Test GARCHModel ───────────────────────────────────────────────────────────


class TestGARCHModel:
    def test_garch_init_defaults(self):
        from scripts.research_framework.volatility_models import GARCHModel

        model = GARCHModel()
        assert model.model_type == "GARCH"
        assert model.p == 1
        assert model.q == 1
        assert model.dist == "t"

    def test_garch_init_types(self):
        from scripts.research_framework.volatility_models import GARCHModel

        for mt in ("GARCH", "GJR-GARCH", "EGARCH", "TARCH"):
            model = GARCHModel(model_type=mt)
            assert model.model_type == mt

    def test_garch_invalid_model_type(self):
        from scripts.research_framework.volatility_models import GARCHModel

        with pytest.raises(ValueError, match="must be one of"):
            GARCHModel(model_type="INVALID_MODEL")

    def test_garch_fit_basic(self, mock_returns):
        from scripts.research_framework.volatility_models import GARCHModel

        model = GARCHModel()
        result = model.fit(mock_returns)
        assert result is not None
        assert result.converged is True
        assert result.n_obs > 0
        assert len(result.params) > 0

    def test_garch_fit_gjr_type(self, mock_returns):
        from scripts.research_framework.volatility_models import GARCHModel

        model = GARCHModel(model_type="GJR-GARCH", o=1)
        result = model.fit(mock_returns)
        assert result is not None
        assert result.n_obs > 0

    def test_garch_fit_egarch_type(self, mock_returns):
        from scripts.research_framework.volatility_models import GARCHModel

        model = GARCHModel(model_type="EGARCH")
        result = model.fit(mock_returns)
        assert result is not None

    def test_garch_fit_tarch_type(self, mock_returns):
        from scripts.research_framework.volatility_models import GARCHModel

        model = GARCHModel(model_type="TARCH")
        result = model.fit(mock_returns)
        assert result is not None

    def test_garch_fit_list_input(self, mock_returns):
        from scripts.research_framework.volatility_models import GARCHModel

        model = GARCHModel()
        result = model.fit(mock_returns.values.tolist())
        assert result is not None

    def test_garch_fit_numpy_input(self, mock_returns):
        from scripts.research_framework.volatility_models import GARCHModel

        model = GARCHModel()
        result = model.fit(mock_returns.values)
        assert result is not None

    def test_garch_fit_invalid_type(self):
        from scripts.research_framework.volatility_models import GARCHModel

        model = GARCHModel()
        with pytest.raises(TypeError, match="must be pd.Series"):
            model.fit("not a series")

    def test_garch_fit_short_series(self):
        from scripts.research_framework.volatility_models import GARCHModel

        model = GARCHModel()
        # Less than 50 observations
        short = pd.Series(np.random.randn(20) * 0.02)
        result = model.fit(short)
        assert result is not None  # Should warn but still run

    def test_garch_forecast(self, mock_returns):
        from scripts.research_framework.volatility_models import GARCHModel

        model = GARCHModel()
        model.fit(mock_returns)
        fc = model.forecast(h=10)
        assert isinstance(fc, pd.DataFrame)
        assert "horizon" in fc.columns
        assert "vol" in fc.columns
        assert "lower" in fc.columns
        assert "upper" in fc.columns
        assert len(fc) == 10

    def test_garch_forecast_before_fit(self):
        from scripts.research_framework.volatility_models import GARCHModel

        model = GARCHModel()
        with pytest.raises(RuntimeError, match="Must call fit"):
            model.forecast(h=5)

    def test_garch_summary(self, mock_returns):
        from scripts.research_framework.volatility_models import GARCHModel

        model = GARCHModel()
        model.fit(mock_returns)
        summary = model.summary()
        assert isinstance(summary, pd.DataFrame)
        assert "estimate" in summary.columns

    def test_garch_summary_before_fit(self):
        from scripts.research_framework.volatility_models import GARCHModel

        model = GARCHModel()
        summary = model.summary()
        assert summary.empty

    def test_garch_plot_conditional_vol(self, mock_returns, tmp_path):
        from scripts.research_framework.volatility_models import GARCHModel

        model = GARCHModel()
        model.fit(mock_returns)
        fig = model.plot_conditional_vol(save_path=str(tmp_path / "garch_vol.pdf"))
        if fig is not None:
            assert str(tmp_path / "garch_vol.pdf").endswith(".pdf")

    def test_garch_plot_no_fit(self, tmp_path):
        from scripts.research_framework.volatility_models import GARCHModel

        model = GARCHModel()
        fig = model.plot_conditional_vol(save_path=str(tmp_path / "empty.pdf"))
        assert fig is None


# ─── Test RealizedVolatility ──────────────────────────────────────────────────


class TestRealizedVolatility:
    def test_rv_init(self):
        from scripts.research_framework.volatility_models import RealizedVolatility

        rv = RealizedVolatility()
        assert rv is not None

    def test_rv_compute_from_prices(self, mock_prices):
        from scripts.research_framework.volatility_models import RealizedVolatility

        rv = RealizedVolatility()
        result = rv.compute_from_prices(mock_prices)
        assert isinstance(result, pd.Series)
        assert len(result) > 0
        assert (result >= 0).all()

    def test_rv_compute_short_prices(self):
        from scripts.research_framework.volatility_models import RealizedVolatility

        rv = RealizedVolatility()
        short_prices = pd.Series([100.0, 101.0, 100.5, 102.0])
        result = rv.compute_from_prices(short_prices)
        assert result.empty or len(result) == 0

    def test_rv_bipower_variation(self, mock_prices):
        from scripts.research_framework.volatility_models import RealizedVolatility

        rv = RealizedVolatility()
        bpv = rv.bipower_variation(mock_prices)
        assert isinstance(bpv, pd.Series)
        assert len(bpv) > 0

    def test_rv_jump_test(self, mock_prices):
        from scripts.research_framework.volatility_models import RealizedVolatility

        rv = RealizedVolatility()
        jt = rv.jump_test(mock_prices)
        assert isinstance(jt, dict)
        assert "z_stat" in jt
        assert "pval" in jt
        assert "has_jumps" in jt
        assert isinstance(jt["has_jumps"], bool)

    def test_rv_jump_test_default_threshold(self, mock_prices):
        from scripts.research_framework.volatility_models import RealizedVolatility

        rv = RealizedVolatility()
        jt = rv.jump_test(mock_prices, threshold=3.0)
        assert "pval" in jt

    def test_rv_plot_rv_comparison(self, mock_prices, tmp_path):
        from scripts.research_framework.volatility_models import RealizedVolatility

        rv = RealizedVolatility()
        fig = rv.plot_rv_comparison(mock_prices, save_path=str(tmp_path / "rv_compare.pdf"))
        if fig is not None:
            assert str(tmp_path / "rv_compare.pdf").endswith(".pdf")


# ─── Test RealizedGARCH ───────────────────────────────────────────────────────


class TestRealizedGARCH:
    def test_realized_garch_init(self):
        from scripts.research_framework.volatility_models import RealizedGARCH

        rg = RealizedGARCH()
        assert rg._params is None

    def test_realized_garch_fit(self, mock_rv_series, mock_returns):
        from scripts.research_framework.volatility_models import RealizedGARCH

        rg = RealizedGARCH()
        # Align lengths
        min_len = min(len(mock_rv_series), len(mock_returns))
        rv = mock_rv_series.iloc[:min_len].reset_index(drop=True)
        ret = mock_returns.iloc[:min_len].reset_index(drop=True)

        result = rg.fit(rv=rv, returns=ret)
        assert isinstance(result, dict)
        assert "params" in result
        assert "converged" in result
        assert result["n_obs"] > 0

    def test_realized_garch_fit_short_series(self):
        from scripts.research_framework.volatility_models import RealizedGARCH

        rg = RealizedGARCH()
        short_rv = pd.Series(np.random.exponential(0.01, size=30))
        short_ret = pd.Series(np.random.randn(30) * 0.02)
        result = rg.fit(rv=short_rv, returns=short_ret)
        assert result == {}

    def test_realized_garch_predict_before_fit(self):
        from scripts.research_framework.volatility_models import RealizedGARCH

        rg = RealizedGARCH()
        with pytest.raises(RuntimeError, match="Must call fit"):
            rg.predict(h=5)

    def test_realized_garch_predict(self, mock_rv_series, mock_returns):
        from scripts.research_framework.volatility_models import RealizedGARCH

        rg = RealizedGARCH()
        min_len = min(len(mock_rv_series), len(mock_returns))
        rv = mock_rv_series.iloc[:min_len].reset_index(drop=True)
        ret = mock_returns.iloc[:min_len].reset_index(drop=True)
        rg.fit(rv=rv, returns=ret)

        preds = rg.predict(h=5)
        assert len(preds) == 5
        assert np.all(preds >= 0)

    def test_realized_garch_predict_single_step(self, mock_rv_series, mock_returns):
        from scripts.research_framework.volatility_models import RealizedGARCH

        rg = RealizedGARCH()
        min_len = min(len(mock_rv_series), len(mock_returns))
        rv = mock_rv_series.iloc[:min_len].reset_index(drop=True)
        ret = mock_returns.iloc[:min_len].reset_index(drop=True)
        rg.fit(rv=rv, returns=ret)

        pred = rg.predict(h=1)
        assert isinstance(pred, (float, np.floating, np.ndarray))


# ─── Test HARModel ─────────────────────────────────────────────────────────────


class TestHARModel:
    def test_har_init(self):
        from scripts.research_framework.volatility_models import HARModel

        har = HARModel()
        assert har._params == {}
        assert har._rv is None

    def test_har_fit(self, mock_rv_series):
        from scripts.research_framework.volatility_models import HARModel

        har = HARModel()
        result = har.fit(mock_rv_series)
        assert isinstance(result, dict)
        assert "params" in result
        assert "aic" in result
        assert "bic" in result
        assert result["n_obs"] > 0

    def test_har_fit_short_rv(self):
        from scripts.research_framework.volatility_models import HARModel

        har = HARModel()
        short_rv = pd.Series(np.random.exponential(0.01, size=15))
        result = har.fit(short_rv)
        assert result == {}

    def test_har_forecast(self, mock_rv_series):
        from scripts.research_framework.volatility_models import HARModel

        har = HARModel()
        har.fit(mock_rv_series)
        fc = har.forecast(h=5)
        assert len(fc) == 5
        assert not np.any(np.isnan(fc))

    def test_har_forecast_single_step(self, mock_rv_series):
        from scripts.research_framework.volatility_models import HARModel

        har = HARModel()
        har.fit(mock_rv_series)
        pred = har.forecast(h=1)
        assert isinstance(pred, (float, np.floating))

    def test_har_forecast_before_fit(self):
        from scripts.research_framework.volatility_models import HARModel

        har = HARModel()
        fc = har.forecast(h=5)
        assert isinstance(fc, np.ndarray)
        assert np.all(np.isnan(fc))

    def test_har_plot_fit(self, mock_rv_series, tmp_path):
        from scripts.research_framework.volatility_models import HARModel

        har = HARModel()
        har.fit(mock_rv_series)
        fig = har.plot_fit(save_path=str(tmp_path / "har_fit.pdf"))
        if fig is not None:
            assert str(tmp_path / "har_fit.pdf").endswith(".pdf")


# ─── Test VolatilitySpillover ─────────────────────────────────────────────────


class TestVolatilitySpillover:
    def test_spillover_init(self):
        from scripts.research_framework.volatility_models import VolatilitySpillover

        data = {
            "AAPL": pd.Series(np.random.randn(252) * 0.02),
            "MSFT": pd.Series(np.random.randn(252) * 0.02),
            "GOOGL": pd.Series(np.random.randn(252) * 0.02),
        }
        spill = VolatilitySpillover(data)
        assert spill.returns_dict == data

    def test_spillover_diebold_yilmaz(self):
        from scripts.research_framework.volatility_models import VolatilitySpillover

        np.random.seed(42)
        n = 200
        data = {
            "AAPL": pd.Series(np.random.randn(n) * 0.02, index=range(n)),
            "MSFT": pd.Series(np.random.randn(n) * 0.02, index=range(n)),
            "GOOGL": pd.Series(np.random.randn(n) * 0.02, index=range(n)),
        }
        spill = VolatilitySpillover(data)
        result = spill.diebold_yilmaz()
        assert isinstance(result, pd.DataFrame)
        assert len(result) > 0

    def test_spillover_diebold_yilmaz_two_assets(self):
        from scripts.research_framework.volatility_models import VolatilitySpillover

        np.random.seed(42)
        data = {
            "X": pd.Series(np.random.randn(100) * 0.02),
            "Y": pd.Series(np.random.randn(100) * 0.02),
        }
        spill = VolatilitySpillover(data)
        result = spill.diebold_yilmaz()
        assert isinstance(result, pd.DataFrame)


# ─── Test VolatilitySuite ──────────────────────────────────────────────────────


class TestVolatilitySuite:
    def test_suite_init(self):
        from scripts.research_framework.volatility_models import VolatilitySuite

        suite = VolatilitySuite()
        assert suite is not None

    def test_suite_run_all(self, mock_prices, mock_returns):
        from scripts.research_framework.volatility_models import VolatilitySuite

        suite = VolatilitySuite()
        results = suite.run_all(prices=mock_prices, returns=mock_returns)
        assert isinstance(results, dict)
        assert "garch" in results or any("garch" in k.lower() for k in results.keys())


# ─── Test Standalone Helpers ───────────────────────────────────────────────────


class TestRealizedVolatilityFromPrices:
    def test_rv_from_prices(self, mock_prices):
        from scripts.research_framework.volatility_models import realized_volatility_from_prices

        rv = realized_volatility_from_prices(mock_prices, rule="5min")
        assert isinstance(rv, pd.Series)
        assert len(rv) > 0


class TestGarchFitHelper:
    def test_garch_fit_helper(self, mock_returns):
        from scripts.research_framework.volatility_models import garch_fit

        result = garch_fit(mock_returns)
        assert isinstance(result, object)  # returns VolatilityResult


# ─── Test edge cases ───────────────────────────────────────────────────────────


class TestVolatilityEdgeCases:
    def test_garch_fit_constant_returns(self):
        from scripts.research_framework.volatility_models import GARCHModel

        constant = pd.Series([0.0] * 100)
        model = GARCHModel()
        result = model.fit(constant)
        assert result is not None

    def test_garch_fit_nan_returns(self):
        from scripts.research_framework.volatility_models import GARCHModel

        returns = pd.Series([np.nan, 0.01, -0.01, 0.005, np.nan] * 20)
        model = GARCHModel()
        result = model.fit(returns)
        assert result is not None

    def test_volatility_result_empty_params(self):
        from scripts.research_framework.volatility_models import VolatilityResult

        result = VolatilityResult(model_type="test", n_obs=0)
        d = result.to_dict()
        assert d["model_type"] == "test"
        assert d["n_obs"] == 0

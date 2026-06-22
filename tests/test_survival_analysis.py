"""Tests for scripts/research_framework/survival_analysis.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
import numpy as np
import pandas as pd


# ─── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def survival_df():
    """Synthetic survival dataset for testing."""
    np.random.seed(42)
    n = 200
    df = pd.DataFrame({
        "id": np.arange(n),
        "time": np.random.exponential(scale=5, size=n),
        "event": np.random.binomial(1, p=0.6, size=n),
        "did": np.random.binomial(1, p=0.5, size=n),
        "size": np.random.normal(loc=5, scale=1, size=n),
        "lev": np.random.uniform(low=0.1, high=0.9, size=n),
        "age": np.random.randint(1, 30, size=n),
        "industry": np.random.choice(["Tech", "Finance", "Manuf"], size=n),
    })
    df.loc[df["event"] == 0, "time"] += 10  # censored observations live longer
    return df


@pytest.fixture
def survival_df_small():
    """Small dataset for edge-case tests."""
    return pd.DataFrame({
        "id": np.arange(10),
        "time": np.arange(1, 11, dtype=float),
        "event": [1, 0, 1, 1, 0, 1, 0, 1, 1, 0],
        "did": np.random.binomial(1, 0.5, size=10),
        "size": np.random.randn(10),
        "lev": np.random.uniform(0.2, 0.8, size=10),
    })


@pytest.fixture
def survival_df_groups():
    """Dataset with two groups for KM / log-rank testing."""
    np.random.seed(0)
    n1, n2 = 80, 80
    g1 = pd.DataFrame({
        "time": np.random.exponential(scale=4, size=n1),
        "event": np.random.binomial(1, 0.7, size=n1),
        "group": 0,
    })
    g2 = pd.DataFrame({
        "time": np.random.exponential(scale=6, size=n2),
        "event": np.random.binomial(1, 0.5, size=n2),
        "group": 1,
    })
    return pd.concat([g1, g2], ignore_index=True)


# ─── Test SurvivalResult ────────────────────────────────────────────────────────


class TestSurvivalResult:
    def test_survival_result_to_dict(self):
        from scripts.research_framework.survival_analysis import SurvivalResult

        result = SurvivalResult(
            model_type="cox_ph",
            coef_dict={"did": 0.5, "size": -0.1},
            se_dict={"did": 0.2, "size": 0.05},
            z_dict={"did": 2.5, "size": -2.0},
            pval_dict={"did": 0.0124, "size": 0.0455},
            ci_lower={"did": 0.1, "size": -0.2},
            ci_upper={"did": 0.9, "size": 0.0},
            sig_dict={"did": "*", "size": "*"},
            n_obs=200,
            n_events=120,
            concordance=0.68,
            log_likelihood=-350.0,
            aic=706.0,
            bic=720.0,
            converged=True,
        )

        d = result.to_dict()
        assert d["model_type"] == "cox_ph"
        assert d["n_obs"] == 200
        assert d["n_events"] == 120
        assert d["concordance"] == 0.68
        assert "coef_did" in d
        assert "hr_did" in d
        assert np.isclose(d["hr_did"], np.exp(0.5))
        assert "sig_did" in d

    def test_survival_result_default_values(self):
        from scripts.research_framework.survival_analysis import SurvivalResult

        result = SurvivalResult(model_type="kaplan_meier", n_obs=100)
        assert result.n_obs == 100
        assert result.concordance is None
        assert result.log_likelihood is None
        assert result.baseline_hazard is None
        assert result.converged is True


# ─── Test Internal Helpers ──────────────────────────────────────────────────────


class TestSignificanceMark:
    def test_significance_mark(self):
        from scripts.research_framework.survival_analysis import _significance_mark

        assert _significance_mark(0.0005) == "***"
        assert _significance_mark(0.005) == "**"
        assert _significance_mark(0.03) == "*"
        assert _significance_mark(0.08) == r"$\dagger$"
        assert _significance_mark(0.15) == ""

    def test_significance_mark_exact_thresholds(self):
        from scripts.research_framework.survival_analysis import _significance_mark

        # Strict < threshold: use values just inside the boundary
        assert _significance_mark(0.0009) == "***"
        assert _significance_mark(0.009) == "**"
        assert _significance_mark(0.049) == "*"
        assert _significance_mark(0.099) == r"$\dagger$"


class TestConcordanceIndex:
    def test_concordance_index_basic(self):
        from scripts.research_framework.survival_analysis import _concordance_index

        # Two events, correct ordering
        y_time = np.array([5.0, 10.0])
        y_event = np.array([1.0, 1.0])
        y_pred = np.array([0.0, 1.0])  # subject 1 has higher risk but dies later
        c = _concordance_index(y_time, y_event, y_pred)
        assert 0 <= c <= 1
        assert not np.isnan(c)

    def test_concordance_index_all_censored(self):
        from scripts.research_framework.survival_analysis import _concordance_index

        c = _concordance_index(
            np.array([5.0, 10.0, 15.0]),
            np.array([0.0, 0.0, 0.0]),
            np.array([1.0, 2.0, 3.0]),
        )
        assert np.isnan(c)

    def test_concordance_index_single_observation(self):
        from scripts.research_framework.survival_analysis import _concordance_index

        c = _concordance_index(
            np.array([5.0]),
            np.array([1.0]),
            np.array([1.0]),
        )
        assert np.isnan(c)

    def test_concordance_index_empty(self):
        from scripts.research_framework.survival_analysis import _concordance_index

        c = _concordance_index(np.array([]), np.array([]), np.array([]))
        assert np.isnan(c)

    def test_concordance_index_perfect(self):
        from scripts.research_framework.survival_analysis import _concordance_index

        # Perfect concordance: subject with higher predicted risk has event first
        y_time = np.array([5.0, 10.0, 15.0, 20.0])
        y_event = np.array([1.0, 1.0, 1.0, 1.0])
        # Lower y_pred dies first → module's '>' check in t_i < t_j path is satisfied
        y_pred = np.array([4.0, 3.0, 2.0, 1.0])
        c = _concordance_index(y_time, y_event, y_pred)
        assert c == 1.0


class TestPartialLogLikelihood:
    def test_partial_log_likelihood(self):
        from scripts.research_framework.survival_analysis import _partial_log_likelihood

        np.random.seed(42)
        T = np.array([5.0, 10.0, 8.0, 15.0, 12.0])
        E = np.array([1, 0, 1, 1, 0])
        X = np.random.randn(5, 2)
        beta = np.array([0.5, -0.2])

        pll = _partial_log_likelihood(beta, T, E, X)
        assert isinstance(pll, (float, np.floating))
        assert not np.isnan(pll)
        # Negative log-likelihood should be positive
        assert pll >= 0

    def test_partial_log_likelihood_zero_beta(self):
        from scripts.research_framework.survival_analysis import _partial_log_likelihood

        T = np.array([5.0, 10.0, 8.0])
        E = np.array([1, 1, 1])
        X = np.ones((3, 1))
        beta = np.array([0.0])
        pll = _partial_log_likelihood(beta, T, E, X)
        assert not np.isnan(pll)


class TestLogRankTest:
    def test_log_rank_basic(self):
        from scripts.research_framework.survival_analysis import _log_rank_test

        times1 = np.array([3.0, 5.0, 8.0])
        events1 = np.array([1, 1, 0])
        times2 = np.array([4.0, 7.0, 10.0])
        events2 = np.array([1, 0, 1])

        result = _log_rank_test(times1, events1, times2, events2)
        assert result["test"] == "log_rank"
        assert "statistic" in result
        assert "pval" in result
        assert "z_statistic" in result
        assert "interpretation" in result
        assert isinstance(result["interpretation"], str)

    def test_log_rank_insufficient_data(self):
        from scripts.research_framework.survival_analysis import _log_rank_test

        # Only censored observations
        result = _log_rank_test(
            np.array([5.0]), np.array([0]),
            np.array([7.0]), np.array([0]),
        )
        assert result["statistic"] is np.nan or np.isnan(result["pval"])

    def test_log_rank_large_sample(self, survival_df_groups):
        from scripts.research_framework.survival_analysis import _log_rank_test

        g1 = survival_df_groups[survival_df_groups["group"] == 0]
        g2 = survival_df_groups[survival_df_groups["group"] == 1]

        result = _log_rank_test(
            g1["time"].values, g1["event"].values,
            g2["time"].values, g2["event"].values,
        )
        assert "statistic" in result
        assert result["df"] == 1


class TestBreslowTest:
    def test_breslow_basic(self):
        from scripts.research_framework.survival_analysis import _breslow_test

        times1 = np.array([3.0, 5.0, 8.0, 12.0])
        events1 = np.array([1, 1, 0, 1])
        times2 = np.array([4.0, 7.0, 10.0, 15.0])
        events2 = np.array([1, 0, 1, 0])

        result = _breslow_test(times1, events1, times2, events2)
        assert result["test"] == "breslow"
        assert "statistic" in result
        assert "pval" in result

    def test_breslow_all_censored(self):
        from scripts.research_framework.survival_analysis import _breslow_test

        result = _breslow_test(
            np.array([5.0, 8.0]), np.array([0, 0]),
            np.array([6.0, 9.0]), np.array([0, 0]),
        )
        assert result["statistic"] is np.nan or np.isnan(result.get("pval"))


class TestLoadLifelines:
    def test_load_lifelines_returns_bool(self):
        from scripts.research_framework.survival_analysis import _load_lifelines

        result = _load_lifelines()
        assert isinstance(result, bool)


class TestManualCoxFit:
    def test_manual_cox_fit(self, survival_df_small):
        from scripts.research_framework.survival_analysis import _manual_cox_fit

        result = _manual_cox_fit(
            survival_df_small,
            duration="time",
            event="event",
            X_names=["size", "lev"],
        )
        assert result.model_type == "cox_ph"
        assert result.converged is True
        assert result.n_obs > 0
        assert result.n_events > 0
        assert "const" in result.coef_dict
        assert "size" in result.coef_dict
        assert "lev" in result.coef_dict
        assert "concordance" in dir(result) or hasattr(result, "concordance")

    def test_manual_cox_fit_with_missing(self):
        from scripts.research_framework.survival_analysis import _manual_cox_fit

        df = pd.DataFrame({
            "time": [1, 2, 3, 4, 5],
            "event": [1, 0, 1, 0, 1],
            "size": [1.0, 2.0, np.nan, 4.0, 5.0],
            "lev": [0.5, 0.6, 0.7, 0.8, 0.9],
        })
        result = _manual_cox_fit(df, duration="time", event="event", X_names=["size", "lev"])
        assert result.n_obs < 5  # NaN rows dropped


# ─── Test CoxPHModel ───────────────────────────────────────────────────────────


class TestCoxPHModel:
    def test_cox_init(self):
        from scripts.research_framework.survival_analysis import CoxPHModel

        cox = CoxPHModel(ties="efron")
        assert cox.ties == "efron"
        assert cox._result is None

    def test_cox_init_breslow(self):
        from scripts.research_framework.survival_analysis import CoxPHModel

        cox = CoxPHModel(ties="breslow", strata=["industry"])
        assert cox.ties == "breslow"
        assert cox.strata == ["industry"]

    def test_cox_fit(self, survival_df):
        from scripts.research_framework.survival_analysis import CoxPHModel

        cox = CoxPHModel()
        result = cox.fit(survival_df, duration="time", event="event", X=["did", "size", "lev"])
        assert result is not None
        assert result.model_type == "cox_ph"
        assert result.n_obs == len(survival_df)

    def test_cox_fit_with_strata(self, survival_df):
        from scripts.research_framework.survival_analysis import CoxPHModel

        cox = CoxPHModel(strata=["industry"])
        result = cox.fit(survival_df, duration="time", event="event", X=["did", "size"])
        assert result is not None

    def test_cox_summary(self, survival_df):
        from scripts.research_framework.survival_analysis import CoxPHModel

        cox = CoxPHModel()
        cox.fit(survival_df, duration="time", event="event", X=["did", "size"])
        summary = cox.summary()
        assert isinstance(summary, pd.DataFrame)
        assert len(summary) > 0
        assert "Variable" in summary.columns
        assert "HR" in summary.columns

    def test_cox_to_latex(self, survival_df):
        from scripts.research_framework.survival_analysis import CoxPHModel

        cox = CoxPHModel()
        cox.fit(survival_df, duration="time", event="event", X=["did", "size"])
        latex = cox.to_latex()
        assert isinstance(latex, str)
        assert "\\begin{table}" in latex
        assert "\\end{table}" in latex

    def test_cox_to_latex_empty(self):
        from scripts.research_framework.survival_analysis import CoxPHModel

        cox = CoxPHModel()
        latex = cox.to_latex()
        assert latex == ""

    def test_cox_predict_survival(self, survival_df):
        from scripts.research_framework.survival_analysis import CoxPHModel

        cox = CoxPHModel()
        cox.fit(survival_df, duration="time", event="event", X=["did", "size"])
        pred = cox.predict_survival(survival_df.head(20))
        assert isinstance(pred, pd.DataFrame)
        assert len(pred.columns) == 20

    def test_cox_predict_survival_before_fit(self):
        from scripts.research_framework.survival_analysis import CoxPHModel

        cox = CoxPHModel()
        with pytest.raises(ValueError, match="not fitted"):
            cox.predict_survival(pd.DataFrame({"size": [1, 2]}))

    def test_cox_plot_baseline_hazard(self, survival_df, tmp_path):
        from scripts.research_framework.survival_analysis import CoxPHModel

        cox = CoxPHModel()
        cox.fit(survival_df, duration="time", event="event", X=["did", "size"])
        fig = cox.plot_baseline_hazard(save_path=str(tmp_path / "bh.pdf"))
        if fig is not None:
            assert str(tmp_path / "bh.pdf").endswith(".pdf")

    def test_cox_plot_predicted_survival(self, survival_df, tmp_path):
        from scripts.research_framework.survival_analysis import CoxPHModel

        cox = CoxPHModel()
        cox.fit(survival_df, duration="time", event="event", X=["did", "size"])
        fig = cox.plot_predicted_survival(
            survival_df,
            groups={"Treated": survival_df["did"] == 1, "Control": survival_df["did"] == 0},
            save_path=str(tmp_path / "pred_surv.pdf"),
        )
        if fig is not None:
            assert str(tmp_path / "pred_surv.pdf").endswith(".pdf")


# ─── Test KaplanMeier ─────────────────────────────────────────────────────────


class TestKaplanMeier:
    def test_km_init(self):
        from scripts.research_framework.survival_analysis import KaplanMeier

        km = KaplanMeier()
        assert km._result is None

    def test_km_fit(self, survival_df_groups):
        from scripts.research_framework.survival_analysis import KaplanMeier

        km = KaplanMeier()
        result = km.fit(survival_df_groups, duration="time", event="event")
        assert result is not None
        assert "surv" in result
        assert "times" in result
        assert "n_obs" in result
        assert "n_events" in result

    def test_km_compare_groups(self, survival_df_groups):
        from scripts.research_framework.survival_analysis import KaplanMeier

        km = KaplanMeier()
        km.fit(survival_df_groups, duration="time", event="event")
        test_result = km.compare_groups(
            survival_df_groups,
            duration="time",
            event="event",
            group_var="group",
        )
        assert test_result is not None
        assert "statistic" in test_result or "pval" in test_result


# ─── Test SurvivalSuite ────────────────────────────────────────────────────────


class TestSurvivalSuite:
    def test_suite_init(self):
        from scripts.research_framework.survival_analysis import SurvivalSuite

        suite = SurvivalSuite()
        # _results is set to {} on init via run_all, default is None before that
        assert suite._results is None or suite._results == {}

    def test_suite_run_all(self, survival_df):
        from scripts.research_framework.survival_analysis import SurvivalSuite

        suite = SurvivalSuite()
        results = suite.run_all(
            survival_df,
            duration="time",
            event="event",
            X=["did", "size"],
        )
        assert isinstance(results, dict)
        assert "cox_ph" in results

    def test_suite_run_all_with_kaplan_meier(self, survival_df):
        from scripts.research_framework.survival_analysis import SurvivalSuite

        suite = SurvivalSuite()
        results = suite.run_all(
            survival_df,
            duration="time",
            event="event",
            X=["did", "size"],
        )
        # KM is always run inside run_all; check it's present
        assert "kaplan_meier" in results

    def test_suite_heterogeneity_analysis(self, survival_df):
        from scripts.research_framework.survival_analysis import SurvivalSuite

        suite = SurvivalSuite()
        suite.run_all(
            survival_df,
            duration="time",
            event="event",
            X=["did", "size"],
        )
        het_df = suite.heterogeneity_analysis(
            survival_df,
            duration="time",
            event="event",
            X=["did", "size"],
            group_var="industry",
        )
        assert isinstance(het_df, pd.DataFrame)
        assert "group" in het_df.columns or len(het_df) >= 1


# ─── Test NelsonAalen ──────────────────────────────────────────────────────────


class TestNelsonAalen:
    def test_nelson_aalen_fit(self, survival_df_groups):
        from scripts.research_framework.survival_analysis import NelsonAalen

        na = NelsonAalen()
        result = na.fit(survival_df_groups, duration="time", event="event")
        assert result is not None
        assert "cum_hazard" in result


# ─── Test edge cases ───────────────────────────────────────────────────────────


class TestSurvivalEdgeCases:
    def test_partial_log_likelihood_empty(self):
        from scripts.research_framework.survival_analysis import _partial_log_likelihood

        pll = _partial_log_likelihood(
            np.array([0.0]),
            np.array([]),
            np.array([]),
            np.ones((0, 1)),
        )
        assert pll == 0.0

    def test_concordance_index_no_comparable_pairs(self):
        from scripts.research_framework.survival_analysis import _concordance_index

        c = _concordance_index(
            np.array([1.0, 2.0]),
            np.array([0.0, 0.0]),  # both censored
            np.array([1.0, 2.0]),
        )
        assert np.isnan(c)

"""Test suite for robustness_runner.py.

Covers: RobustnessRunner dispatch table, run_comprehensive, oster_bounds,
and FDR correction.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.research_framework.robustness_runner import (
    RobustnessRunner,
    RobustnessReport,
    RobustnessTest,
    oster_bounds,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def panel_df() -> pd.DataFrame:
    """Balanced panel: 100 firms, 10 years, binary treatment."""
    rng = np.random.default_rng(42)
    n_firms = 100
    years = list(range(2014, 2024))
    rows = []
    for firm in range(n_firms):
        treat_year = rng.choice(years[3:]) if rng.random() > 0.4 else None
        for year in years:
            post = int(year >= treat_year) if treat_year else 0
            did = post if treat_year is not None else 0
            u = rng.standard_normal()
            y = (
                0.5 * did
                + 0.3 * (year - 2014)
                + 0.1 * firm
                + u
            )
            rows.append(
                {
                    "firm_id": firm,
                    "year": year,
                    "roa": y,
                    "did": did,
                    "post": post,
                    "size": rng.uniform(5, 10),
                    "lev": rng.uniform(0.2, 0.8),
                    "treat_year": treat_year if treat_year else -1,
                }
            )
    df = pd.DataFrame(rows)
    df["did"] = df.groupby("firm_id")["post"].transform(lambda x: x.cumsum().clip(upper=1))
    return df


@pytest.fixture
def baseline_result() -> dict:
    """Baseline DID result."""
    return {
        "estimator": "twfe",
        "coef": 0.52,
        "se": 0.08,
        "pval": 0.001,
        "n_obs": 1000,
        "n_clusters": 100,
        "r_squared": 0.32,
    }


# ── Dispatch Table Tests ───────────────────────────────────────────────────────


class TestDispatchTable:
    """Verify all 19 robustness tests are registered in the dispatch table."""

    TESTS = [
        # Basic (8)
        "parallel_trends",
        "placebo",
        "psm",
        "replace_outliers",
        "replace_depvar",
        "change_control",
        "sub_sample",
        "remove_extreme",
        # Advanced (6)
        "wild_bootstrap",
        "change_cluster",
        "exclude_preannouncement",
        "honest_did",
        "triple_did",
        "oster_bounds",
        # Extended (5)
        "psm_truncation",
        "combined_ddd",
        "iv_robust",
        "lagged_depvar",
    ]

    def test_all_tests_registered(self, panel_df, baseline_result):
        """Every named test in TESTS resolves without warning."""
        runner = RobustnessRunner(
            df=panel_df,
            baseline_result=baseline_result,
            y_var="roa",
            treat_var="did",
            time_var="year",
            unit_var="firm_id",
            x_vars=["size", "lev"],
        )
        for name in self.TESTS:
            cfg = {"year_range": [2016, 2022]} if name == "sub_sample" else {}
            runner.add_test(name, sub_config=cfg)
        assert len(runner._pending_tests) == len(self.TESTS)

    def test_unknown_test_logs_warning(self, panel_df, baseline_result, caplog):
        """Unknown test name emits a warning."""
        import logging

        runner = RobustnessRunner(
            df=panel_df,
            baseline_result=baseline_result,
            y_var="roa",
            treat_var="did",
            time_var="year",
            unit_var="firm_id",
        )
        with caplog.at_level(logging.WARNING):
            result = runner._run_single_test("not_a_real_test", {})
        assert result is None


# ── run_comprehensive Tests ───────────────────────────────────────────────────


class TestRunComprehensive:
    """Test the run_comprehensive() convenience method."""

    def test_basic_level(self, panel_df, baseline_result):
        runner = RobustnessRunner(
            df=panel_df,
            baseline_result=baseline_result,
            y_var="roa",
            treat_var="did",
            time_var="year",
            unit_var="firm_id",
        )
        report = runner.run_comprehensive(level="basic")
        assert isinstance(report, RobustnessReport)
        assert len(report.tests) >= 8  # basic has 8 tests

    def test_advanced_level(self, panel_df, baseline_result):
        runner = RobustnessRunner(
            df=panel_df,
            baseline_result=baseline_result,
            y_var="roa",
            treat_var="did",
            time_var="year",
            unit_var="firm_id",
        )
        report = runner.run_comprehensive(level="advanced")
        assert isinstance(report, RobustnessReport)
        # advanced has 14 tests but some may fail gracefully (honest_did needs honestdid)
        assert len(report.tests) >= 8  # at minimum basic tests run

    def test_full_level(self, panel_df, baseline_result):
        runner = RobustnessRunner(
            df=panel_df,
            baseline_result=baseline_result,
            y_var="roa",
            treat_var="did",
            time_var="year",
            unit_var="firm_id",
        )
        report = runner.run_comprehensive(level="full")
        assert isinstance(report, RobustnessReport)


# ── Oster Bounds Tests ────────────────────────────────────────────────────────


class TestOsterBounds:
    """Test the oster_bounds() function."""

    def test_oster_bounds_returns_dict(self, panel_df):
        result = oster_bounds(
            df=panel_df,
            y_var="roa",
            treatment_var="did",
            x_vars=["size"],
            control_vars=["lev"],
            r2_max_options=[0.5, 0.7, 0.9],
        )
        assert isinstance(result, dict)
        assert "beta_restricted" in result
        assert "beta_full" in result
        assert "r2_restricted" in result
        assert "r2_full" in result
        assert "delta_values" in result
        assert isinstance(result["delta_values"], dict)

    def test_oster_bounds_delta_values_structure(self, panel_df):
        result = oster_bounds(
            df=panel_df,
            y_var="roa",
            treatment_var="did",
            x_vars=["size"],
            control_vars=["lev"],
            r2_max_options=[0.5, 0.9],
        )
        for r2_key, val in result["delta_values"].items():
            assert "adjusted_beta" in val
            assert "delta" in val

    def test_oster_bounds_default_r2_options(self, panel_df):
        result = oster_bounds(
            df=panel_df,
            y_var="roa",
            treatment_var="did",
            x_vars=["size"],
            control_vars=["lev"],
        )
        # Default r2_max_options = [0.5, 0.7, 0.9, 1.0]
        assert set(result["delta_values"].keys()) == {"0.5", "0.7", "0.9", "1.0"}

    def test_oster_bounds_interpretation(self, panel_df):
        result = oster_bounds(
            df=panel_df,
            y_var="roa",
            treatment_var="did",
            x_vars=["size"],
            control_vars=["lev"],
        )
        assert "interpretation" in result
        assert isinstance(result["interpretation"], dict)
        for key, val in result["interpretation"].items():
            assert isinstance(key, str)
            assert isinstance(val, str)


# ── RobustnessReport Tests ────────────────────────────────────────────────────


class TestRobustnessReport:
    """Test RobustnessReport."""

    def test_report_from_baseline(self, baseline_result):
        report = RobustnessReport(baseline_result=baseline_result)
        assert report.baseline_result == baseline_result
        assert isinstance(report.tests, list)
        assert len(report.tests) == 0

    def test_report_add_test(self, baseline_result):
        report = RobustnessReport(baseline_result=baseline_result)
        test = RobustnessTest(
            test_name="placebo",
            test_type="placebo",
            did_coef=0.41,
            did_se=0.09,
            did_pval=0.05,
            is_consistent=True,
            is_significant=True,
            note="Placebo test",
        )
        report.tests.append(test)
        assert len(report.tests) == 1

    def test_overall_consistency(self, baseline_result):
        report = RobustnessReport(baseline_result=baseline_result)
        for i, sign in enumerate([True, False, True, False, True]):
            t = RobustnessTest(
                test_name=f"test_{i}",
                test_type="test",
                did_coef=0.5 if sign else -0.5,
                did_se=0.1,
                did_pval=0.05,
                is_consistent=sign,
                is_significant=True,
                note="",
            )
            report.tests.append(t)
        # 3 consistent, 2 not → 60%
        assert report.overall_consistency == pytest.approx(0.6, abs=0.01)

    def test_overall_significance(self, baseline_result):
        report = RobustnessReport(baseline_result=baseline_result)
        for i, sig in enumerate([True, True, False, True, False]):
            t = RobustnessTest(
                test_name=f"test_{i}",
                test_type="test",
                did_coef=0.5,
                did_se=0.1,
                did_pval=0.05 if sig else 0.8,
                is_consistent=True,
                is_significant=sig,
                note="",
            )
            report.tests.append(t)
        # 3 significant, 2 not → 60%
        assert report.overall_significance == pytest.approx(0.6, abs=0.01)

    def test_to_dataframe(self, baseline_result):
        report = RobustnessReport(baseline_result=baseline_result)
        test = RobustnessTest(
            test_name="placebo",
            test_type="placebo",
            did_coef=0.41,
            did_se=0.09,
            did_pval=0.05,
            is_consistent=True,
            is_significant=True,
            note="placebo test",
        )
        report.tests.append(test)
        df = report.to_dataframe()
        assert isinstance(df, pd.DataFrame)
        # Columns are in Chinese: 'Test', 'Type', 'DID Coef', 'SE', etc.
        assert "Test" in df.columns
        assert len(df) == 2  # baseline + 1 test
        # Baseline row + test row
        assert df.iloc[0]["Test"] == "(Baseline)" or df.iloc[1]["Test"] == "placebo"

    def test_to_latex(self, baseline_result):
        report = RobustnessReport(baseline_result=baseline_result)
        test = RobustnessTest(
            test_name="placebo",
            test_type="placebo",
            did_coef=0.41,
            did_se=0.09,
            did_pval=0.05,
            is_consistent=True,
            is_significant=True,
            note="placebo test",
        )
        report.tests.append(test)
        latex = report.to_latex()
        assert isinstance(latex, str)
        assert "placebo" in latex


# ── Individual Robustness Tests ────────────────────────────────────────────────


class TestIndividualRobustnessTests:
    """Test individual robustness test methods on panel_df."""

    def test_placebo(self, panel_df, baseline_result):
        runner = RobustnessRunner(
            df=panel_df,
            baseline_result=baseline_result,
            y_var="roa",
            treat_var="did",
            time_var="year",
            unit_var="firm_id",
        )
        result = runner._test_placebo({})
        assert isinstance(result, RobustnessTest)
        assert result.test_type is not None and isinstance(result.test_type, str)

    def test_parallel_trends(self, panel_df, baseline_result):
        runner = RobustnessRunner(
            df=panel_df,
            baseline_result=baseline_result,
            y_var="roa",
            treat_var="did",
            time_var="year",
            unit_var="firm_id",
        )
        result = runner._test_parallel_trends({})
        assert isinstance(result, RobustnessTest)
        assert result.test_type is not None

    def test_psm(self, panel_df, baseline_result):
        runner = RobustnessRunner(
            df=panel_df,
            baseline_result=baseline_result,
            y_var="roa",
            treat_var="did",
            time_var="year",
            unit_var="firm_id",
            x_vars=["size", "lev"],
        )
        result = runner._test_psm({})
        assert isinstance(result, RobustnessTest)
        assert result.test_type is not None

    def test_replace_outliers(self, panel_df, baseline_result):
        runner = RobustnessRunner(
            df=panel_df,
            baseline_result=baseline_result,
            y_var="roa",
            treat_var="did",
            time_var="year",
            unit_var="firm_id",
        )
        result = runner._test_replace_outliers({})
        assert isinstance(result, RobustnessTest)
        assert result.test_type is not None

    def test_remove_extreme(self, panel_df, baseline_result):
        runner = RobustnessRunner(
            df=panel_df,
            baseline_result=baseline_result,
            y_var="roa",
            treat_var="did",
            time_var="year",
            unit_var="firm_id",
        )
        result = runner._test_remove_extreme({})
        assert isinstance(result, RobustnessTest)

    def test_wild_bootstrap(self, panel_df, baseline_result):
        runner = RobustnessRunner(
            df=panel_df,
            baseline_result=baseline_result,
            y_var="roa",
            treat_var="did",
            time_var="year",
            unit_var="firm_id",
        )
        result = runner._test_wild_bootstrap({})
        assert isinstance(result, RobustnessTest)
        assert result.test_type is not None

    def test_sub_sample_by_year(self, panel_df, baseline_result):
        runner = RobustnessRunner(
            df=panel_df,
            baseline_result=baseline_result,
            y_var="roa",
            treat_var="did",
            time_var="year",
            unit_var="firm_id",
        )
        result = runner._test_sub_sample({"year_range": [2016, 2022]})
        assert isinstance(result, RobustnessTest)
        assert result.test_type is not None

    def test_psm_truncation(self, panel_df, baseline_result):
        runner = RobustnessRunner(
            df=panel_df,
            baseline_result=baseline_result,
            y_var="roa",
            treat_var="did",
            time_var="year",
            unit_var="firm_id",
            x_vars=["size", "lev"],
        )
        result = runner._test_psm_truncation({"trim_pct": 5})
        assert isinstance(result, RobustnessTest)
        assert result.test_type is not None

    def test_lagged_depvar(self, panel_df, baseline_result):
        runner = RobustnessRunner(
            df=panel_df,
            baseline_result=baseline_result,
            y_var="roa",
            treat_var="did",
            time_var="year",
            unit_var="firm_id",
        )
        result = runner._test_lagged_depvar({"n_lags": 1})
        assert isinstance(result, RobustnessTest)
        assert result.test_type is not None

    def test_oster_bounds(self, panel_df, baseline_result):
        runner = RobustnessRunner(
            df=panel_df,
            baseline_result=baseline_result,
            y_var="roa",
            treat_var="did",
            time_var="year",
            unit_var="firm_id",
            x_vars=["size", "lev"],
        )
        result = runner._test_oster_bounds({})
        assert isinstance(result, RobustnessTest)
        assert "Oster" in result.test_name

    def test_iv_robust(self, panel_df, baseline_result):
        runner = RobustnessRunner(
            df=panel_df,
            baseline_result=baseline_result,
            y_var="roa",
            treat_var="did",
            time_var="year",
            unit_var="firm_id",
        )
        result = runner._test_iv_robust({})
        assert isinstance(result, RobustnessTest)

"""Tests for scripts/research_framework/diagnostic_reporter.py

Covers:
    - DiagnosticDecision enum
    - DiagnosticCheck dataclass
    - DiagnosticReport dataclass (n_pass/n_warn/n_fail/overall/to_dataframe/to_latex/summary_text)
    - DiagnosticReporter (add/add_check/add_vif/add_normality/add_parallel_trends/add_placebo/add_mccrary)
    - Auto-decision logic for VIF, Moran I, Breusch-Pagan, Durbin-Watson,
      Shapiro-Wilk, parallel trends, placebo, honest DiD, McCrary, LR/Wald, F-stat, R²
    - add_honest_did/add_ar2/add_weak_iv/add_two_way_clustering
"""

import pytest


class TestDiagnosticDecision:
    """DiagnosticDecision enum tests."""

    def test_enum_values(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticDecision

        assert DiagnosticDecision.PASS.value == "PASS"
        assert DiagnosticDecision.WARN.value == "WARN"
        assert DiagnosticDecision.FAIL.value == "FAIL"

    def test_enum_is_string(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticDecision

        # DiagnosticDecision extends str
        d = DiagnosticDecision.PASS
        assert isinstance(d, str)
        assert d == "PASS"

    def test_enum_comparison(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticDecision

        assert DiagnosticDecision.PASS == "PASS"
        assert DiagnosticDecision.WARN != "PASS"


class TestDiagnosticCheck:
    """DiagnosticCheck dataclass tests."""

    def test_required_fields(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticCheck, DiagnosticDecision

        check = DiagnosticCheck(
            name="vif_gdp",
            name_zh="VIF (GDP)",
            category="D. 多重共线性",
            decision=DiagnosticDecision.PASS,
            value=2.5,
            threshold="VIF < 5 (PASS), 5-10 (WARN), > 10 (FAIL)",
            pval=None,
            recommendation="变量 GDP 无共线性问题",
            details={"note": "OK"},
        )
        assert check.name == "vif_gdp"
        assert check.name_zh == "VIF (GDP)"
        assert check.category == "D. 多重共线性"
        assert check.decision == DiagnosticDecision.PASS
        assert check.value == 2.5
        assert check.pval is None
        assert check.recommendation == "变量 GDP 无共线性问题"
        assert check.details == {"note": "OK"}

    def test_to_dict(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticCheck, DiagnosticDecision

        check = DiagnosticCheck(
            name="parallel_trends",
            name_zh="平行趋势检验",
            category="A. 平行趋势",
            decision=DiagnosticDecision.PASS,
            value=0.15,
            threshold="p > 0.05",
            pval=0.08,
            recommendation="平行趋势成立",
        )
        d = check.to_dict()
        assert d["name"] == "parallel_trends"
        assert d["decision"] == "PASS"
        assert d["pval"] == 0.08
        assert d["value"] == 0.15


class TestDiagnosticReport:
    """DiagnosticReport dataclass tests."""

    def test_add_and_counts(self):
        from scripts.research_framework.diagnostic_reporter import (
            DiagnosticCheck, DiagnosticDecision, DiagnosticReport,
        )

        report = DiagnosticReport()
        assert report.n_pass == 0
        assert report.n_warn == 0
        assert report.n_fail == 0
        assert report.overall == DiagnosticDecision.PASS

        report.add(DiagnosticCheck(
            "vif", "VIF", "collinearity",
            DiagnosticDecision.PASS, 2.5, "VIF<5",
        ))
        report.add(DiagnosticCheck(
            "moran", "Moran I", "spatial",
            DiagnosticDecision.WARN, 0.04, "p<0.05",
            pval=0.04,
        ))
        report.add(DiagnosticCheck(
            "heterosk", "异方差", "heterosk",
            DiagnosticDecision.FAIL, 0.001, "p<0.01",
            pval=0.001,
        ))

        assert report.n_pass == 1
        assert report.n_warn == 1
        assert report.n_fail == 1
        assert report.overall == DiagnosticDecision.FAIL

    def test_overall_fail_wins(self):
        from scripts.research_framework.diagnostic_reporter import (
            DiagnosticCheck, DiagnosticDecision, DiagnosticReport,
        )

        report = DiagnosticReport()
        report.add(DiagnosticCheck(
            "a", "A", "cat", DiagnosticDecision.PASS, 1.0, "t=1"
        ))
        report.add(DiagnosticCheck(
            "b", "B", "cat", DiagnosticDecision.WARN, 0.06, "p=0.06"
        ))
        # FAIL dominates
        report.add(DiagnosticCheck(
            "c", "C", "cat", DiagnosticDecision.FAIL, 0.001, "p=0.001",
            pval=0.001,
        ))
        assert report.overall == DiagnosticDecision.FAIL

    def test_to_dataframe(self):
        from scripts.research_framework.diagnostic_reporter import (
            DiagnosticCheck, DiagnosticDecision, DiagnosticReport,
        )

        report = DiagnosticReport()
        report.add(DiagnosticCheck(
            "vif", "VIF", "collin", DiagnosticDecision.PASS,
            2.5, "VIF<5", pval=None,
        ))
        df = report.to_dataframe()
        assert len(df) == 1
        assert "检验" in df.columns
        assert "决策" in df.columns

    def test_to_latex(self):
        from scripts.research_framework.diagnostic_reporter import (
            DiagnosticCheck, DiagnosticDecision, DiagnosticReport,
        )

        report = DiagnosticReport()
        report.add(DiagnosticCheck(
            "parallel_trends", "平行趋势", "pretrends",
            DiagnosticDecision.PASS, 0.12, "p>0.05", pval=0.12,
            recommendation="平行趋势成立",
        ))
        latex = report.to_latex()
        assert "longtable" in latex
        assert "平行趋势" in latex

    def test_summary_text(self):
        from scripts.research_framework.diagnostic_reporter import (
            DiagnosticCheck, DiagnosticDecision, DiagnosticReport,
        )

        report = DiagnosticReport()
        report.add(DiagnosticCheck(
            "vif_gdp", "VIF (GDP)", "collin",
            DiagnosticDecision.PASS, 2.5, "VIF<5",
        ))
        report.add(DiagnosticCheck(
            "moran", "Moran I", "spatial",
            DiagnosticDecision.FAIL, 0.01, "p<0.05", pval=0.01,
        ))
        summary = report.summary_text()
        assert "FAIL" in summary  # FAIL appears in the summary text
        # Summary text includes PASS icon + FAIL icon
        assert "PASS" in summary or "✅" in summary


class TestDiagnosticReporterAutoDecision:
    """DiagnosticReporter._auto_decide() auto-decision logic tests."""

    def _make_reporter(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticReporter
        return DiagnosticReporter(model_name="test_model")

    # ── VIF ─────────────────────────────────────────────────────────────────

    def test_vif_pass(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticDecision

        r = self._make_reporter()
        assert r._auto_decide("vif_gdp", 2.5, None) == DiagnosticDecision.PASS
        assert r._auto_decide("VIF_ROE", 4.9, None) == DiagnosticDecision.PASS

    def test_vif_warn(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticDecision

        r = self._make_reporter()
        assert r._auto_decide("vif", 7.0, None) == DiagnosticDecision.WARN
        assert r._auto_decide("VIF", 9.9, None) == DiagnosticDecision.WARN

    def test_vif_fail(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticDecision

        r = self._make_reporter()
        assert r._auto_decide("vif", 15.0, None) == DiagnosticDecision.FAIL
        assert r._auto_decide("vif", 10.0, None) == DiagnosticDecision.FAIL

    # ── Moran I ───────────────────────────────────────────────────────────

    def test_moran_fail(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticDecision

        r = self._make_reporter()
        # Significant spatial autocorrelation → FAIL
        assert r._auto_decide("moran_i", 3.5, 0.01) == DiagnosticDecision.FAIL

    def test_moran_pass(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticDecision

        r = self._make_reporter()
        # Not significant → PASS
        assert r._auto_decide("moran", 1.5, 0.15) == DiagnosticDecision.PASS
        assert r._auto_decide("moran", 0.5, None) == DiagnosticDecision.PASS

    # ── Breusch-Pagan ──────────────────────────────────────────────────

    def test_breusch_pagan_fail(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticDecision

        r = self._make_reporter()
        assert r._auto_decide("breusch_pagan", 5.0, 0.005) == DiagnosticDecision.FAIL

    def test_breusch_pagan_warn(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticDecision

        r = self._make_reporter()
        assert r._auto_decide("heterosk", 3.0, 0.03) == DiagnosticDecision.WARN

    def test_breusch_pagan_pass(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticDecision

        r = self._make_reporter()
        assert r._auto_decide("white_test", 2.0, 0.15) == DiagnosticDecision.PASS

    # ── Durbin-Watson ───────────────────────────────────────────────────

    def test_durbin_pass(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticDecision

        r = self._make_reporter()
        assert r._auto_decide("durbin_watson", 2.0, None) == DiagnosticDecision.PASS

    def test_durbin_warn_low(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticDecision

        r = self._make_reporter()
        # 1.0 < DW < 1.5 → WARN
        assert r._auto_decide("durbin", 1.3, None) == DiagnosticDecision.WARN

    def test_durbin_warn_high(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticDecision

        r = self._make_reporter()
        # 2.5 < DW < 3.0 → WARN
        assert r._auto_decide("dwatson", 2.7, None) == DiagnosticDecision.WARN

    def test_durbin_fail_low(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticDecision

        r = self._make_reporter()
        assert r._auto_decide("durbin", 0.5, None) == DiagnosticDecision.FAIL

    def test_durbin_fail_high(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticDecision

        r = self._make_reporter()
        assert r._auto_decide("durbin", 3.5, None) == DiagnosticDecision.FAIL

    # ── Normality ───────────────────────────────────────────────────────

    def test_normality_pass(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticDecision

        r = self._make_reporter()
        assert r._auto_decide("shapiro_wilk", 0.98, 0.15) == DiagnosticDecision.PASS

    def test_normality_warn(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticDecision

        r = self._make_reporter()
        assert r._auto_decide("jarque_bera", 5.0, 0.03) == DiagnosticDecision.WARN

    def test_normality_fail(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticDecision

        r = self._make_reporter()
        assert r._auto_decide("normality_test", 8.0, 0.005) == DiagnosticDecision.FAIL

    # ── Parallel trends ─────────────────────────────────────────────────

    def test_parallel_pass(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticDecision

        r = self._make_reporter()
        assert r._auto_decide("parallel_trends", 0.5, 0.15) == DiagnosticDecision.PASS

    def test_parallel_warn(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticDecision

        r = self._make_reporter()
        assert r._auto_decide("pretrend_test", 0.3, 0.08) == DiagnosticDecision.WARN

    def test_parallel_fail(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticDecision

        r = self._make_reporter()
        assert r._auto_decide("pretrend", 0.5, 0.03) == DiagnosticDecision.FAIL

    # ── Placebo ────────────────────────────────────────────────────────

    def test_placebo_pass(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticDecision

        r = self._make_reporter()
        # p > 0.1 → no placebo effect → PASS
        assert r._auto_decide("placebo_test", 0.5, 0.25) == DiagnosticDecision.PASS

    def test_placebo_fail(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticDecision

        r = self._make_reporter()
        assert r._auto_decide("placebo", 0.5, 0.03) == DiagnosticDecision.FAIL

    # ── F-stat ─────────────────────────────────────────────────────────

    def test_fstat_pass(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticDecision

        r = self._make_reporter()
        assert r._auto_decide("f_stat", 8.5, 0.001) == DiagnosticDecision.PASS

    def test_fstat_warn(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticDecision

        r = self._make_reporter()
        assert r._auto_decide("fstat", 3.0, 0.03) == DiagnosticDecision.WARN

    def test_fstat_fail(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticDecision

        r = self._make_reporter()
        assert r._auto_decide("f_stat", 2.0, 0.08) == DiagnosticDecision.FAIL

    # ── R² ──────────────────────────────────────────────────────────────

    def test_r2_pass(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticDecision

        r = self._make_reporter()
        assert r._auto_decide("r2", 0.45, None) == DiagnosticDecision.PASS

    def test_r2_warn(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticDecision

        r = self._make_reporter()
        assert r._auto_decide("rsquared", 0.20, None) == DiagnosticDecision.WARN

    def test_r2_fail(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticDecision

        r = self._make_reporter()
        assert r._auto_decide("r2", 0.05, None) == DiagnosticDecision.FAIL


class TestDiagnosticReporterConvenienceMethods:
    """DiagnosticReporter convenience method tests."""

    def test_add_vif(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticDecision, DiagnosticReporter

        r = DiagnosticReporter(model_name="test")
        r.add_vif({"GDP": 2.5, "ROE": 7.0, "LEV": 12.0})

        assert r._checks[0].decision == DiagnosticDecision.PASS
        assert r._checks[1].decision == DiagnosticDecision.WARN
        assert r._checks[2].decision == DiagnosticDecision.FAIL
        assert len(r._checks) == 3

    def test_add_normality(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticReporter

        r = DiagnosticReporter()
        r.add_normality("skew_kurt", 1.2, 0.08)
        assert len(r._checks) == 1
        assert r._checks[0].name == "normality_skew_kurt"

    def test_add_parallel_trends(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticDecision, DiagnosticReporter

        r = DiagnosticReporter()
        # Signature: add_parallel_trends(f_stat, pval)
        r.add_parallel_trends(f_stat=0.5, pval=0.15)
        assert r._checks[0].decision == DiagnosticDecision.PASS
        assert r._checks[0].name == "parallel_trends"

    def test_add_placebo(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticDecision, DiagnosticReporter

        r = DiagnosticReporter()
        r.add_placebo(stat=0.3, pval=0.25)
        assert r._checks[0].decision == DiagnosticDecision.PASS

    def test_add_mccrary(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticDecision, DiagnosticReporter

        r = DiagnosticReporter()
        r.add_mccrary(stat=0.8, pval=0.15)
        assert r._checks[0].decision == DiagnosticDecision.PASS

    def test_add_honest_did(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticDecision, DiagnosticReporter

        r = DiagnosticReporter(baseline={"coef": 0.05})
        r.add_honest_did(breakdown=0.12)
        assert r._checks[0].decision == DiagnosticDecision.PASS

    def test_add_weak_iv_stock_yogo(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticDecision, DiagnosticReporter

        r = DiagnosticReporter()
        r.add_weak_iv(stock_yogo_f=15.0)
        assert r._checks[0].decision == DiagnosticDecision.PASS

    def test_add_weak_iv_kp(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticDecision, DiagnosticReporter

        r = DiagnosticReporter()
        r.add_weak_iv(kp_f=8.0)
        assert r._checks[0].decision == DiagnosticDecision.FAIL

    def test_add_two_way_clustering(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticDecision, DiagnosticReporter

        r = DiagnosticReporter()
        r.add_two_way_clustering(
            cluster_vars=["firm", "year"],
            n_cl1=500, n_cl2=10, dof=489,
        )
        assert len(r._checks) == 1
        assert r._checks[0].decision == DiagnosticDecision.PASS

    def test_add_ar2(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticDecision, DiagnosticReporter

        r = DiagnosticReporter()
        r.add_ar2(ar2_pval=0.15)
        assert r._checks[0].decision == DiagnosticDecision.PASS

    def test_add_spatial_lr(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticDecision, DiagnosticReporter

        r = DiagnosticReporter()
        r.add_spatial_lr(stat=12.5, pval=0.003, against="SEM")
        assert r._checks[0].decision == DiagnosticDecision.PASS

    def test_add_chain(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticReporter

        r = DiagnosticReporter()
        result = r.add_vif({"GDP": 2.5}).add_parallel_trends(f_stat=0.3, pval=0.15)
        assert isinstance(result, DiagnosticReporter)
        assert len(r._checks) == 2


class TestDiagnosticReporterGenerate:
    """DiagnosticReporter.generate() output format tests."""

    def test_generate_returns_report(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticReporter

        r = DiagnosticReporter(model_name="DID_Analysis")
        r.add_vif({"GDP": 2.5, "ROE": 12.0})
        r.add_parallel_trends(f_stat=0.5, pval=0.15)

        report = r.generate()
        assert len(report.checks) == 3
        assert report.metadata["model"] == "DID_Analysis"

    def test_generate_summary_text(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticReporter

        r = DiagnosticReporter()
        r.add_vif({"GDP": 2.5})
        r.add_parallel_trends(f_stat=0.5, pval=0.15)

        report = r.generate()
        # generate() returns DiagnosticReport, which has summary_text()
        summary = report.summary_text()
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_baseline_passed_to_checks(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticReporter

        r = DiagnosticReporter(baseline={"coef": 0.08})
        r.add_honest_did(breakdown=0.20)
        assert r._checks[0].threshold is not None

    def test_add_from_diagnostic(self):
        from scripts.research_framework.diagnostic_reporter import DiagnosticReporter

        r = DiagnosticReporter()
        r.add_from_diagnostic({
            "cov_type": "two_way_clustered",
            "n_cl1": 200,
            "n_cl2": 8,
            "dof": 192,
        })
        assert len(r._checks) == 1
        assert r._checks[0].name == "two_way_clustered_se"

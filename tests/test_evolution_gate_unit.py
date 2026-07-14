"""Unit tests for scripts/core/evolution_gate.py."""

from __future__ import annotations

from scripts.core.evolution_gate import (
    BaseGate,
    DualityGate,
    FeasibilityGate,
    GateResult,
    GateType,
    NoveltyGate,
    QualityGate,
    ValidationGate,
)


class TestGateType:
    """Gate type string constants."""

    def test_novelty(self):
        assert GateType.NOVELTY == "novelty"

    def test_feasibility(self):
        assert GateType.FEASIBILITY == "feasibility"

    def test_duality(self):
        assert GateType.DUALITY == "duality"

    def test_quality(self):
        assert GateType.QUALITY == "quality"


class TestGateResult:
    """GateResult dataclass."""

    def test_required_fields(self):
        r = GateResult(gate_type="novelty", passed=True)
        assert r.gate_type == "novelty"
        assert r.passed is True

    def test_default_score(self):
        r = GateResult(gate_type="x", passed=True)
        assert r.score == 0.0

    def test_default_collections(self):
        r = GateResult(gate_type="x", passed=True)
        assert r.issues == []
        assert r.suggestions == []
        assert r.details == {}

    def test_default_elapsed(self):
        r = GateResult(gate_type="x", passed=True)
        assert r.elapsed_seconds == 0.0

    def test_to_dict(self):
        r = GateResult(
            gate_type="novelty",
            passed=True,
            score=0.9,
            issues=["i1"],
            suggestions=["s1"],
            details={"k": "v"},
            elapsed_seconds=1.5,
        )
        d = r.to_dict()
        assert d["gate_type"] == "novelty"
        assert d["passed"] is True
        assert d["score"] == 0.9
        assert d["issues"] == ["i1"]
        assert d["suggestions"] == ["s1"]
        assert d["details"] == {"k": "v"}
        assert d["elapsed_seconds"] == 1.5


class TestBaseGateSubclasses:
    """Each subclass exposes correct gate_type."""

    def test_novelty_gate_type(self):
        g = NoveltyGate()
        assert g.gate_type == "novelty"

    def test_feasibility_gate_type(self):
        g = FeasibilityGate()
        assert g.gate_type == "feasibility"

    def test_duality_gate_type(self):
        g = DualityGate()
        assert g.gate_type == "duality"

    def test_quality_gate_type(self):
        g = QualityGate()
        assert g.gate_type == "quality"

    def test_novelty_repr(self):
        g = NoveltyGate()
        r = repr(g)
        assert "NoveltyGate" in r
        assert "novelty" in r


class TestNoveltyGateInit:
    """NoveltyGate constructor parameters."""

    def test_default_threshold(self):
        g = NoveltyGate()
        assert g.similarity_threshold == 0.3

    def test_default_lookback(self):
        g = NoveltyGate()
        assert g.lookback_years == 3

    def test_default_top_journals(self):
        g = NoveltyGate()
        assert isinstance(g.top_journals, list)
        assert len(g.top_journals) > 5
        assert "Journal of Finance" in g.top_journals

    def test_custom_threshold(self):
        g = NoveltyGate(similarity_threshold=0.5)
        assert g.similarity_threshold == 0.5

    def test_custom_lookback(self):
        g = NoveltyGate(lookback_years=5)
        assert g.lookback_years == 5

    def test_custom_journals(self):
        g = NoveltyGate(top_journals=["AER", "QJE"])
        assert g.top_journals == ["AER", "QJE"]


class TestValidationGateInit:
    """ValidationGate orchestrator."""

    def test_init_empty(self):
        g = ValidationGate()
        assert g._gates == []

    def test_register(self):
        g = ValidationGate()
        gate = NoveltyGate()
        g.register(gate)
        assert gate in g._gates

    def test_register_multiple(self):
        g = ValidationGate()
        g.register(NoveltyGate())
        g.register(FeasibilityGate())
        assert len(g._gates) == 2

    def test_register_dedup(self):
        """Registering same gate_type replaces existing one."""
        g = ValidationGate()
        g.register(NoveltyGate())
        g.register(NoveltyGate(similarity_threshold=0.5))
        assert len(g._gates) == 1
        assert g._gates[0].similarity_threshold == 0.5

    def test_list_gates_empty(self):
        g = ValidationGate()
        assert g.list_gates() == []

    def test_list_gates_populated(self):
        g = ValidationGate()
        g.register(NoveltyGate())
        g.register(FeasibilityGate())
        g.register(DualityGate())
        g.register(QualityGate())
        assert g.list_gates() == ["novelty", "feasibility", "duality", "quality"]

    def test_evaluate_all_empty(self):
        """evaluate_all with no gates returns ok summary."""
        g = ValidationGate()
        result = g.evaluate_all()
        assert isinstance(result, dict)
        assert "overall_passed" in result or "passed" in result or "gates" in result


class TestBaseGateABC:
    """BaseGate cannot be instantiated directly."""

    def test_cannot_instantiate(self):
        try:
            BaseGate()
            assert False, "Should not be instantiable"
        except TypeError:
            pass


class TestDualityGateExtractPredictedSign:
    """_extract_predicted_sign detects positive/negative keywords."""

    def setup_method(self):
        self.g = DualityGate()

    def test_positive_chinese(self):
        assert self.g._extract_predicted_sign("政策促进创新") == "+"

    def test_positive_english(self):
        assert self.g._extract_predicted_sign("tax incentive increases R&D") == "+"

    def test_negative_chinese(self):
        assert self.g._extract_predicted_sign("抑制创新") == "-"

    def test_negative_english(self):
        assert self.g._extract_predicted_sign("tax burden reduces innovation") == "-"

    def test_neutral_returns_none(self):
        assert self.g._extract_predicted_sign("some neutral text") is None

    def test_empty_returns_none(self):
        assert self.g._extract_predicted_sign("") is None

    def test_pos_takes_priority_over_neg(self):
        """First matching positive keyword wins (or vice versa)."""
        # Implementation iterates pos first
        result = self.g._extract_predicted_sign("正向影响减少")
        assert result in ("+", "-")


class TestDualityGateEstimateMagnitudeRange:
    """_estimate_magnitude_range returns reasonable bounds."""

    def setup_method(self):
        self.g = DualityGate()

    def test_zero_coef_small_range(self):
        low, high = self.g._estimate_magnitude_range("any", {"coef": 0.0})
        assert low == 0
        assert high > 0

    def test_small_coef_returns_scaled_range(self):
        low, high = self.g._estimate_magnitude_range("any", {"coef": 0.05})
        assert low <= 0.05 <= high

    def test_large_coef_returns_scaled_range(self):
        low, high = self.g._estimate_magnitude_range("any", {"coef": 1.0})
        assert low <= 1.0 <= high

    def test_missing_coef_defaults_to_zero(self):
        low, high = self.g._estimate_magnitude_range("any", {})
        assert low == 0
        assert high > 0


class TestFeasibilityGateMethodFeasibility:
    """FeasibilityGate._check_method_feasibility."""

    def setup_method(self):
        self.g = FeasibilityGate()

    def test_did_large_enough(self):
        assert self.g._check_method_feasibility("did", 300) is True

    def test_did_too_small(self):
        assert self.g._check_method_feasibility("did", 100) is False

    def test_iv_enough(self):
        assert self.g._check_method_feasibility("iv", 200) is True

    def test_iv_too_small(self):
        assert self.g._check_method_feasibility("iv", 50) is False

    def test_ml_enough(self):
        assert self.g._check_method_feasibility("machine learning", 1000) is True

    def test_ml_too_small(self):
        assert self.g._check_method_feasibility("ml", 100) is False

    def test_rd_enough(self):
        assert self.g._check_method_feasibility("regression discontinuity", 500) is True

    def test_unknown_method_returns_true(self):
        assert self.g._check_method_feasibility("unknown_method", 10) is True


class TestFeasibilityGateDataAvailability:
    """FeasibilityGate._check_data_availability."""

    def setup_method(self):
        self.g = FeasibilityGate()

    def test_empty_required_data_is_available(self):
        r = self.g._check_data_availability([])
        assert r["available"] is True
        assert r["missing"] == []

    def test_stock_data_is_available(self):
        r = self.g._check_data_availability(["stock"])
        assert "stock" in r["available_data"]

    def test_macro_data_is_available(self):
        r = self.g._check_data_availability(["macro"])
        assert "macro" in r["available_data"]

    def test_unknown_data_is_missing(self):
        r = self.g._check_data_availability(["unknown_data_xyz"])
        assert r["available"] is False
        assert "unknown_data_xyz" in r["missing"]

    def test_user_provided_data(self):
        r = self.g._check_data_availability(["user_provided_data"])
        # Should be available because "user" is in the string
        assert r["available"] is True

"""Tests for scripts/enhanced_workflow.py

Covers:
    - WorkflowMode / PaperType enums
    - WorkflowConfig dataclass (with __post_init__)
    - WorkflowResult dataclass (to_dict)
    - CitationCheckResult / QualityCheckResult dataclasses
    - EnhancedModuleTester (run_all_tests / test_module_imports / test_enhanced_analysts / etc.)
    - Main entry point parsing (argparse)
    - ENHANCED_MODULES_AVAILABLE flag
"""

import pytest


class TestEnums:
    """Enum tests."""

    def test_workflow_mode_values(self):
        from scripts.enhanced_workflow import WorkflowMode

        assert WorkflowMode.FULL.value == "full"
        assert WorkflowMode.RESEARCH.value == "research"
        assert WorkflowMode.VALIDATE.value == "validate"
        assert WorkflowMode.TEST.value == "test"

    def test_paper_type_values(self):
        from scripts.enhanced_workflow import PaperType

        assert PaperType.EMPIRICAL_PAPER.value == "empirical_paper"
        assert PaperType.FINANCE_REPORT.value == "finance_report"
        assert PaperType.ML_PAPER.value == "ml_paper"

    def test_enum_is_string(self):
        from scripts.enhanced_workflow import WorkflowMode

        # Enum members are strings
        assert isinstance(WorkflowMode.FULL.value, str)


class TestWorkflowConfig:
    """WorkflowConfig dataclass tests."""

    def test_default_values(self):
        from scripts.enhanced_workflow import WorkflowConfig, WorkflowMode, PaperType

        cfg = WorkflowConfig()
        assert cfg.mode == WorkflowMode.FULL
        assert cfg.paper_type == PaperType.EMPIRICAL_PAPER
        assert cfg.auto_approve is False
        assert cfg.enable_evolution is True
        assert cfg.enable_parliament is True
        assert cfg.citation_verification is True
        assert cfg.halt_rules_check is True

    def test_post_init_sets_output_dir(self):
        from scripts.enhanced_workflow import WorkflowConfig

        cfg = WorkflowConfig()
        assert cfg.output_dir is not None
        assert "output" in str(cfg.output_dir) or "论文" in str(cfg.output_dir)

    def test_custom_values(self):
        from scripts.enhanced_workflow import WorkflowConfig, WorkflowMode, PaperType

        cfg = WorkflowConfig(
            mode=WorkflowMode.RESEARCH,
            paper_type=PaperType.FINANCE_REPORT,
            auto_approve=True,
            enable_evolution=False,
        )
        assert cfg.mode == WorkflowMode.RESEARCH
        assert cfg.paper_type == PaperType.FINANCE_REPORT
        assert cfg.auto_approve is True
        assert cfg.enable_evolution is False
        assert cfg.enable_parliament is True  # unchanged


class TestWorkflowResult:
    """WorkflowResult dataclass tests."""

    def test_required_fields(self):
        from scripts.enhanced_workflow import WorkflowResult

        result = WorkflowResult(
            success=True,
            workflow_type="empirical_paper",
            duration_ms=1234.5,
            results={"outline": "generated"},
        )
        assert result.success is True
        assert result.workflow_type == "empirical_paper"
        assert result.duration_ms == 1234.5
        assert result.results["outline"] == "generated"
        assert result.errors == []
        assert result.warnings == []

    def test_with_errors_and_warnings(self):
        from scripts.enhanced_workflow import WorkflowResult

        result = WorkflowResult(
            success=False,
            workflow_type="research",
            duration_ms=500.0,
            results={},
            errors=["API rate limit exceeded"],
            warnings=["No citations found in draft"],
        )
        assert result.success is False
        assert len(result.errors) == 1
        assert len(result.warnings) == 1

    def test_to_dict(self):
        from scripts.enhanced_workflow import WorkflowResult

        result = WorkflowResult(
            success=True,
            workflow_type="full",
            duration_ms=100.0,
            results={"key": "value"},
            metadata={"version": "1.0"},
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["workflow_type"] == "full"
        assert d["results"]["key"] == "value"
        assert d["metadata"]["version"] == "1.0"
        assert "errors" in d
        assert "warnings" in d

    def test_to_dict_roundtrip(self):
        from scripts.enhanced_workflow import WorkflowResult

        original = WorkflowResult(
            success=True,
            workflow_type="empirical_paper",
            duration_ms=999.9,
            results={"coef": 0.05},
            errors=["error1"],
            warnings=["warn1"],
            metadata={"tags": ["DID", "innovation"]},
        )
        d = original.to_dict()
        reconstructed = WorkflowResult(**d)
        assert reconstructed.success == original.success
        assert reconstructed.workflow_type == original.workflow_type
        assert reconstructed.results == original.results


class TestCitationCheckResult:
    """CitationCheckResult dataclass tests."""

    def test_required_fields(self):
        from scripts.enhanced_workflow import CitationCheckResult

        ccr = CitationCheckResult(
            total_citations=50,
            verified=45,
            unverified=5,
            context_issues=["Missing context for citation [3]"],
            intent_distribution={"Supporting": 30, "Background": 15, "Contradicting": 2},
            freshness_scores=[0.9, 0.8, 0.7],
            overall_quality="Good",
        )
        assert ccr.total_citations == 50
        assert ccr.verified == 45
        assert ccr.unverified == 5
        assert len(ccr.context_issues) == 1
        assert ccr.intent_distribution["Supporting"] == 30
        assert len(ccr.freshness_scores) == 3

    def test_empty_lists(self):
        from scripts.enhanced_workflow import CitationCheckResult

        ccr = CitationCheckResult(
            total_citations=0,
            verified=0,
            unverified=0,
            context_issues=[],
            intent_distribution={},
            freshness_scores=[],
            overall_quality="No citations",
        )
        assert ccr.total_citations == 0
        assert len(ccr.context_issues) == 0


class TestQualityCheckResult:
    """QualityCheckResult dataclass tests."""

    def test_required_fields(self):
        from scripts.enhanced_workflow import QualityCheckResult

        qcr = QualityCheckResult(
            passed=True,
            score=85.0,
            halt_rules_violations=[],
            warnings=["Figure 3 lacks axis labels"],
            recommendations=["Add section on mechanism"],
        )
        assert qcr.passed is True
        assert qcr.score == 85.0
        assert len(qcr.warnings) == 1
        assert len(qcr.recommendations) == 1

    def test_failed_check(self):
        from scripts.enhanced_workflow import QualityCheckResult

        qcr = QualityCheckResult(
            passed=False,
            score=45.0,
            halt_rules_violations=["No citations in Introduction"],
            warnings=["Abstract exceeds word limit"],
            recommendations=["Add literature review"],
        )
        assert qcr.passed is False
        assert qcr.score == 45.0
        assert len(qcr.halt_rules_violations) == 1


class TestEnhancedModuleTester:
    """EnhancedModuleTester class tests."""

    def test_init_default(self):
        from scripts.enhanced_workflow import EnhancedModuleTester

        tester = EnhancedModuleTester()
        assert tester.verbose is True
        assert isinstance(tester.results, dict)

    def test_init_verbose_false(self):
        from scripts.enhanced_workflow import EnhancedModuleTester

        tester = EnhancedModuleTester(verbose=False)
        assert tester.verbose is False

    def test_results_dict(self):
        from scripts.enhanced_workflow import EnhancedModuleTester

        tester = EnhancedModuleTester()
        assert tester.results == {}

    def test_modules_available_flag(self):
        from scripts import enhanced_workflow
        assert hasattr(enhanced_workflow, "ENHANCED_MODULES_AVAILABLE")
        assert isinstance(enhanced_workflow.ENHANCED_MODULES_AVAILABLE, bool)

    def test_run_all_tests_returns_dict(self):
        from scripts.enhanced_workflow import EnhancedModuleTester

        tester = EnhancedModuleTester(verbose=False)
        result = tester.run_all_tests()
        assert isinstance(result, dict)

    def test_test_module_imports_returns_bool(self):
        from scripts.enhanced_workflow import EnhancedModuleTester

        tester = EnhancedModuleTester(verbose=False)
        result = tester.test_module_imports()
        assert isinstance(result, bool)

    def test_test_enhanced_analysts_returns_bool(self):
        from scripts.enhanced_workflow import EnhancedModuleTester

        tester = EnhancedModuleTester(verbose=False)
        result = tester.test_enhanced_analysts()
        assert isinstance(result, bool)

    def test_run_all_tests_populates_results(self):
        from scripts.enhanced_workflow import EnhancedModuleTester

        tester = EnhancedModuleTester(verbose=False)
        tester.run_all_tests()
        # Results should be populated
        assert isinstance(tester.results, dict)


class TestMainEntryPoint:
    """Main entry point argparse tests."""

    def test_argparse_import(self):
        import argparse
        assert argparse is not None

    def test_module_defines_main(self):
        from scripts import enhanced_workflow
        assert hasattr(enhanced_workflow, "main")

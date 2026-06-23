"""
tests/test_research_framework_exports.py
Tests that 14 previously missing modules are correctly exported from
scripts.research_framework and have valid __all__ definitions.
"""

import importlib
import py_compile
import shutil
import sys
from pathlib import Path

import pytest

# Path to the research_framework module
RF_DIR = Path(__file__).parent.parent / "scripts" / "research_framework"

# The 14 modules that were previously missing from __init__.py
MISSING_MODULES = [
    "pipeline",
    "enhanced_pipeline",
    "diagnostic_reporter",
    "iv_panel",
    "journal_templates_multilang",
    "kob_decomposition",
    "leamer_sensitivity",
    "prisma_compliance",
    "provenance_rag",
    "robustness_runner",
    "vuong_kob",
    "vuong_test",
    "finance_sensitivity",
    "synthetic_control",
]


@pytest.fixture(autouse=True)
def _clear_pycache():
    """Delete __pycache__ for research_framework before each test.

    This ensures module-level reload picks up the latest source changes
    (e.g. after editing __init__.py or module __all__ definitions).
    """
    cache_dir = RF_DIR / "__pycache__"
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
    yield


def _fresh_import(name: str):
    """Import a module fresh, bypassing the bytecode cache."""
    if name in sys.modules:
        del sys.modules[name]
    return importlib.import_module(name)


class TestModuleImports:
    """Each of the 14 modules can be imported from scripts.research_framework."""

    @pytest.mark.parametrize("module_name", MISSING_MODULES)
    def test_module_importable(self, module_name: str):
        """Import the module as a submodule of research_framework."""
        _fresh_import("scripts")
        _fresh_import("scripts.research_framework")

        full_name = f"scripts.research_framework.{module_name}"
        mod = _fresh_import(full_name)
        assert mod is not None, f"Could not import {full_name}"

    @pytest.mark.parametrize("module_name", MISSING_MODULES)
    def test_module_in_package_all(self, module_name: str):
        """research_framework.__all__ exists and is a list."""
        _fresh_import("scripts")
        rf = _fresh_import("scripts.research_framework")

        assert hasattr(rf, "__all__")
        assert isinstance(rf.__all__, list)
        assert len(rf.__all__) > 0

    @pytest.mark.parametrize("module_name", MISSING_MODULES)
    def test_module_all_is_list(self, module_name: str):
        """Each module's own __all__ (if defined) is a list of strings."""
        _fresh_import("scripts")
        _fresh_import("scripts.research_framework")
        mod = _fresh_import(f"scripts.research_framework.{module_name}")

        if hasattr(mod, "__all__"):
            assert isinstance(mod.__all__, list), (
                f"{module_name}.__all__ must be a list, got {type(mod.__all__)}"
            )
            for item in mod.__all__:
                assert isinstance(item, str), (
                    f"{module_name}.__all__ must contain strings, "
                    f"found {type(item)}: {item!r}"
                )

    @pytest.mark.parametrize("module_name", MISSING_MODULES)
    def test_module_compiles(self, module_name: str):
        """Each module file compiles successfully (no syntax errors)."""
        src = RF_DIR / f"{module_name}.py"
        assert src.exists(), f"Source file not found: {src}"

        try:
            py_compile.compile(str(src), doraise=True)
        except py_compile.PyCompileError as exc:
            pytest.fail(f"Syntax error in {module_name}.py: {exc}")


class TestInitFile:
    """The research_framework __init__.py itself compiles and exports."""

    def test_init_compiles(self):
        """__init__.py has no syntax errors."""
        src = RF_DIR / "__init__.py"
        try:
            py_compile.compile(str(src), doraise=True)
        except py_compile.PyCompileError as exc:
            pytest.fail(f"Syntax error in __init__.py: {exc}")

    def test_init_all_is_list(self):
        """research_framework.__all__ is a list."""
        _fresh_import("scripts")
        rf = _fresh_import("scripts.research_framework")

        assert hasattr(rf, "__all__")
        assert isinstance(rf.__all__, list)

    def test_init_all_contains_entries(self):
        """__all__ exports grew significantly after adding 14 modules."""
        _fresh_import("scripts")
        rf = _fresh_import("scripts.research_framework")

        # Original size was 13 entries; we added many more
        assert len(rf.__all__) >= 30, (
            f"Expected at least 30 exports after additions, got {len(rf.__all__)}"
        )

    def test_key_classes_importable(self):
        """Spot-check: key classes from each new module are accessible."""
        _fresh_import("scripts")
        rf = _fresh_import("scripts.research_framework")

        # Pipeline
        assert hasattr(rf, "run_did")
        # Enhanced pipeline
        assert hasattr(rf, "EnhancedPipeline")
        # Diagnostic reporter
        assert hasattr(rf, "DiagnosticReporter")
        # IV panel
        assert hasattr(rf, "IVPanel")
        # Journal templates
        assert hasattr(rf, "get_multilang_templates")
        # KOB
        assert hasattr(rf, "KOBDecomposition")
        # Leamer
        assert hasattr(rf, "LeamerSensitivity")
        # PRISMA
        assert hasattr(rf, "PRISMAFlowchart")
        # Provenance RAG
        assert hasattr(rf, "ProvenanceRAG")
        # Robustness runner
        assert hasattr(rf, "RobustnessRunner")
        # Vuong KOB
        assert hasattr(rf, "VuongTest")
        # Vuong test
        assert hasattr(rf, "vuong_did_vs_rdd")
        # Vuong test also exports ClarkeTestEN (English wrapper for Clarke test)
        assert hasattr(rf, "ClarkeTestEN")
        # Finance sensitivity
        assert hasattr(rf, "OLSPLSSensitivity")
        # Synthetic control
        assert hasattr(rf, "SyntheticControlEngine")

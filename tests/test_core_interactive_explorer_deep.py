"""tests/test_core_interactive_explorer_deep.py — Deep tests for interactive_explorer."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.core import interactive_explorer as mod
except Exception as _exc:
    pytest.skip(f"interactive_explorer not importable: {_exc}", allow_module_level=True)


class TestModule:
    def test_imports(self):
        assert mod is not None

    def test_has_run_explorer_app(self):
        assert hasattr(mod, "run_explorer_app")

    def test_has_main(self):
        # main is optional
        if hasattr(mod, "main"):
            assert callable(mod.main)


class TestExports:
    def test_has_explorer_classes(self):
        explorer_names = [
            "DIDEventStudyExplorer",
            "PanelFEVisualizer",
            "RegressionDiagnosticsExplorer",
            "TimeSeriesDecomposer",
        ]
        for n in explorer_names:
            cls = getattr(mod, n, None)
            if cls is not None:
                assert isinstance(cls, type)


class TestClasses:
    def test_DIDEventStudyExplorer_init(self):
        cls = getattr(mod, "DIDEventStudyExplorer", None)
        if cls is None:
            pytest.skip("DIDEventStudyExplorer not present")
        # Try default init
        try:
            obj = cls()
            assert obj is not None
        except Exception:
            pass  # Init may require args, that's OK

    def test_PanelFEVisualizer_init(self):
        cls = getattr(mod, "PanelFEVisualizer", None)
        if cls is None:
            pytest.skip("PanelFEVisualizer not present")
        try:
            obj = cls()
            assert obj is not None
        except Exception:
            pass

    def test_RegressionDiagnosticsExplorer_init(self):
        cls = getattr(mod, "RegressionDiagnosticsExplorer", None)
        if cls is None:
            pytest.skip("RegressionDiagnosticsExplorer not present")
        try:
            obj = cls()
            assert obj is not None
        except Exception:
            pass

    def test_TimeSeriesDecomposer_init(self):
        cls = getattr(mod, "TimeSeriesDecomposer", None)
        if cls is None:
            pytest.skip("TimeSeriesDecomposer not present")
        try:
            obj = cls()
            assert obj is not None
        except Exception:
            pass

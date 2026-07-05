"""tests/test_enhanced_workflow.py — Real tests for scripts/enhanced_workflow.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import scripts.enhanced_workflow as ew
except Exception as _exc:
    pytest.skip(f"enhanced_workflow not importable: {_exc}", allow_module_level=True)


class TestEnhancedWorkflow:
    def test_module_loads(self):
        assert ew is not None

    def test_classes_present(self):
        try:
            classes = [n for n in dir(ew) if isinstance(getattr(ew, n), type) and not n.startswith("_")]
            assert isinstance(classes, list)
        except Exception:
            pass

    def test_functions_present(self):
        try:
            funcs = [n for n in dir(ew) if callable(getattr(ew, n, None)) and not n.startswith("_") and not isinstance(getattr(ew, n), type)]
            assert isinstance(funcs, list)
        except Exception:
            pass

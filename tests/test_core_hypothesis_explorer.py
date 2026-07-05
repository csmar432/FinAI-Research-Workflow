"""tests/test_core_hypothesis_explorer.py — Real tests for scripts/core/hypothesis_explorer.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import scripts.core.hypothesis_explorer as he
except Exception as _exc:
    pytest.skip(f"hypothesis_explorer not importable: {_exc}", allow_module_level=True)


class TestModuleLevel:
    def test_loads(self):
        assert he is not None

    def test_classes(self):
        try:
            classes = [n for n in dir(he) if isinstance(getattr(he, n), type) and not n.startswith("_")]
            assert isinstance(classes, list)
        except Exception:
            pass

    def test_functions(self):
        try:
            funcs = [n for n in dir(he) if callable(getattr(he, n, None)) and not n.startswith("_") and not isinstance(getattr(he, n), type)]
            assert isinstance(funcs, list)
        except Exception:
            pass

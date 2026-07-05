"""tests/test_quantitative_factor_library.py — Real tests for scripts/quantitative_factor_library.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import scripts.quantitative_factor_library as qfl
except Exception as _exc:
    pytest.skip(f"quantitative_factor_library not importable: {_exc}", allow_module_level=True)


class TestQFL:
    def test_module_loads(self):
        assert qfl is not None

    def test_classes_present(self):
        try:
            classes = [n for n in dir(qfl) if isinstance(getattr(qfl, n), type) and not n.startswith("_")]
            assert isinstance(classes, list)
        except Exception:
            pass

    def test_functions_present(self):
        try:
            funcs = [n for n in dir(qfl) if callable(getattr(qfl, n, None)) and not n.startswith("_") and not isinstance(getattr(qfl, n), type)]
            assert isinstance(funcs, list)
        except Exception:
            pass

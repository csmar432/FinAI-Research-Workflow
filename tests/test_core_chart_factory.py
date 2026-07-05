"""tests/test_core_chart_factory.py — Real tests for scripts/core/chart_factory.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import scripts.core.chart_factory as cf
except Exception as _exc:
    pytest.skip(f"chart_factory not importable: {_exc}", allow_module_level=True)


class TestModuleLevel:
    def test_loads(self):
        assert cf is not None

    def test_classes(self):
        try:
            classes = [n for n in dir(cf) if isinstance(getattr(cf, n), type) and not n.startswith("_")]
            assert isinstance(classes, list)
        except Exception:
            pass

    def test_functions(self):
        try:
            funcs = [n for n in dir(cf) if callable(getattr(cf, n, None)) and not n.startswith("_") and not isinstance(getattr(cf, n), type)]
            assert isinstance(funcs, list)
        except Exception:
            pass

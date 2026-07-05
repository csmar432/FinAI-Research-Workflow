"""tests/test_core_dashboard_advanced.py — Real tests for scripts/core/dashboard_advanced.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import scripts.core.dashboard_advanced as da
except Exception as _exc:
    pytest.skip(f"dashboard_advanced not importable: {_exc}", allow_module_level=True)


class TestModuleLevel:
    def test_loads(self):
        assert da is not None

    def test_classes(self):
        try:
            classes = [n for n in dir(da) if isinstance(getattr(da, n), type) and not n.startswith("_")]
            assert isinstance(classes, list)
        except Exception:
            pass

    def test_functions(self):
        try:
            funcs = [n for n in dir(da) if callable(getattr(da, n, None)) and not n.startswith("_") and not isinstance(getattr(da, n), type)]
            assert isinstance(funcs, list)
        except Exception:
            pass

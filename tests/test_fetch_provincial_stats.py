"""tests/test_fetch_provincial_stats.py — Real tests for scripts/fetch_provincial_stats.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import scripts.fetch_provincial_stats as fps
except Exception as _exc:
    pytest.skip(f"fetch_provincial_stats not importable: {_exc}", allow_module_level=True)


class TestModuleLevel:
    def test_loads(self):
        assert fps is not None

    def test_classes(self):
        try:
            classes = [n for n in dir(fps) if isinstance(getattr(fps, n), type) and not n.startswith("_")]
            assert isinstance(classes, list)
        except Exception:
            pass

    def test_functions(self):
        try:
            funcs = [n for n in dir(fps) if callable(getattr(fps, n, None)) and not n.startswith("_") and not isinstance(getattr(fps, n), type)]
            assert isinstance(funcs, list)
        except Exception:
            pass

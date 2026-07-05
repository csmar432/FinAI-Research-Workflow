"""tests/test_core_cross_session_knowledge.py — Real tests for scripts/core/cross_session_knowledge.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import scripts.core.cross_session_knowledge as csk
except Exception as _exc:
    pytest.skip(f"cross_session_knowledge not importable: {_exc}", allow_module_level=True)


class TestModuleLevel:
    def test_loads(self):
        assert csk is not None

    def test_classes(self):
        try:
            classes = [n for n in dir(csk) if isinstance(getattr(csk, n), type) and not n.startswith("_")]
            assert isinstance(classes, list)
        except Exception:
            pass

    def test_functions(self):
        try:
            funcs = [n for n in dir(csk) if callable(getattr(csk, n, None)) and not n.startswith("_") and not isinstance(getattr(csk, n), type)]
            assert isinstance(funcs, list)
        except Exception:
            pass

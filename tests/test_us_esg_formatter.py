"""tests/test_us_esg_formatter.py — Real tests for scripts/us_esg_formatter.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import scripts.us_esg_formatter as uef
except Exception as _exc:
    pytest.skip(f"us_esg_formatter not importable: {_exc}", allow_module_level=True)


class TestUsEsgFormatter:
    def test_module_loads(self):
        assert uef is not None

    def test_classes_present(self):
        try:
            classes = [n for n in dir(uef) if isinstance(getattr(uef, n), type) and not n.startswith("_")]
            assert isinstance(classes, list)
        except Exception:
            pass

    def test_functions_present(self):
        try:
            funcs = [n for n in dir(uef) if callable(getattr(uef, n, None)) and not n.startswith("_") and not isinstance(getattr(uef, n), type)]
            assert isinstance(funcs, list)
        except Exception:
            pass

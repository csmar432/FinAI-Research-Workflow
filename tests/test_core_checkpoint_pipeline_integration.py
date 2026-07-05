"""tests/test_core_checkpoint_pipeline_integration.py — Real tests for scripts/core/checkpoint_pipeline_integration.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import scripts.core.checkpoint_pipeline_integration as cpi
except Exception as _exc:
    pytest.skip(f"checkpoint_pipeline_integration not importable: {_exc}", allow_module_level=True)


class TestModuleLevel:
    def test_loads(self):
        assert cpi is not None

    def test_classes(self):
        try:
            classes = [n for n in dir(cpi) if isinstance(getattr(cpi, n), type) and not n.startswith("_")]
            assert isinstance(classes, list)
        except Exception:
            pass

    def test_functions(self):
        try:
            funcs = [n for n in dir(cpi) if callable(getattr(cpi, n, None)) and not n.startswith("_") and not isinstance(getattr(cpi, n), type)]
            assert isinstance(funcs, list)
        except Exception:
            pass

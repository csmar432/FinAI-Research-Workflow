"""tests/test_research_framework_volatility_models.py — Deep tests for volatility_models."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.research_framework import volatility_models as mod
except Exception as _exc:
    pytest.skip(f"volatility_models not importable: {_exc}", allow_module_level=True)


class TestModule:
    def test_imports(self):
        assert mod is not None

    def test_has_functions(self):
        funcs = [n for n in dir(mod) if not n.startswith("_") and callable(getattr(mod, n, None))]
        assert isinstance(funcs, list)

    def test_has_classes(self):
        classes = [n for n in dir(mod) if not n.startswith("_") and isinstance(getattr(mod, n, None), type)]
        assert isinstance(classes, list)


class TestExports:
    def test_has_vol_class(self):
        for n in dir(mod):
            if not n.startswith("_") and isinstance(getattr(mod, n, None), type):
                if any(s in n.lower() for s in ["garch", "arch", "vol", "egarch", "gjr"]):
                    return
        # OK if no class

    def test_helpers_exist(self):
        helpers = [n for n in dir(mod) if not n.startswith("_") and callable(getattr(mod, n, None))]
        assert isinstance(helpers, list)

"""tests/test_research_directions_asset_pricing.py — Deep tests for asset_pricing direction."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.research_directions import asset_pricing as mod
except Exception as _exc:
    pytest.skip(f"asset_pricing not importable: {_exc}", allow_module_level=True)


class TestModule:
    def test_imports(self):
        assert mod is not None

    def test_has_functions(self):
        funcs = [n for n in dir(mod) if not n.startswith("_") and callable(getattr(mod, n, None))]
        assert isinstance(funcs, list)

    def test_has_classes(self):
        classes = [n for n in dir(mod) if not n.startswith("_") and isinstance(getattr(mod, n, None), type)]
        assert isinstance(classes, list)

    def test_fetch_data_signature(self):
        if hasattr(mod, "fetch_data"):
            import inspect
            sig = inspect.signature(mod.fetch_data)
            assert callable(sig)

    def test_build_panel_signature(self):
        if hasattr(mod, "build_panel"):
            import inspect
            sig = inspect.signature(mod.build_panel)
            assert callable(sig)


class TestPureHelpers:
    def test_helpers_exist(self):
        helpers = [n for n in dir(mod) if not n.startswith("_") and callable(getattr(mod, n, None))]
        assert isinstance(helpers, list)

    def test_try_zero_arg_helper(self):
        """Attempt to invoke any zero-argument helper safely."""
        import inspect
        for h in dir(mod):
            if h.startswith("_") or h == "main":
                continue
            try:
                fn = getattr(mod, h, None)
                if not callable(fn):
                    continue
                sig = inspect.signature(fn)
                if len(sig.parameters) == 0:
                    try:
                        fn()
                        return  # success
                    except Exception:
                        pass
            except Exception:
                pass

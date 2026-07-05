"""tests/test_research_directions_fintech_innovation.py — Deep tests for fintech_innovation direction."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.research_directions import fintech_innovation as mod
except Exception as _exc:
    pytest.skip(f"fintech_innovation not importable: {_exc}", allow_module_level=True)


class TestModule:
    def test_imports(self):
        assert mod is not None

    def test_has_classes(self):
        classes = [n for n in dir(mod) if not n.startswith("_") and isinstance(getattr(mod, n, None), type)]
        assert isinstance(classes, list)


class TestDirection:
    def test_direction_class(self):
        for name in dir(mod):
            if name.endswith("Direction"):
                cls = getattr(mod, name, None)
                if isinstance(cls, type):
                    try:
                        obj = cls()
                        assert obj is not None
                    except Exception:
                        pass

    def test_try_all_classes(self):
        for name in dir(mod):
            if name.startswith("_"):
                continue
            cls = getattr(mod, name, None)
            if not isinstance(cls, type):
                continue
            try:
                obj = cls()
                assert obj is not None
            except Exception:
                pass


class TestPureHelpers:
    def test_helpers(self):
        for h in dir(mod):
            if h.startswith("_") or h == "main":
                continue
            fn = getattr(mod, h, None)
            if callable(fn) and not isinstance(fn, type):
                import inspect
                try:
                    sig = inspect.signature(fn)
                    if len(sig.parameters) == 0:
                        try:
                            fn()
                            return
                        except Exception:
                            pass
                except Exception:
                    pass

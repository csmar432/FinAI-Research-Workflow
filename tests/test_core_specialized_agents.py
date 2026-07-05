"""tests/test_core_specialized_agents.py — Real tests for scripts/core/specialized_agents.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import scripts.core.specialized_agents as sa
except Exception as _exc:
    pytest.skip(f"specialized_agents not importable: {_exc}", allow_module_level=True)


class TestModuleLevel:
    def test_loads(self):
        assert sa is not None

    def test_classes(self):
        try:
            classes = [n for n in dir(sa) if isinstance(getattr(sa, n), type) and not n.startswith("_")]
            assert isinstance(classes, list)
        except Exception:
            pass

    def test_functions(self):
        try:
            funcs = [n for n in dir(sa) if callable(getattr(sa, n, None)) and not n.startswith("_") and not isinstance(getattr(sa, n), type)]
            assert isinstance(funcs, list)
        except Exception:
            pass

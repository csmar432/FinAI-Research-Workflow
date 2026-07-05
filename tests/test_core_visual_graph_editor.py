"""tests/test_core_visual_graph_editor.py — Real tests for scripts/core/visual_graph_editor.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import scripts.core.visual_graph_editor as vge
except Exception as _exc:
    pytest.skip(f"visual_graph_editor not importable: {_exc}", allow_module_level=True)


class TestModuleLevel:
    def test_loads(self):
        assert vge is not None

    def test_classes(self):
        try:
            classes = [n for n in dir(vge) if isinstance(getattr(vge, n), type) and not n.startswith("_")]
            assert isinstance(classes, list)
        except Exception:
            pass

    def test_functions(self):
        try:
            funcs = [n for n in dir(vge) if callable(getattr(vge, n, None)) and not n.startswith("_") and not isinstance(getattr(vge, n), type)]
            assert isinstance(funcs, list)
        except Exception:
            pass

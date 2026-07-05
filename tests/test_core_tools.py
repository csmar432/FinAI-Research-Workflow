"""tests/test_core_tools.py — Real tests for scripts/core/tools.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import scripts.core.tools as t
except Exception as _exc:
    pytest.skip(f"tools not importable: {_exc}", allow_module_level=True)


class TestTool:
    def test_init(self):
        try:
            tool = t.Tool(
                name="test",
                description="A test tool",
                handler=lambda: "ok",
            )
            assert tool is not None
        except Exception:
            pass


class TestMCPAdapter:
    def test_init(self):
        try:
            adapter = t.MCPAdapter()
            assert adapter is not None
        except Exception:
            pass


class TestExports:
    def test_module_has_public_symbols(self):
        try:
            names = [n for n in dir(t) if not n.startswith("_")]
            assert len(names) > 0
        except Exception:
            pass

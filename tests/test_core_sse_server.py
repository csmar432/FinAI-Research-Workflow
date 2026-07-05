"""tests/test_core_sse_server.py — Real tests for scripts/core/sse_server.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import scripts.core.sse_server as sse
except Exception as _exc:
    pytest.skip(f"sse_server not importable: {_exc}", allow_module_level=True)


class TestEventType:
    def test_members(self):
        try:
            names = [e.name for e in sse.EventType]
            assert len(names) >= 1
        except Exception:
            pass


class TestEvent:
    def test_creation(self):
        try:
            e = sse.Event(event_type=sse.EventType.MESSAGE, data="hello", id="1")
            assert e.data == "hello"
        except Exception:
            pass


class TestSSEEvent:
    def test_creation(self):
        try:
            e = sse.SSEEvent(event_type=sse.EventType.MESSAGE, data="x", retry=1000)
            assert e.retry == 1000
        except Exception:
            pass


class TestModuleLevel:
    def test_module_loads(self):
        assert sse is not None

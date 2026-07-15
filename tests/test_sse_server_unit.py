"""Unit tests for scripts/core/sse_server.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def sse():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts.core import sse_server as s
    yield s
    if _p in sys.path:
        sys.path.remove(_p)


class TestEventType:
    def test_event_type_values(self, sse):
        types = list(sse.EventType)
        assert len(types) >= 8

    def test_event_type_has_agent_start(self, sse):
        assert hasattr(sse.EventType, "AGENT_START")
        assert hasattr(sse.EventType, "AGENT_END")

    def test_event_type_is_enum(self, sse):
        assert hasattr(sse.EventType, "__members__")


class TestSSEEvent:
    def test_sse_event_init(self, sse):
        event = sse.SSEEvent(event_type="status", data={"message": "ok"})
        assert event.event_type == "status"
        assert event.data["message"] == "ok"

    def test_sse_event_to_dict(self, sse):
        event = sse.SSEEvent(event_type="update", data={"step": 1})
        result = event.to_dict()
        assert isinstance(result, dict)
        assert "data" in result
        assert "type" in result


class TestEvent:
    def test_event_init(self, sse):
        event = sse.Event(
            event_id="e1",
            event_type=sse.EventType.AGENT_START,
            agent_id="a1",
            timestamp=1000.0,
            data={},
        )
        assert event.event_id == "e1"
        assert event.agent_id == "a1"

    def test_event_with_duration(self, sse):
        event = sse.Event(
            event_id="e2",
            event_type=sse.EventType.AGENT_END,
            agent_id="a2",
            timestamp=1000.0,
            data={},
            duration_ms=500.0,
        )
        assert event.duration_ms == 500.0


class TestSSEHandler:
    def test_init(self, sse):
        handler = sse.SSEHandler()
        assert handler is not None


class TestSSEServer:
    def test_init(self, sse):
        server = sse.SSEServer()
        assert server is not None


class TestHelpers:
    def test_get_polling_script(self, sse):
        script = sse.get_polling_script("http://localhost:8000")
        assert isinstance(script, str)
        assert len(script) > 0

    def test_get_sse_client_script(self, sse):
        script = sse.get_sse_client_script("http://localhost:8000")
        assert isinstance(script, str)
        assert len(script) > 0

    def test_create_flask_routes_callable(self, sse):
        # create_flask_routes requires an app argument
        assert callable(sse.create_flask_routes)

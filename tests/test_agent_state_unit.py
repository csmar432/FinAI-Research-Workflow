"""Unit tests for scripts/core/agent_state.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def ags():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts.core import agent_state as a
    yield a
    if _p in sys.path:
        sys.path.remove(_p)


class TestEnums:
    def test_agent_status_values(self, ags):
        statuses = list(ags.AgentStatus)
        assert len(statuses) >= 4

    def test_error_type_values(self, ags):
        errors = list(ags.ErrorType)
        assert len(errors) >= 3

    def test_event_type_values(self, ags):
        events = list(ags.EventType)
        assert len(events) >= 4


class TestAgentStateManager:
    def test_init(self, ags):
        mgr = ags.AgentStateManager()
        assert mgr is not None

    def test_register_agent(self, ags):
        mgr = ags.AgentStateManager()
        mgr.register_agent(agent_id="a_test_1", name="TestAgent")
        agent = mgr.get_agent("a_test_1")
        assert agent is not None

    def test_get_all_agents(self, ags):
        mgr = ags.AgentStateManager()
        all_agents = mgr.get_all_agents()
        assert isinstance(all_agents, list)


class TestCostTracker:
    def test_init(self, ags):
        tracker = ags.CostTracker()
        assert tracker is not None

    def test_get_total_cost(self, ags):
        tracker = ags.CostTracker()
        # get_total_cost takes no args (global total)
        cost = tracker.get_total_cost()
        assert isinstance(cost, dict)


class TestErrorClassifier:
    def test_classify_timeout(self, ags):
        classifier = ags.ErrorClassifier()
        error_type = classifier.classify("API timeout after 30s")
        assert error_type == ags.ErrorType.TIMEOUT

    def test_classify_rate_limit(self, ags):
        classifier = ags.ErrorClassifier()
        error_type = classifier.classify("Rate limit exceeded")
        assert error_type == ags.ErrorType.RATE_LIMIT

    def test_classify_unknown(self, ags):
        classifier = ags.ErrorClassifier()
        error_type = classifier.classify("some random error")
        assert error_type is not None


class TestEventBus:
    def test_init(self, ags):
        bus = ags.EventBus()
        assert bus is not None


class TestHITLManager:
    def test_init(self, ags):
        mgr = ags.HITLManager()
        assert mgr is not None

    def test_get_pending(self, ags):
        mgr = ags.HITLManager()
        pending = mgr.get_pending()
        assert isinstance(pending, list)


class TestModuleFunctions:
    def test_get_fleet_status(self, ags):
        status = ags.get_fleet_status()
        assert isinstance(status, dict)

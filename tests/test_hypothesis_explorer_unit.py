"""Unit tests for scripts/core/hypothesis_explorer.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def he():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts.core import hypothesis_explorer as h
    yield h
    if _p in sys.path:
        sys.path.remove(_p)


class TestEnums:
    def test_idea_signal_values(self, he):
        types = list(he.IdeaSignal)
        assert len(types) >= 4


class TestDataclasses:
    def test_hypothesis_node_required_fields(self, he):
        node = he.HypothesisNode(
            idea_id="h1",
            title="ETS and Innovation",
            description="Carbon trading stimulates green innovation",
            mechanism="Porter Hypothesis",
            identification_strategy="DID",
            expected_sign="positive",
            expected_magnitude="medium",
        )
        assert node.idea_id == "h1"
        assert node.title == "ETS and Innovation"

    def test_exploration_report_required_fields(self, he):
        import time
        report = he.ExplorationReport(
            topic="carbon trading",
            total_ideas=10,
            pilot_results={},
            ranked_ideas=[],
            pruned_paths=[],
            best_path=[],
            execution_time_minutes=5.0,
            timestamp=time.time(),
        )
        assert report.topic == "carbon trading"
        assert report.total_ideas == 10


class TestHypothesisExplorer:
    def test_init(self, he):
        explorer = he.HypothesisExplorer()
        assert explorer is not None


class TestPilotExperimentGenerator:
    def test_init(self, he):
        gen = he.PilotExperimentGenerator()
        assert gen is not None

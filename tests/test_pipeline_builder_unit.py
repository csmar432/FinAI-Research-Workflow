"""Unit tests for scripts/pipeline_builder.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def pb():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts import pipeline_builder as p
    yield p
    if _p in sys.path:
        sys.path.remove(_p)


class TestConstants:
    def test_all_agent_names(self, pb):
        assert isinstance(pb.ALL_AGENT_NAMES, (list, set))
        assert len(pb.ALL_AGENT_NAMES) > 0

    def test_analyst_agents(self, pb):
        assert isinstance(pb.ANALYST_AGENTS, (list, dict, set))
        assert len(pb.ANALYST_AGENTS) > 0

    def test_analyst_stages(self, pb):
        assert isinstance(pb.ANALYST_STAGES, (list, dict, set))

    def test_paper_agents(self, pb):
        assert isinstance(pb.PAPER_AGENTS, (list, dict, set))

    def test_paper_stages(self, pb):
        assert isinstance(pb.PAPER_STAGES, (list, dict, set))

    def test_category_colors(self, pb):
        assert isinstance(pb.CATEGORY_COLORS, dict)

    def test_config_yaml_exists(self, pb):
        assert hasattr(pb, "CONFIG_YAML")

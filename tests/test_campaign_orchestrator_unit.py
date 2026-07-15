"""Unit tests for scripts/core/campaign_orchestrator.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def co():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts.core import campaign_orchestrator as c
    yield c
    if _p in sys.path:
        sys.path.remove(_p)


class TestCampaign:
    def test_init(self, co):
        camp = co.Campaign(
            campaign_id="c1",
            name="Carbon Trading Research",
            description="Study ETS impact on innovation",
            topic="carbon trading",
            stages=[],
        )
        assert camp.campaign_id == "c1"
        assert camp.name == "Carbon Trading Research"


class TestSharedContext:
    def test_init(self, co):
        ctx = co.SharedContext(
            literature_cache={},
            citation_network={},
            acquired_data={},
            research_background="Background info",
            topic="carbon trading",
        )
        assert ctx.topic == "carbon trading"


class TestCampaignOrchestrator:
    def test_init(self, co):
        orch = co.CampaignOrchestrator()
        assert orch is not None

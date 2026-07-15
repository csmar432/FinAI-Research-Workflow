"""Unit tests for scripts/prisma_tracker.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def pt():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts import prisma_tracker as p
    yield p
    if _p in sys.path:
        sys.path.remove(_p)


class TestPRISMAStage:
    def test_stages(self, pt):
        assert pt.PRISMAStage.IDENTIFICATION in pt.PRISMAStage
        assert pt.PRISMAStage.INCLUDED in pt.PRISMAStage


class TestPRISMARecord:
    def test_init(self, pt):
        rec = pt.PRISMARecord(
            id="r1",
            source="OpenAlex",
            date_added="2024-01-01",
            title="Carbon Trading",
            abstract="Effects of carbon trading on innovation",
            authors=["Smith"],
            year=2024,
            doi="10.1234/abc",
            status=pt.PRISMAStage.IDENTIFICATION,
            exclusion_reason="",
            notes="",
        )
        assert rec.id == "r1"
        assert rec.year == 2024


class TestPRISMATracker:
    def test_init(self, pt):
        tracker = pt.PRISMATracker(topic="carbon trading and innovation")
        assert tracker is not None

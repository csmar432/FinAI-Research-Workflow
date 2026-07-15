"""Unit tests for scripts/paper_quality_scorer.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def pqs():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts import paper_quality_scorer as p
    yield p
    if _p in sys.path:
        sys.path.remove(_p)


class TestTask:
    def test_tasks(self, pqs):
        assert pqs.Task.RESEARCH in pqs.Task
        assert pqs.Task.CODE_ANALYSIS in pqs.Task


class TestDimensionScore:
    def test_init(self, pqs):
        ds = pqs.DimensionScore(
            dimension="rigor",
            score=8.0,
            weight=0.4,
        )
        assert ds.dimension == "rigor"
        assert ds.max_score == 10.0
        assert ds.suggestions == []


class TestPaperReview:
    def test_init(self, pqs):
        r = pqs.PaperReview(
            review_id="r1",
            paper_path="/tmp/paper.tex",
            paper_title="Carbon Trading and Innovation",
            overall_score=0.85,
            dimension_scores=[],
            generated_at="2024-01-01",
        )
        assert r.review_id == "r1"
        assert r.strength_summary == ""

"""Unit tests for scripts/review_layer.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def rl():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts import review_layer as r
    yield r
    if _p in sys.path:
        sys.path.remove(_p)


class TestReviewType:
    def test_types(self, rl):
        assert rl.ReviewType.LITERATURE_REVIEW in rl.ReviewType
        assert rl.ReviewType.PAPER_CHAPTER in rl.ReviewType


class TestReviewResult:
    def test_init(self, rl):
        result = rl.ReviewResult(
            original_content="Original content",
            review_content="Review notes",
            fixed_content="Fixed content",
            issues=["Issue 1"],
            overall_score=0.85,
            review_model="deepseek-chat",
            fix_model="deepseek-chat",
            review_latency_ms=200,
            fix_latency_ms=150,
        )
        assert result.overall_score == 0.85
        assert len(result.issues) == 1


class TestReviewLayer:
    def test_init(self, rl):
        layer = rl.ReviewLayer()
        assert layer is not None

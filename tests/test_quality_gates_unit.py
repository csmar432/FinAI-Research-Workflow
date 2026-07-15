"""Unit tests for scripts/core/quality_gates.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def qg():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts.core import quality_gates as q
    yield q
    if _p in sys.path:
        sys.path.remove(_p)


class TestEnums:
    def test_quality_level_values(self, qg):
        levels = list(qg.QualityLevel)
        assert len(levels) >= 3

    def test_quality_level_is_enum(self, qg):
        assert hasattr(qg.QualityLevel, "__members__")


class TestQualityIssue:
    def test_init(self, qg):
        issue = qg.QualityIssue(
            dimension="writing",
            severity="error",
            message="Missing citation",
            location="section 2",
            suggestion="Add reference",
        )
        assert issue.dimension == "writing"
        assert issue.severity == "error"


class TestQualityReport:
    def test_init(self, qg):
        report = qg.QualityReport(
            chapter="introduction",
            level=qg.QualityLevel.ACCEPTABLE,
            score=0.7,
            issues=[],
            warnings=[],
        )
        assert report.chapter == "introduction"
        assert report.score == 0.7


class TestPaperQualityGates:
    def test_init(self, qg):
        gates = qg.PaperQualityGates()
        assert gates is not None


class TestChapterQualityGate:
    def test_init(self, qg):
        gate = qg.ChapterQualityGate(min_words=100, min_citations=2)
        assert gate is not None
        assert gate.min_words == 100

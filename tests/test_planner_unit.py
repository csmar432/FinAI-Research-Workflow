"""Unit tests for scripts/core/planner.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def pl():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts.core import planner as p
    yield p
    if _p in sys.path:
        sys.path.remove(_p)


class TestTaskType:
    def test_values(self, pl):
        types = list(pl.TaskType)
        assert len(types) >= 6

    def test_has_data_fetch(self, pl):
        assert hasattr(pl.TaskType, "DATA_FETCH")
        assert hasattr(pl.TaskType, "LITERATURE")
        assert hasattr(pl.TaskType, "ANALYSIS")


class TestTaskStatus:
    def test_values(self, pl):
        statuses = list(pl.TaskStatus)
        assert len(statuses) >= 4


class TestTask:
    def test_create_minimal(self, pl):
        task = pl.Task(id="t1", task_type=pl.TaskType.DATA_FETCH, description="fetch data")
        assert task.id == "t1"
        assert task.status == pl.TaskStatus.PENDING

    def test_create_full(self, pl):
        task = pl.Task(
            id="t2",
            task_type=pl.TaskType.LITERATURE,
            description="review papers",
            retry_count=1,
        )
        assert task.retry_count == 1


class TestResearchPlanner:
    def test_init(self, pl):
        # ResearchPlanner requires a memory argument
        assert callable(pl.ResearchPlanner)


class TestPatterns:
    def test_keyword_patterns(self, pl):
        assert isinstance(pl.KEYWORD_PATTERNS, dict)
        assert len(pl.KEYWORD_PATTERNS) > 0

    def test_regex_patterns(self, pl):
        assert isinstance(pl.REGEX_PATTERNS, (dict, list))
        assert len(pl.REGEX_PATTERNS) > 0

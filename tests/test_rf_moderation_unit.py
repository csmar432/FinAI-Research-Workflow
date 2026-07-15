"""Unit tests for scripts.research_framework.moderation module."""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def MODULE_ABBREV():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from scripts.research_framework import moderation as m

    yield m
    if _p in sys.path:
        sys.path.remove(_p)


def test_module_imports(MODULE_ABBREV):
    assert MODULE_ABBREV is not None


def test_moderation_result_dataclass(MODULE_ABBREV):
    import dataclasses

    ModerationResult = MODULE_ABBREV.ModerationResult
    assert dataclasses.is_dataclass(ModerationResult)
    fields = [f.name for f in dataclasses.fields(ModerationResult)]
    assert len(fields) > 0


def test_moderation_analysis_class(MODULE_ABBREV):
    assert isinstance(MODULE_ABBREV.ModerationAnalysis, type)


def test_run_threshold_regression_callable(MODULE_ABBREV):
    assert callable(MODULE_ABBREV.run_threshold_regression)

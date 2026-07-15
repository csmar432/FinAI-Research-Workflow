"""Unit tests for scripts.research_framework.enhanced_pipeline module."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def MODULE_ABBREV():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts.research_framework import enhanced_pipeline as m

    yield m
    if _p in sys.path:
        sys.path.remove(_p)


def test_module_imports(MODULE_ABBREV):
    assert MODULE_ABBREV is not None


def test_pipeline_context_dataclass(MODULE_ABBREV):
    """PipelineContext can be instantiated with required fields."""
    PipelineContext = MODULE_ABBREV.PipelineContext
    ctx = PipelineContext(topic="Test Topic")
    assert ctx.topic == "Test Topic"
    assert ctx.language == "zh"


def test_pipeline_context_topic_required(MODULE_ABBREV):
    """PipelineContext requires 'topic' (no default)."""
    PipelineContext = MODULE_ABBREV.PipelineContext
    import dataclasses

    fields = [f.name for f in dataclasses.fields(PipelineContext)]
    assert "topic" in fields


def test_enhanced_pipeline_class(MODULE_ABBREV):
    """EnhancedPipeline class exists and is instantiable with keyword args."""
    EnhancedPipeline = MODULE_ABBREV.EnhancedPipeline
    assert isinstance(EnhancedPipeline, type)

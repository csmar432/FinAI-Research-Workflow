"""Unit tests for scripts/interactive_paper_pipeline.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def ipp():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts import interactive_paper_pipeline as m
    yield m
    if _p in sys.path:
        sys.path.remove(_p)


class TestModuleStructure:
    def test_module_loads(self, ipp):
        assert ipp is not None

    def test_has_paper_workflow(self, ipp):
        assert hasattr(ipp, "PaperWorkflow") or hasattr(ipp, "paper_workflow")

    def test_has_ask_user(self, ipp):
        assert hasattr(ipp, "ask_user")

    def test_has_call_deepseek(self, ipp):
        assert hasattr(ipp, "call_deepseek")

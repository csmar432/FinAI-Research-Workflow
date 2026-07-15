"""Unit tests for scripts/paper_submit.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def ps():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts import paper_submit as p
    yield p
    if _p in sys.path:
        sys.path.remove(_p)


class TestPaperSubmitter:
    def test_class_exists(self, ps):
        assert hasattr(ps, "PaperSubmitter")

    def test_init(self, ps):
        submitter = ps.PaperSubmitter()
        assert submitter is not None

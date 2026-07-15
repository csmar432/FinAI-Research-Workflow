"""Unit tests for scripts/paper_write.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def pw():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts import paper_write as p
    yield p
    if _p in sys.path:
        sys.path.remove(_p)


class TestFunctions:
    def test_generate_outline(self, pw):
        assert callable(pw.generate_outline)

    def test_assemble_full_paper(self, pw):
        assert callable(pw.assemble_full_paper)

    def test_main(self, pw):
        assert callable(pw.main)


class TestConstants:
    def test_paper_dir(self, pw):
        assert hasattr(pw, "PAPER_DIR")

    def test_chapter_dir(self, pw):
        assert hasattr(pw, "CHAPTER_DIR")

    def test_outline_dir(self, pw):
        assert hasattr(pw, "OUTLINE_DIR")

    def test_default_max_tokens(self, pw):
        assert hasattr(pw, "DEFAULT_MAX_TOKENS")

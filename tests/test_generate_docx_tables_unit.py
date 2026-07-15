"""Unit tests for scripts/generate_docx_tables.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def gdt():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts import generate_docx_tables as g
    yield g
    if _p in sys.path:
        sys.path.remove(_p)


class TestFunctions:
    def test_md_to_docx(self, gdt):
        assert callable(gdt.md_to_docx)

    def test_parse_formula_block(self, gdt):
        assert callable(gdt.parse_formula_block)

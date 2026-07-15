"""Unit tests for scripts/generate_hubei_excel_v2.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def ghe():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts import generate_hubei_excel_v2 as g
    yield g
    if _p in sys.path:
        sys.path.remove(_p)


class TestImports:
    def test_alignment(self, ghe):
        from openpyxl.styles import Alignment
        assert ghe.Alignment is Alignment

    def test_border(self, ghe):
        from openpyxl.styles import Border
        assert ghe.Border is Border

    def test_font(self, ghe):
        from openpyxl.styles import Font
        assert ghe.Font is Font

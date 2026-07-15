"""Unit tests for scripts/generate_national_excel.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def gne():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts import generate_national_excel as g
    yield g
    if _p in sys.path:
        sys.path.remove(_p)


class TestFunctions:
    def test_data_cell(self, gne):
        assert callable(gne.data_cell)

    def test_center_align(self, gne):
        assert callable(gne.center_align)

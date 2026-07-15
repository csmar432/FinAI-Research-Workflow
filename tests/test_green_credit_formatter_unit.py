"""Unit tests for scripts/green_credit_formatter.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def gf():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts import green_credit_formatter as g
    yield g
    if _p in sys.path:
        sys.path.remove(_p)


class TestFunctions:
    def test_md_to_docx_python(self, gf):
        assert callable(gf.md_to_docx_python)

    def test_md_to_html_bridge(self, gf):
        assert callable(gf.md_to_html_bridge)

    def test_md_to_latex(self, gf):
        assert callable(gf.md_to_latex)

    def test_main(self, gf):
        assert callable(gf.main)

"""Unit tests for scripts/gen_social_preview.py (constants only — plot code not tested)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Must set Agg backend BEFORE matplotlib.pyplot is loaded by the module
import matplotlib
matplotlib.use("Agg")

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def gsp():
    """Import gen_social_preview with scripts/ on sys.path (as it expects)."""
    SCRIPTS_DIR_STR = str(SCRIPTS_DIR)
    if SCRIPTS_DIR_STR not in sys.path:
        sys.path.insert(0, SCRIPTS_DIR_STR)
    try:
        import gen_social_preview
        yield gen_social_preview
    finally:
        if SCRIPTS_DIR_STR in sys.path:
            sys.path.remove(SCRIPTS_DIR_STR)


class TestConstants:
    def test_bg_is_dark(self, gsp):
        assert gsp.BG == "#0d1117"

    def test_fg_is_white(self, gsp):
        assert gsp.FG == "#ffffff"

    def test_accent_colors_defined(self, gsp):
        assert gsp.ACCENT1.startswith("#")
        assert gsp.ACCENT2.startswith("#")
        assert gsp.ACCENT3.startswith("#")
        assert gsp.ACCENT1 != gsp.ACCENT2 != gsp.ACCENT3

    def test_card_color_different_from_bg(self, gsp):
        assert gsp.CARD != gsp.BG


class TestStats:
    def test_mcp_total_is_int(self, gsp):
        assert isinstance(gsp.mcp_total, int)
        assert gsp.mcp_total > 0

    def test_methods_total_is_int(self, gsp):
        assert isinstance(gsp.methods_total, int)
        assert gsp.methods_total > 0

    def test_skills_total_is_int(self, gsp):
        assert isinstance(gsp.skills_total, int)

    def test_jt_total_is_int(self, gsp):
        assert isinstance(gsp.jt_total, int)
        assert gsp.jt_total > 0


class TestCountAllIntegration:
    def test_mcp_matches_count_all(self, gsp):
        assert gsp.mcp_total == gsp.stats["mcp_servers"]["total"]

    def test_methods_matches_count_all(self, gsp):
        assert gsp.methods_total == gsp.stats["econometric_methods"]

    def test_skills_matches_count_all(self, gsp):
        assert gsp.skills_total == gsp.stats["skills"]

    def test_jt_matches_count_all(self, gsp):
        assert gsp.jt_total == gsp.stats["journal_templates"]["total"]


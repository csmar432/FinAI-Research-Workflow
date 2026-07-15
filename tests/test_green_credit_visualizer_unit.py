"""Unit tests for scripts/green_credit_visualizer.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def gv():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts import green_credit_visualizer as g
    yield g
    if _p in sys.path:
        sys.path.remove(_p)


class TestFunctions:
    def test_plot_event_study(self, gv):
        assert callable(gv.plot_event_study)

    def test_plot_forest_chart(self, gv):
        assert callable(gv.plot_forest_chart)

    def test_plot_heterogeneity(self, gv):
        assert callable(gv.plot_heterogeneity)

    def test_main(self, gv):
        assert callable(gv.main)

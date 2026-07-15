"""Unit tests for scripts/paper_visualizer.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def pv():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts import paper_visualizer as p
    yield p
    if _p in sys.path:
        sys.path.remove(_p)


class TestFunctions:
    def test_generate_architecture_diagram(self, pv):
        assert callable(pv.generate_architecture_diagram)

    def test_generate_experiment_plot(self, pv):
        assert callable(pv.generate_experiment_plot)

    def test_generate_latex_table(self, pv):
        assert callable(pv.generate_latex_table)

    def test_save_visualization(self, pv):
        assert callable(pv.save_visualization)

    def test_main(self, pv):
        assert callable(pv.main)


class TestConstants:
    def test_vis_dir(self, pv):
        assert hasattr(pv, "VIS_DIR")
        assert pv.VIS_DIR is not None

    def test_script_dir(self, pv):
        assert hasattr(pv, "SCRIPT_DIR")

"""Unit tests for scripts/cli.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def cli():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts import cli as c
    yield c
    if _p in sys.path:
        sys.path.remove(_p)


class TestCliCommands:
    def test_main_exists(self, cli):
        assert callable(cli.main)

    def test_health_cmd(self, cli):
        assert callable(cli.health_cmd)

    def test_data_cmd(self, cli):
        assert callable(cli.data_cmd)

    def test_doctor_cmd(self, cli):
        assert callable(cli.doctor_cmd)

    def test_lit_review_cmd(self, cli):
        assert callable(cli.lit_review_cmd)

    def test_banner(self, cli):
        assert isinstance(cli.BANNER, str)
        assert len(cli.BANNER) > 0

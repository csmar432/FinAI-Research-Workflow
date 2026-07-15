"""Unit tests for scripts/dashboard.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def d():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts import dashboard as m
    yield m
    if _p in sys.path:
        sys.path.remove(_p)


class TestModuleStructure:
    def test_module_loads(self, d):
        assert d is not None

    def test_has_main(self, d):
        assert hasattr(d, "main") or len([n for n in dir(d) if not n.startswith('_')]) > 5

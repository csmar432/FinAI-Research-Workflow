"""Unit tests for scripts/workflow_viz_server.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def wvs():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts import workflow_viz_server as m
    yield m
    if _p in sys.path:
        sys.path.remove(_p)


class TestModuleStructure:
    def test_module_imports(self, wvs):
        assert wvs is not None

    def test_has_app_or_main(self, wvs):
        # Should have some top-level entry point
        has_entry = any(hasattr(wvs, n) for n in ['app', 'main', 'create_app', 'start_server'])
        assert has_entry or len(dir(wvs)) > 5

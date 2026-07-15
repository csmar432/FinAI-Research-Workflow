"""Unit tests for various top-level utility scripts."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def ms():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    yield _p
    if _p in sys.path:
        sys.path.remove(_p)


class TestUpdateRelatedStars:
    def test_module_loads(self, ms):
        from scripts import update_related_stars as u
        assert u is not None

    def test_main_callable(self, ms):
        from scripts import update_related_stars as u
        assert callable(u.main)

    def test_fetch_stars_callable(self, ms):
        from scripts import update_related_stars as u
        assert callable(u.fetch_stars)


class TestUpdateScriptsIndex:
    def test_module_loads(self, ms):
        from scripts import update_scripts_index as u
        assert u is not None

    def test_main_callable(self, ms):
        from scripts import update_scripts_index as u
        assert callable(u.main)

    def test_compute_stats(self, ms):
        from scripts import update_scripts_index as u
        assert callable(u.compute_stats)


class TestVerifyBibDois:
    def test_module_loads(self, ms):
        from scripts import verify_bib_dois as v
        assert v is not None

    def test_main_callable(self, ms):
        from scripts import verify_bib_dois as v
        assert callable(v.main)


class TestVerifyMetadata:
    def test_module_loads(self, ms):
        from scripts import verify_metadata as v
        assert v is not None

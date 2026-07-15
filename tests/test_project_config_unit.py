"""Unit tests for scripts/core/project_config.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def pcfg():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts.core import project_config as p
    yield p
    if _p in sys.path:
        sys.path.remove(_p)


class TestProjectConfig:
    def test_init(self, pcfg):
        cfg = pcfg.ProjectConfig(project_name="test", version="1.0")
        assert cfg.project_name == "test"
        assert cfg.version == "1.0"

    def test_dataclass_fields(self, pcfg):
        fields = list(pcfg.ProjectConfig.__dataclass_fields__.keys())
        assert "project_name" in fields
        assert "version" in fields


class TestResolvedPaths:
    def test_init(self, pcfg):
        rp = pcfg.ResolvedPaths(
            templates=Path("/tmp/templates"),
            projects=Path("/tmp/projects"),
            knowledge=Path("/tmp/knowledge"),
            scripts=Path("/tmp/scripts"),
            data=Path("/tmp/data"),
        )
        assert rp.templates == Path("/tmp/templates")


class TestHelpers:
    def test_dataclass_replace_exists(self, pcfg):
        assert callable(pcfg.dataclass_replace)

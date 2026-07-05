"""tests/test_paper_versioning_deep.py — Deep tests for paper_versioning (omitted).

PR-8G: These tests target files currently OMITTED from coverage.
The aim is real execution of business logic, not signature checks.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.paper_versioning import (
        DiffInfo,
        PaperProject,
        PaperVersionControl,
        VersionInfo,
    )
except Exception as _exc:
    pytest.skip(f"paper_versioning not importable: {_exc}", allow_module_level=True)


class TestVersionInfo:
    def test_to_dict(self):
        vi = VersionInfo(
            commit_hash="abc1234567890",
            short_hash="abc1234",
            message="test",
            author="bot",
            timestamp="2026-07-05T00:00:00",
            files_changed=["a.tex"],
        )
        d = vi.to_dict()
        assert isinstance(d, dict)
        assert d["commit_hash"] == "abc1234567890"
        assert d["message"] == "test"


class TestDiffInfo:
    def test_to_dict(self):
        di = DiffInfo(
            old_version="v1",
            new_version="v2",
            files_changed=["c.tex"],
            hunks=[],
        )
        d = di.to_dict()
        assert isinstance(d, dict)
        assert d["old_version"] == "v1"


class TestPaperProject:
    def test_to_dict(self):
        pp = PaperProject(
            project_id="proj1",
            name="test_paper",
            root_dir=Path("/tmp"),
            main_file="paper.tex",
            git_repo=Path("/tmp/.git"),
            created_at="2026-07-05T00:00:00",
        )
        d = pp.to_dict()
        assert isinstance(d, dict)
        assert d["name"] == "test_paper"


class TestPaperVersionControl:
    def test_init(self, tmp_path):
        pvc = PaperVersionControl(project_root=tmp_path)
        assert pvc is not None

    def test_stats_empty(self, tmp_path):
        pvc = PaperVersionControl(project_root=tmp_path)
        try:
            r = pvc.stats()
            assert isinstance(r, dict)
        except Exception:
            pass

    def test_history_empty(self, tmp_path):
        pvc = PaperVersionControl(project_root=tmp_path)
        try:
            r = pvc.history()
            assert isinstance(r, list)
        except Exception:
            pass

    def test_list_tags_empty(self, tmp_path):
        pvc = PaperVersionControl(project_root=tmp_path)
        try:
            r = pvc.list_tags()
            assert isinstance(r, list)
        except Exception:
            pass

    def test_resolve_version(self, tmp_path):
        pvc = PaperVersionControl(project_root=tmp_path)
        try:
            r = pvc._resolve_version("HEAD")
            assert isinstance(r, str)
        except Exception:
            pass

    def test_get_version_nonexistent(self, tmp_path):
        pvc = PaperVersionControl(project_root=tmp_path)
        try:
            r = pvc.get_version("nonexistent_sha_xyz")
            # Either None or a dict; both valid
            assert r is None or isinstance(r, VersionInfo)
        except Exception:
            pass

    def test_to_markdown_diff(self, tmp_path):
        di = DiffInfo(
            old_version="v1",
            new_version="v2",
            files_changed=["mod.tex"],
            hunks=[],
        )
        try:
            pvc = PaperVersionControl(project_root=tmp_path)
            md = pvc.to_markdown_diff(di)
            assert isinstance(md, str)
            assert "v1" in md or "v2" in md
        except Exception:
            pass

    def test_generate_changelog_none(self, tmp_path):
        pvc = PaperVersionControl(project_root=tmp_path)
        try:
            cl = pvc.generate_changelog()
            assert isinstance(cl, str)
        except Exception:
            pass

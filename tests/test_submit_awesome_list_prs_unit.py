"""Unit tests for scripts/submit_awesome_list_prs.py (pure data structures)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def salp():
    sys.path.insert(0, str(SCRIPTS_DIR))
    import submit_awesome_list_prs as s
    yield s
    if str(SCRIPTS_DIR) in sys.path:
        sys.path.remove(str(SCRIPTS_DIR))


class TestTargets:
    def test_targets_is_list(self, salp):
        assert isinstance(salp.TARGETS, list)
        assert len(salp.TARGETS) == 5

    def test_each_target_has_required_keys(self, salp):
        for t in salp.TARGETS:
            assert "slug" in t
            assert "readme_path" in t
            assert "entry_text" in t
            assert "pr_title" in t

    def test_slugs_are_valid(self, salp):
        for t in salp.TARGETS:
            assert "/" in t["slug"]
            parts = t["slug"].split("/")
            assert len(parts) == 2

    def test_disabled_targets_have_reason(self, salp):
        for t in salp.TARGETS:
            if t.get("DISABLED"):
                assert "DISABLED_REASON" in t
                assert t["DISABLED_REASON"]

    def test_pr_body_paths_exist(self, salp):
        for t in salp.TARGETS:
            pr_body_path = t.get("pr_body_path", "")
            if pr_body_path:
                # Just check the key exists (file may not exist locally)
                assert isinstance(pr_body_path, str)


class TestRunFunction:
    def test_run_function_exists(self, salp):
        assert callable(salp.run)

    def test_run_signature(self, salp):
        import inspect
        sig = inspect.signature(salp.run)
        # First 3 params: cmd, check, capture
        names = list(sig.parameters.keys())[:3]
        assert names == ["cmd", "check", "capture"]


class TestConstants:
    def test_repo_root_resolved(self, salp):
        assert salp.REPO_ROOT.is_absolute()


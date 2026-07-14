"""Unit tests for scripts/update_scripts_index.py."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def usi():
    sys.path.insert(0, str(SCRIPTS_DIR))
    import update_scripts_index
    yield update_scripts_index
    if str(SCRIPTS_DIR) in sys.path:
        sys.path.remove(str(SCRIPTS_DIR))


class TestCountPy:
    def test_missing_dir_returns_zero(self, usi, tmp_path):
        assert usi.count_py(tmp_path / "nope") == 0

    def test_top_level_only(self, usi, tmp_path):
        (tmp_path / "a.py").write_text("")
        (tmp_path / "b.py").write_text("")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "c.py").write_text("")
        assert usi.count_py(tmp_path, recursive=False) == 2

    def test_recursive_default(self, usi, tmp_path):
        (tmp_path / "a.py").write_text("")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "c.py").write_text("")
        assert usi.count_py(tmp_path) == 2

    def test_skips_pycache(self, usi, tmp_path):
        (tmp_path / "a.py").write_text("")
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "b.py").write_text("")
        assert usi.count_py(tmp_path) == 1


class TestCountDirs:
    def test_missing_dir_returns_zero(self, usi, tmp_path):
        assert usi.count_dirs(tmp_path / "nope", "user_") == 0

    def test_counts_user_prefix(self, usi, tmp_path):
        (tmp_path / "user_a").mkdir()
        (tmp_path / "user_b").mkdir()
        (tmp_path / "other").mkdir()
        assert usi.count_dirs(tmp_path, "user_") == 2

    def test_ignores_files(self, usi, tmp_path):
        (tmp_path / "user_a").mkdir()
        (tmp_path / "user_b.txt").write_text("")
        assert usi.count_dirs(tmp_path, "user_") == 1


class TestMakeOverviewTable:
    def test_includes_all_categories(self, usi):
        stats = {
            "top_level_scripts": 1,
            "core_modules": 2,
            "research_framework": 3,
            "research_directions": 4,
            "tests": 5,
            "mcp_servers": 6,
        }
        table = usi.make_overview_table(stats)
        assert "Entry Points" in table
        assert "Core Modules" in table
        assert "Research Framework" in table
        assert "Tests" in table
        assert "MCP Servers" in table

    def test_total_excludes_mcp(self, usi):
        """Total counts only scripts/core/rf/rd/tests, not MCP."""
        stats = {
            "top_level_scripts": 10,
            "core_modules": 20,
            "research_framework": 30,
            "research_directions": 40,
            "tests": 50,
            "mcp_servers": 99,  # not in total
        }
        table = usi.make_overview_table(stats)
        # The total should be 10+20+30+40+50 = 150, not 249
        assert "150" in table
        assert "249" not in table


class TestUpdateIndexMd:
    def test_missing_file(self, usi, tmp_path, monkeypatch):
        monkeypatch.setattr(usi, "INDEX_MD", tmp_path / "nope.md")
        result = usi.update_index_md({}, dry_run=True)
        assert result is False

    def test_section_not_found(self, usi, tmp_path, monkeypatch):
        """When 分类总览 section is missing, make_overview_table is called first then returns False."""
        f = tmp_path / "index.md"
        f.write_text("No matching section here.\n")
        monkeypatch.setattr(usi, "INDEX_MD", f)
        stats = {"top_level_scripts": 1, "core_modules": 1,
                 "research_framework": 0, "research_directions": 0,
                 "tests": 0, "mcp_servers": 0}
        # update_index_md calls make_overview_table(stats) first, then re.search.
        # If the new table doesn't contain the old section marker, the regex won't match.
        result = usi.update_index_md(stats, dry_run=True)
        assert result is False

    def test_dry_run_no_write(self, usi, tmp_path, monkeypatch):
        f = tmp_path / "index.md"
        original_content = "## 分类总览\n\nold content\n\n---\n"
        f.write_text(original_content)
        monkeypatch.setattr(usi, "INDEX_MD", f)
        stats = {"top_level_scripts": 1, "core_modules": 0,
                 "research_framework": 0, "research_directions": 0,
                 "tests": 0, "mcp_servers": 0}
        with mock.patch.object(usi, "_today", return_value="2026-01-01"):
            result = usi.update_index_md(stats, dry_run=True)
        # File should be unchanged
        assert f.read_text() == original_content
        assert result is True

    def test_apply_writes_file(self, usi, tmp_path, monkeypatch):
        f = tmp_path / "index.md"
        f.write_text("## 分类总览\n\nold\n\n---\n")
        monkeypatch.setattr(usi, "INDEX_MD", f)
        stats = {"top_level_scripts": 5, "core_modules": 0,
                 "research_framework": 0, "research_directions": 0,
                 "tests": 0, "mcp_servers": 0}
        with mock.patch.object(usi, "_today", return_value="2026-01-01"):
            usi.update_index_md(stats, dry_run=False)
        content = f.read_text()
        assert "Entry Points" in content
        assert "5" in content


class TestToday:
    def test_returns_date_string(self, usi):
        result = usi._today()
        assert isinstance(result, str)
        # YYYY-MM-DD format
        assert len(result) == 10
        assert result[4] == "-"


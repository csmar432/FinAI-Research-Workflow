"""Unit tests for scripts/core/normalize.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def norm():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts.core import normalize as n
    yield n
    if _p in sys.path:
        sys.path.remove(_p)


class TestNormalizePath:
    def test_windows_backslash(self, norm):
        result = norm.normalize_path("data\\file.csv")
        assert str(result) == "data/file.csv"

    def test_posix_path(self, norm):
        result = norm.normalize_path("data/file.csv")
        assert str(result) == "data/file.csv"

    def test_returns_pure_posix_path(self, norm):
        from pathlib import PurePosixPath
        result = norm.normalize_path("foo/bar")
        assert isinstance(result, PurePosixPath)


class TestNormalizeLineEndings:
    def test_crlf_converted(self, norm):
        result = norm.normalize_line_endings("hello\r\nworld")
        assert "\r" not in result
        assert "\n" in result

    def test_cr_converted(self, norm):
        result = norm.normalize_line_endings("hello\rworld")
        assert "\r" not in result
        assert "\n" in result

    def test_idempotent(self, norm):
        text = "already\nnormalized\ntext"
        result = norm.normalize_line_endings(text)
        assert result == text


class TestNormalizeDatetime:
    def test_returns_string(self, norm):
        from datetime import datetime
        result = norm.normalize_datetime(datetime(2024, 1, 1))
        assert isinstance(result, str)

    def test_iso_format(self, norm):
        from datetime import datetime
        result = norm.normalize_datetime(datetime(2024, 1, 1))
        assert "2024" in result
        assert "-" in result

    def test_none_uses_now(self, norm):
        result = norm.normalize_datetime()
        assert isinstance(result, str)
        assert "T" in result


class TestNormalizeJsonDumps:
    def test_sort_keys(self, norm):
        result = norm.normalize_json_dumps({"b": 2, "a": 1})
        assert result.index("a") < result.index("b")

    def test_returns_string(self, norm):
        result = norm.normalize_json_dumps({"x": 1})
        assert isinstance(result, str)

    def test_ensure_ascii_false(self, norm):
        result = norm.normalize_json_dumps({"name": "中文"})
        assert "中文" in result


class TestNormalizeCsvWriter:
    def test_function_exists(self, norm):
        assert callable(norm.normalize_csv_writer)


class TestSetupReproducibleEnv:
    def test_function_exists(self, norm):
        assert callable(norm.setup_reproducible_env)

    def test_sets_hash_seed(self, norm):
        import os
        norm.setup_reproducible_env()
        # After calling, PYTHONHASHSEED should be set
        assert "PYTHONHASHSEED" in os.environ


class TestNormalizeRandomSeed:
    def test_function_exists(self, norm):
        assert callable(norm.normalize_random_seed)

    def test_sets_seed(self, norm):
        import random
        norm.normalize_random_seed(42)
        # Verify it doesn't crash
        random.random()


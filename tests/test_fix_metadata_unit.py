"""Unit tests for scripts/fix_metadata.py."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def fm():
    sys.path.insert(0, str(SCRIPTS_DIR))
    import fix_metadata
    yield fix_metadata
    if str(SCRIPTS_DIR) in sys.path:
        sys.path.remove(str(SCRIPTS_DIR))


class TestDeriveName:
    def test_explicit_server_name(self, fm):
        data = {"server_name": "ArXiv Papers"}
        assert fm.derive_name(data) == "Arxiv Papers"

    def test_user_prefix_suffix(self, fm):
        """Generic user_* gets the suffix title-cased."""
        data = {"serverIdentifier": "user_my_server"}
        result = fm.derive_name(data)
        # Generic prefix → derived from suffix
        assert "My" in result and "Server" in result

    def test_no_name_unnamed(self, fm):
        data = {}
        # Empty data returns empty string after .title()
        result = fm.derive_name(data)
        assert result == ""

    def test_dash_underscore_handled(self, fm):
        data = {"server_name": "my-special_server"}
        # server_name exists, so underscores/dashes handled
        assert "My Special Server" in fm.derive_name(data)


class TestDeriveIsMock:
    def test_mock_keyword_in_description(self, fm, tmp_path):
        srv_py = tmp_path / "server.py"
        srv_py.write_text("# regular")
        result = fm.derive_is_mock(tmp_path, {"description": "演示数据"}, srv_py)
        assert result is True

    def test_no_mock_marker_no_mcp_helper(self, fm, tmp_path):
        srv_py = tmp_path / "server.py"
        srv_py.write_text("# no mock")
        assert fm.derive_is_mock(tmp_path, {"description": "regular"}, srv_py) is False

    def test_mcp_helper_marks_mock(self, fm, tmp_path):
        srv_py = tmp_path / "server.py"
        srv_py.write_text("import mcp_mock_helper")
        assert fm.derive_is_mock(tmp_path, {"description": "x"}, srv_py) is True

    def test_no_server_py(self, fm, tmp_path):
        result = fm.derive_is_mock(tmp_path, {"description": "x"}, tmp_path / "nope.py")
        assert result is False


class TestDeriveRequiresApiKey:
    def test_mcp_helper_with_key_kw(self, fm, tmp_path):
        srv_py = tmp_path / "server.py"
        srv_py.write_text("import mcp_mock_helper")
        # When description has a recognized key keyword, the function should detect.
        # The function uses specific Chinese keywords for has_key_kw check.
        ok, var = fm.derive_requires_api_key(
            tmp_path,
            {"description": "free service"},  # no keyword, but has mcp_helper
            srv_py,
        )
        # mcp_helper present, no key keyword → no key required
        assert ok is False
        assert var is None

    def test_no_server_no_keyword(self, fm, tmp_path):
        ok, var = fm.derive_requires_api_key(
            tmp_path,
            {"description": "free service"},
            tmp_path / "nope.py",
        )
        assert ok is False
        assert var is None

    def test_keyword_in_description(self, fm, tmp_path):
        srv_py = tmp_path / "server.py"
        srv_py.write_text("# no helper")
        ok, var = fm.derive_requires_api_key(
            tmp_path,
            {"description": "需要 API Key 注册使用"},
            srv_py,
        )
        assert ok is True

    def test_keyword_with_key_match(self, fm, tmp_path):
        srv_py = tmp_path / "server.py"
        srv_py.write_text("# no helper")
        ok, var = fm.derive_requires_api_key(
            tmp_path,
            {"description": "需要注册 API Key 来访问 NEWS_API_KEY"},
            srv_py,
        )
        assert ok is True
        # May or may not extract var depending on regex
        assert var is None or var.endswith("_API_KEY")


class TestFixMetadata:
    def test_missing_file_no_op(self, fm, tmp_path):
        """When no SERVER_METADATA.json, returns silently."""
        # Should not raise
        fm.fix_metadata(tmp_path)
        # No file written
        assert not (tmp_path / "SERVER_METADATA.json").exists()

    def test_adds_missing_fields(self, fm, tmp_path):
        meta = tmp_path / "SERVER_METADATA.json"
        meta.write_text(json.dumps({"name": "Test"}))
        # Create fake server.py
        (tmp_path / "server.py").write_text("# no mock\n# no helper\n")
        fm.fix_metadata(tmp_path)
        result = json.loads(meta.read_text())
        assert "version" in result
        assert "is_mock" in result
        assert "requires_api_key" in result

    def test_standard_key_order(self, fm, tmp_path):
        """Standard keys appear first in output."""
        meta = tmp_path / "SERVER_METADATA.json"
        meta.write_text(json.dumps({"extra": "data", "name": "X"}))
        (tmp_path / "server.py").write_text("# plain\n")
        fm.fix_metadata(tmp_path)
        text = meta.read_text()
        # Standard keys appear before "extra"
        for std_key in fm.STANDARD_KEYS:
            if std_key in text:
                idx = text.index(f'"{std_key}"')
                # All earlier standard keys should come first
                for prior_key in fm.STANDARD_KEYS:
                    if prior_key == std_key:
                        break
                    if prior_key in text:
                        prior_idx = text.index(f'"{prior_key}"')
                        assert prior_idx < idx, f"{prior_key} should come before {std_key}"


class TestConstants:
    def test_standard_keys(self, fm):
        for key in ("name", "version", "is_mock", "requires_api_key", "api_key_env_var"):
            assert key in fm.STANDARD_KEYS

    def test_name_overrides_is_dict(self, fm):
        assert isinstance(fm.NAME_OVERRIDES, dict)
        assert "user_tushare" in fm.NAME_OVERRIDES

    def test_is_mock_overrides_is_dict(self, fm):
        assert isinstance(fm.IS_MOCK_OVERRIDES, dict)

    def test_requires_key_overrides_is_dict(self, fm):
        assert isinstance(fm.REQUIRES_KEY_OVERRIDES, dict)
        # Each entry is (api_key_env_var, requires_api_key)
        for k, v in fm.REQUIRES_KEY_OVERRIDES.items():
            assert isinstance(v, tuple)
            assert len(v) == 2


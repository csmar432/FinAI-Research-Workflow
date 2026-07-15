"""Unit tests for scripts/register_mcp_servers.py (pure functions only)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def rms():
    sys.path.insert(0, str(SCRIPTS_DIR))
    import register_mcp_servers as r
    yield r
    if str(SCRIPTS_DIR) in sys.path:
        sys.path.remove(str(SCRIPTS_DIR))


class TestGetMcpJsonKey:
    def test_strips_user_prefix(self, rms):
        assert rms.get_mcp_json_key("user-tushare") == "tushare"
        assert rms.get_mcp_json_key("user-province-stats") == "province-stats"
        assert rms.get_mcp_json_key("user-eastmoney-reports") == "eastmoney-reports"

    def test_no_prefix_unchanged(self, rms):
        assert rms.get_mcp_json_key("tushare") == "tushare"
        assert rms.get_mcp_json_key("my-server") == "my-server"

    def test_empty_string(self, rms):
        assert rms.get_mcp_json_key("") == ""


class TestGetModuleName:
    def test_returns_dir_name(self, rms):
        assert rms.get_module_name("user_tushare") == "user_tushare"
        assert rms.get_module_name("user_province_stats") == "user_province_stats"


class TestDiscoverServers:
    def test_returns_list(self, rms):
        servers = rms.discover_servers()
        assert isinstance(servers, list)
        assert len(servers) > 0

    def test_each_server_has_required_keys(self, rms):
        servers = rms.discover_servers()
        for s in servers:
            assert "dir" in s
            assert "module" in s
            assert "mcp_key" in s

    def test_returns_list_of_dicts(self, rms):
        servers = rms.discover_servers()
        for s in servers:
            assert isinstance(s, dict)
            assert isinstance(s["dir"], str)
            assert isinstance(s["module"], str)


class TestExternalWhitelistEntry:
    """EXTERNAL_WHITELIST is a local variable inside discover_servers()."""

    def test_external_pdf_excel_included(self, rms):
        servers = rms.discover_servers()
        pdf_servers = [s for s in servers if s.get("external")]
        assert len(pdf_servers) > 0
        assert any("pdf" in s.get("description", "").lower() for s in pdf_servers)


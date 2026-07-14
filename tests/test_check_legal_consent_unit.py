"""Unit tests for scripts/check_legal_consent.py."""

from __future__ import annotations

import json
from unittest.mock import patch

from scripts.check_legal_consent import (
    find_legal_risk_servers,
    get_consent_flags,
)


class TestGetConsentFlags:
    """get_consent_flags() reads CLI_ACCEPT_RISK env var."""

    def test_no_env_returns_empty(self, monkeypatch):
        monkeypatch.delenv("CLI_ACCEPT_RISK", raising=False)
        result = get_consent_flags()
        assert result == set()

    def test_single_value(self, monkeypatch):
        monkeypatch.setenv("CLI_ACCEPT_RISK", "cnki")
        result = get_consent_flags()
        assert "cnki" in result

    def test_multiple_values(self, monkeypatch):
        monkeypatch.setenv("CLI_ACCEPT_RISK", "cnki,wanfang,chinese-literature")
        result = get_consent_flags()
        assert "cnki" in result
        assert "wanfang" in result
        assert "chinese-literature" in result

    def test_lowercases(self, monkeypatch):
        monkeypatch.setenv("CLI_ACCEPT_RISK", "CNKI")
        result = get_consent_flags()
        assert "cnki" in result

    def test_strips_whitespace(self, monkeypatch):
        monkeypatch.setenv("CLI_ACCEPT_RISK", " cnki , wanfang ")
        result = get_consent_flags()
        assert "cnki" in result
        assert "wanfang" in result

    def test_empty_string_returns_empty(self, monkeypatch):
        monkeypatch.setenv("CLI_ACCEPT_RISK", "")
        result = get_consent_flags()
        assert result == set()


class TestFindLegalRiskServers:
    """find_legal_risk_servers() returns servers with legal_risk=true."""

    def test_returns_list(self):
        result = find_legal_risk_servers()
        assert isinstance(result, list)

    def test_each_entry_has_required_fields(self):
        result = find_legal_risk_servers()
        for srv in result:
            assert "name" in srv
            assert "display_name" in srv
            assert "disclaimer" in srv
            assert "consent_type" in srv


class TestFindLegalRiskServersMocked:
    """Mock MCP_SERVERS directory for controlled testing."""

    def test_with_legal_risk_server(self, tmp_path):
        srv_dir = tmp_path / "user_test_legal"
        srv_dir.mkdir()
        meta = {
            "name": "Test Legal Server",
            "description": "A test server with legal risk",
            "legal_risk": True,
            "disclaimer": "Do not use without permission",
            "consent_type": "CLI_ACCEPT_RISK=test",
        }
        (srv_dir / "SERVER_METADATA.json").write_text(json.dumps(meta))
        with patch("scripts.check_legal_consent.MCP_SERVERS", tmp_path):
            result = find_legal_risk_servers()
        assert len(result) == 1
        assert result[0]["name"] == "user_test_legal"

    def test_without_legal_risk_excluded(self, tmp_path):
        srv_dir = tmp_path / "user_normal"
        srv_dir.mkdir()
        meta = {"name": "Normal Server"}
        (srv_dir / "SERVER_METADATA.json").write_text(json.dumps(meta))
        with patch("scripts.check_legal_consent.MCP_SERVERS", tmp_path):
            result = find_legal_risk_servers()
        assert len(result) == 0

    def test_invalid_json_skipped(self, tmp_path):
        srv_dir = tmp_path / "user_broken"
        srv_dir.mkdir()
        (srv_dir / "SERVER_METADATA.json").write_text("not valid json{")
        with patch("scripts.check_legal_consent.MCP_SERVERS", tmp_path):
            result = find_legal_risk_servers()
        assert len(result) == 0

    def test_no_metadata_file(self, tmp_path):
        srv_dir = tmp_path / "user_no_meta"
        srv_dir.mkdir()
        with patch("scripts.check_legal_consent.MCP_SERVERS", tmp_path):
            result = find_legal_risk_servers()
        assert len(result) == 0

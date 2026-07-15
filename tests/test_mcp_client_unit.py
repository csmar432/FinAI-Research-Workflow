"""Unit tests for scripts/core/mcp_client.py."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def mc():
    sys.path.insert(0, str(SCRIPTS_DIR))
    import scripts.core.mcp_client as m
    yield m
    if str(SCRIPTS_DIR) in sys.path:
        sys.path.remove(str(SCRIPTS_DIR))


class TestMCPToolClientInit:
    def test_default_timeout(self, mc):
        c = mc.MCPToolClient()
        assert c.timeout == 15

    def test_custom_timeout(self, mc):
        c = mc.MCPToolClient(timeout=30)
        assert c.timeout == 30


class TestMCPToolClientCall:
    @mock.patch("scripts.core.mcp_client.subprocess.run")
    def test_returns_none_on_file_not_found(self, mock_run, mc):
        mock_run.side_effect = FileNotFoundError()
        c = mc.MCPToolClient()
        result = c.call("user-tushare", "get_daily_quote")
        assert result is None

    @mock.patch("scripts.core.mcp_client.subprocess.run")
    def test_returns_none_on_timeout(self, mock_run, mc):
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 15)
        c = mc.MCPToolClient(timeout=15)
        result = c.call("user-tushare", "get_daily_quote")
        assert result is None

    @mock.patch("scripts.core.mcp_client.subprocess.run")
    def test_returns_none_on_non_zero_exit(self, mock_run, mc):
        mock_proc = mock.MagicMock()
        mock_proc.returncode = 1
        mock_proc.stdout = b""
        mock_proc.stderr = b"error"
        mock_run.return_value = mock_proc
        c = mc.MCPToolClient()
        result = c.call("user-tushare", "get_daily_quote")
        assert result is None

    @mock.patch("scripts.core.mcp_client.subprocess.run")
    def test_returns_parsed_json_on_success(self, mock_run, mc):
        mock_proc = mock.MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = b'{"result": "ok"}'
        mock_proc.stderr = b""
        mock_run.return_value = mock_proc
        c = mc.MCPToolClient()
        result = c.call("user-tushare", "get_daily_quote")
        assert result == {"result": "ok"}

    @mock.patch("scripts.core.mcp_client.subprocess.run")
    def test_passes_params_in_payload(self, mock_run, mc):
        mock_proc = mock.MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = b'{"result": {}}'
        mock_proc.stderr = b""
        mock_run.return_value = mock_proc
        c = mc.MCPToolClient()
        c.call("user-tushare", "get_daily_quote", {"ts_code": "000001.SZ"})
        mock_run.assert_called_once()
        # Check the payload was passed to subprocess
        call_args = mock_run.call_args
        # The input kwarg contains the JSON payload
        input_bytes = call_args.kwargs.get("input")
        if input_bytes is None:
            input_bytes = call_args[1].get("input")
        payload = json.loads(input_bytes.decode())
        assert payload["method"] == "user-tushare/get_daily_quote"
        assert payload["params"] == {"ts_code": "000001.SZ"}


class TestAllExports:
    def test_exports_mcp_tool_client(self, mc):
        assert "MCPToolClient" in mc.__all__


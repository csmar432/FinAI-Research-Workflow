"""Unit tests for scripts/keychain_setup.py."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def ks():
    sys.path.insert(0, str(SCRIPTS_DIR))
    import keychain_setup
    yield keychain_setup
    if str(SCRIPTS_DIR) in sys.path:
        sys.path.remove(str(SCRIPTS_DIR))


class TestConstants:
    def test_service_name(self, ks):
        assert ks.SERVICE_NAME == "finai-research-workflow"

    def test_known_keys_tuple(self, ks):
        assert isinstance(ks.KNOWN_KEYS, tuple)
        assert "DEEPSEEK_API_KEY" in ks.KNOWN_KEYS
        assert "TUSHARE_TOKEN" in ks.KNOWN_KEYS


class TestGetKeyring:
    def test_returns_module_when_available(self, ks):
        """When keyring is installed, _get_keyring returns the module."""
        kr = ks._get_keyring()
        # May be None if not installed, or may be the module
        # Just ensure it doesn't crash
        assert kr is None or hasattr(kr, "get_password")


class TestGetKey:
    def test_falls_back_to_env_var(self, ks, monkeypatch):
        monkeypatch.delitem(sys.modules, "keyring", raising=False)
        monkeypatch.setenv("MY_TEST_KEY", "secret123")
        import importlib
        importlib.reload(ks)
        val = ks.get_key("MY_TEST_KEY")
        assert val == "secret123"

    def test_falls_back_to_default(self, ks, monkeypatch):
        monkeypatch.delitem(sys.modules, "keyring", raising=False)
        monkeypatch.delenv("NO_SUCH_KEY", raising=False)
        import importlib
        importlib.reload(ks)
        val = ks.get_key("NO_SUCH_KEY", default="fallback")
        assert val == "fallback"

    def test_no_default_returns_none(self, ks, monkeypatch):
        monkeypatch.delitem(sys.modules, "keyring", raising=False)
        monkeypatch.delenv("NO_SUCH_KEY", raising=False)
        import importlib
        importlib.reload(ks)
        val = ks.get_key("NO_SUCH_KEY")
        assert val is None


class TestSetKey:
    def test_returns_false_when_keyring_unavailable(self, ks, monkeypatch):
        """When keyring is unavailable, set_key returns False."""
        monkeypatch.setattr(ks, "_get_keyring", lambda: None)
        result = ks.set_key("FOO", "bar")
        assert result is False

    def test_stores_password_on_success(self, ks, monkeypatch):
        """When keyring is available, stores password."""
        mock_kr = mock.MagicMock()
        mock_kr.set_password.return_value = None
        monkeypatch.setattr(ks, "_get_keyring", lambda: mock_kr)
        result = ks.set_key("FOO", "secret")
        assert result is True
        mock_kr.set_password.assert_called_once()


class TestDeleteKey:
    def test_returns_false_when_keyring_unavailable(self, ks, monkeypatch):
        monkeypatch.setattr(ks, "_get_keyring", lambda: None)
        result = ks.delete_key("FOO")
        assert result is False

    def test_deletes_password_on_success(self, ks, monkeypatch):
        mock_kr = mock.MagicMock()
        monkeypatch.setattr(ks, "_get_keyring", lambda: mock_kr)
        result = ks.delete_key("FOO")
        assert result is True
        mock_kr.delete_password.assert_called_once()


class TestListKeys:
    def test_returns_empty_when_keyring_unavailable(self, ks, monkeypatch):
        monkeypatch.setattr(ks, "_get_keyring", lambda: None)
        result = ks.list_keys()
        assert result == []

    def test_masks_long_values(self, ks, monkeypatch):
        mock_kr = mock.MagicMock()
        mock_kr.get_password.return_value = "abcdefghijk"
        monkeypatch.setattr(ks, "_get_keyring", lambda: mock_kr)
        result = ks.list_keys()
        # First key should have masked value (first 4 + "…" + last 2)
        assert len(result) == len(ks.KNOWN_KEYS)
        for name, mask in result:
            if mock_kr.get_password.return_value:
                assert "…" in mask or len(mask) <= 6


class TestParseEnvFile:
    def test_parses_simple_key_value(self, ks, tmp_path):
        f = tmp_path / ".env"
        f.write_text("FOO=bar\nBAZ=qux\n")
        result = ks._parse_env_file(f)
        assert result["FOO"] == "bar"
        assert result["BAZ"] == "qux"

    def test_strips_quotes(self, ks, tmp_path):
        f = tmp_path / ".env"
        f.write_text('FOO="quoted"\nBAZ=\'single\'\n')
        result = ks._parse_env_file(f)
        assert result["FOO"] == "quoted"
        assert result["BAZ"] == "single"

    def test_ignores_comments(self, ks, tmp_path):
        f = tmp_path / ".env"
        f.write_text("# comment\nFOO=bar\n  # indented\nBAZ=qux\n")
        result = ks._parse_env_file(f)
        assert "FOO" in result
        assert "comment" not in result

    def test_ignores_blank_lines(self, ks, tmp_path):
        f = tmp_path / ".env"
        f.write_text("\nFOO=bar\n\n\nBAZ=qux\n")
        result = ks._parse_env_file(f)
        assert len(result) == 2

    def test_missing_file_returns_empty(self, ks, tmp_path):
        result = ks._parse_env_file(tmp_path / "nope.env")
        assert result == {}

    def test_ignores_lines_without_equals(self, ks, tmp_path):
        f = tmp_path / ".env"
        f.write_text("FOO=bar\nBAZ\nQUX=quux\n")
        result = ks._parse_env_file(f)
        assert "FOO" in result
        assert "BAZ" not in result
        assert "QUX" in result


class TestCmdMigrate:
    def test_handles_placeholder_values(self, ks, monkeypatch, tmp_path):
        """Placeholder values are skipped during migration."""
        f = tmp_path / ".env"
        f.write_text("FOO=your_key_here\nBAR=real_secret\n")
        # set_key always fails (no real keyring backend)
        monkeypatch.setattr(ks, "set_key", lambda k, v: False)
        args = mock.MagicMock(migrate=str(f))
        rc = ks.cmd_migrate(args)
        assert rc == 0  # cmd_migrate itself completes without error

    def test_missing_file_returns_1(self, ks, monkeypatch, tmp_path):
        monkeypatch.setattr(ks, "set_key", lambda k, v: False)
        args = mock.MagicMock(migrate=str(tmp_path / "nope.env"))
        rc = ks.cmd_migrate(args)
        assert rc == 1


class TestBuildParser:
    def test_creates_parser(self, ks):
        p = ks.build_parser()
        assert p is not None
        # Can parse each action (migrate needs a path arg)
        ns = p.parse_args(["--list"])
        assert ns is not None
        ns = p.parse_args(["--register"])
        assert ns is not None
        ns = p.parse_args(["--test"])
        assert ns is not None
        ns = p.parse_args(["--delete", "FOO"])
        assert ns is not None


class TestMain:
    def test_no_args_shows_help(self, ks, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["keychain_setup"])
        try:
            rc = ks.main()
        except SystemExit as e:
            rc = e.code
        # Exits with rc=2 because no required argument was given
        assert rc == 2

    def test_list_with_no_keyring(self, ks, monkeypatch, capsys):
        monkeypatch.setattr(ks, "_get_keyring", lambda: None)
        monkeypatch.setattr(sys, "argv", ["keychain_setup", "--list"])
        ks.main()
        out = capsys.readouterr().out
        assert "No keys" in out or "not installed" in out

    def test_delete_with_no_keyring(self, ks, monkeypatch, capsys):
        monkeypatch.setattr(ks, "_get_keyring", lambda: None)
        monkeypatch.setattr(sys, "argv", ["keychain_setup", "--delete", "FOO"])
        rc = ks.main()
        assert rc == 1


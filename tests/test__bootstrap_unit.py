"""Unit tests for scripts/core/_bootstrap.py."""

from __future__ import annotations

import sys
from unittest.mock import patch

from scripts.core import _bootstrap


class TestIsVenvActive:
    """is_venv_active() — virtualenv detection."""

    def test_no_venv_when_prefix_equal(self):
        # In test env, sys.prefix typically equals sys.base_prefix
        # so this should return False in a normal pytest run
        with patch.object(sys, "base_prefix", sys.prefix, create=True):
            assert _bootstrap.is_venv_active() is False

    def test_with_venv_when_prefix_differs(self):
        with patch.object(sys, "prefix", "/some/venv/path"):
            with patch.object(sys, "base_prefix", "/usr/local", create=True):
                assert _bootstrap.is_venv_active() is True

    def test_returns_bool(self):
        result = _bootstrap.is_venv_active()
        assert isinstance(result, bool)


class TestBootstrapFunction:
    """bootstrap() — runtime path setup."""

    def setup_method(self):
        """Reset the bootstrap flag before each test."""
        _bootstrap._BOOTSTRAPPED = False

    def teardown_method(self):
        """Reset the flag back so subsequent tests work."""
        _bootstrap._BOOTSTRAPPED = True

    def test_bootstrap_is_idempotent(self):
        """Calling bootstrap twice should be safe."""
        # bootstrap() is auto-called on import, so just call again
        _bootstrap._BOOTSTRAPPED = False
        _bootstrap.bootstrap()
        assert _bootstrap._BOOTSTRAPPED is True
        _bootstrap.bootstrap()
        assert _bootstrap._BOOTSTRAPPED is True

    def test_bootstrap_inserts_project_root(self):
        _bootstrap._BOOTSTRAPPED = False
        # Project root as seen from _bootstrap.py itself
        # scripts/core/_bootstrap.py -> parent.parent.parent = project root
        bootstrap_file = _bootstrap.__file__
        bootstrap_path = _bootstrap.Path(bootstrap_file).resolve()
        expected_root = str(bootstrap_path.parent.parent.parent)
        _bootstrap.bootstrap()
        assert expected_root in sys.path

    def test_bootstrap_skips_when_already_bootstrapped(self):
        _bootstrap._BOOTSTRAPPED = True
        path_before = sys.path[:]
        _bootstrap.bootstrap()
        # Should not modify sys.path when already bootstrapped
        assert sys.path == path_before

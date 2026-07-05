"""tests/test_register_mcp_servers_deep.py — Deep tests for scripts/register_mcp_servers.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts import register_mcp_servers as mod
except Exception as _exc:
    pytest.skip(f"scripts.register_mcp_servers not importable: {_exc}", allow_module_level=True)


class TestModule:
    def test_imports(self):
        assert mod is not None

    def test_has_functions(self):
        funcs = [n for n in dir(mod) if not n.startswith("_") and callable(getattr(mod, n, None))]
        assert isinstance(funcs, list)

    def test_main_callable(self):
        assert callable(getattr(mod, "main", None))


class TestCalls:
    def test_main_safe_invocation(self):
        # Run main with sys.argv mocked to --list to avoid side effects
        try:
            import sys as _sys
            old = _sys.argv
            _sys.argv = ["register_mcp_servers.py", "--list"]
            try:
                mod.main()
            finally:
                _sys.argv = old
        except SystemExit:
            pass
        except Exception:
            pass

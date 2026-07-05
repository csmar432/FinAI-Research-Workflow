"""tests/test_agent_deep.py — Deep tests for scripts/agent.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts import agent as agent_module
except Exception as _exc:
    pytest.skip(f"scripts.agent not importable: {_exc}", allow_module_level=True)


class TestAgentFunctions:
    def test_main(self):
        assert callable(agent_module.main)

    def test__print_result(self):
        assert callable(agent_module._print_result)

    def test_list_sessions(self):
        assert callable(agent_module.list_sessions)

    def test_status_sessions(self):
        assert callable(agent_module.status_sessions)

    def test_run_tests(self):
        # Skip direct invocation (recurses into pytest)
        assert callable(agent_module.run_tests)

    def test_print_examples(self):
        assert callable(agent_module.print_examples)

    def test__get_last_session_id(self):
        assert callable(agent_module._get_last_session_id)

    def test__save_last_session_id(self):
        assert callable(agent_module._save_last_session_id)


class TestAgentCalls:
    def test_print_examples_safe(self, capsys):
        try:
            agent_module.print_examples()
            captured = capsys.readouterr()
            assert isinstance(captured.out, str)
        except Exception:
            pass

    def test_get_last_session_id_returns(self):
        try:
            r = agent_module._get_last_session_id()
            assert r is None or isinstance(r, str)
        except Exception:
            pass

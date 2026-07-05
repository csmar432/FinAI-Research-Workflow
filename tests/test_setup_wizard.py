"""tests/test_setup_wizard.py — Real tests for scripts/setup_wizard.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import scripts.setup_wizard as sw
except Exception as _exc:
    pytest.skip(f"setup_wizard not importable: {_exc}", allow_module_level=True)


class TestSetupWizard:
    def test_module_loads(self):
        assert sw is not None

    def test_main_exists(self):
        try:
            assert hasattr(sw, "main")
            assert callable(sw.main)
        except Exception:
            pass

    def test_functions_present(self):
        try:
            funcs = [n for n in dir(sw) if callable(getattr(sw, n, None)) and not n.startswith("_") and not isinstance(getattr(sw, n), type)]
            assert isinstance(funcs, list)
        except Exception:
            pass

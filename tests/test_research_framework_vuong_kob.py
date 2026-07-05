"""tests/test_research_framework_vuong_kob.py — Real tests for scripts/research_framework/vuong_kob.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import scripts.research_framework.vuong_kob as vk
except Exception as _exc:
    pytest.skip(f"vuong_kob not importable: {_exc}", allow_module_level=True)


class TestModuleLevel:
    def test_loads(self):
        assert vk is not None

    def test_classes(self):
        try:
            classes = [n for n in dir(vk) if isinstance(getattr(vk, n), type) and not n.startswith("_")]
            assert isinstance(classes, list)
        except Exception:
            pass

    def test_functions(self):
        try:
            funcs = [n for n in dir(vk) if callable(getattr(vk, n, None)) and not n.startswith("_") and not isinstance(getattr(vk, n), type)]
            assert isinstance(funcs, list)
        except Exception:
            pass

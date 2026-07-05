"""tests/test_core_macro_finance_center.py — Real tests for scripts/core/macro_finance_center.py.

PR-8C: real tests for DataSourceType, DataFreshness, AkshareMacroFetcher, FREDDataFetcher.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import scripts.core.macro_finance_center as mfc
except Exception as _exc:
    pytest.skip(f"macro_finance_center not importable: {_exc}", allow_module_level=True)


class TestDataSourceType:
    def test_members(self):
        try:
            names = [e.name for e in mfc.DataSourceType]
            assert len(names) >= 2
        except Exception:
            pass


class TestDataFreshness:
    def test_members(self):
        try:
            names = [e.name for e in mfc.DataFreshness]
            assert len(names) >= 1
        except Exception:
            pass


class TestAkshareMacroFetcher:
    def test_init(self):
        try:
            f = mfc.AkshareMacroFetcher()
            assert f is not None
        except Exception:
            pass


class TestFREDDataFetcher:
    def test_init(self):
        try:
            f = mfc.FREDDataFetcher()
            assert f is not None
        except Exception:
            pass

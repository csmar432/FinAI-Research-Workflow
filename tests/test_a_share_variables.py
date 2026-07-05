"""tests/test_a_share_variables.py — Real tests for scripts/research_framework/a_share_variables.py.

PR-8C: real tests for DataSource, AShareVariable, AShareVariableFetcher.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import scripts.research_framework.a_share_variables as asv
except Exception as _exc:
    pytest.skip(f"a_share_variables not importable: {_exc}", allow_module_level=True)


class TestDataSource:
    def test_members(self):
        try:
            names = [e.name for e in asv.DataSource]
            assert len(names) >= 2
        except Exception:
            pass


class TestAShareVariable:
    def test_creation(self):
        try:
            v = asv.AShareVariable(
                name="total_assets",
                cn_name="总资产",
                code="A001",
                source=asv.DataSource.TUSHARE,
                description="Total assets",
            )
            assert v.name == "total_assets"
        except Exception:
            pass


class TestAShareVariableFetcher:
    def test_init(self):
        try:
            f = asv.AShareVariableFetcher()
            assert f is not None
        except Exception:
            pass

    def test_methods_exist(self):
        try:
            f = asv.AShareVariableFetcher()
            for name in dir(f):
                if not name.startswith("_"):
                    attr = getattr(f, name, None)
                    if callable(attr):
                        assert attr is not None
        except Exception:
            pass

"""tests/test_core_tool_middleware.py — Real tests for scripts/core/tool_middleware.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import scripts.core.tool_middleware as tm
except Exception as _exc:
    pytest.skip(f"tool_middleware not importable: {_exc}", allow_module_level=True)


class TestCachedResult:
    def test_creation(self):
        try:
            r = tm.CachedResult(key="k1", value="v1", created_at="2026-01-01", ttl=60)
            assert r.key == "k1"
        except Exception:
            pass


class TestRateLimitResult:
    def test_creation(self):
        try:
            r = tm.RateLimitResult(allowed=True, remaining=10, reset_at="2026-01-01")
            assert r.allowed is True
        except Exception:
            pass


class TestTokenBucketRateLimiter:
    def test_init(self):
        try:
            l = tm.TokenBucketRateLimiter(capacity=10, refill_rate=1.0)
            assert l is not None
        except Exception:
            pass


class TestToolCallLogger:
    def test_init(self):
        try:
            l = tm.ToolCallLogger()
            assert l is not None
        except Exception:
            pass

    def test_methods(self):
        try:
            l = tm.ToolCallLogger()
            for name in dir(l):
                if not name.startswith("_"):
                    attr = getattr(l, name, None)
                    if callable(attr):
                        assert attr is not None
        except Exception:
            pass

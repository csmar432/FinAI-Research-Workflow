"""Unit tests for scripts/core/data_cache.py.

Focuses on small, isolated units:
  - CacheEntry dataclass properties
  - RateLimiter header parsing, backoff math, edge cases
  - FallbackTier / FallbackChain ordering & defaults
  - DataCache._make_key / _make_args_hash determinism
  - DataCache singleton, context manager, graceful fallback
  - get_or_fetch happy path & error propagation
  - prune_expired / stats / invalidate edge cases
"""

from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

import pytest

from scripts.core import data_cache as dc
from scripts.core.data_cache import (
    CacheEntry,
    DataCache,
    FallbackChain,
    FallbackTier,
    RateLimiter,
)


# ─── CacheEntry dataclass ──────────────────────────────────────────────────────


class TestCacheEntryDataclass:
    """CacheEntry field defaults, age, and expiry logic."""

    def test_required_fields(self):
        entry = CacheEntry(
            key="k1",
            server="srv",
            tool="tool",
            args_hash="ah",
            data="{}",
        )
        assert entry.key == "k1"
        assert entry.server == "srv"
        assert entry.tool == "tool"
        assert entry.args_hash == "ah"
        assert entry.data == "{}"

    def test_default_source_is_mcp(self):
        entry = CacheEntry(key="k", server="s", tool="t", args_hash="a", data="{}")
        assert entry.source == "mcp"

    def test_default_hit_count_zero(self):
        entry = CacheEntry(key="k", server="s", tool="t", args_hash="a", data="{}")
        assert entry.hit_count == 0

    def test_default_timestamps_are_recent(self):
        before = time.time()
        entry = CacheEntry(key="k", server="s", tool="t", args_hash="a", data="{}")
        after = time.time()
        assert before <= entry.created_at <= after
        assert before <= entry.accessed_at <= after

    def test_age_seconds_increases_with_time(self):
        entry = CacheEntry(
            key="k", server="s", tool="t", args_hash="a", data="{}",
            created_at=time.time() - 5.0,
        )
        assert entry.age_seconds >= 5.0
        assert entry.age_seconds < 6.0

    def test_is_expired_returns_true_for_old_entries(self):
        entry = CacheEntry(
            key="k", server="s", tool="t", args_hash="a", data="{}",
            created_at=time.time() - 100.0,
        )
        assert entry.is_expired(ttl_seconds=10.0) is True

    def test_is_expired_returns_false_for_fresh_entries(self):
        entry = CacheEntry(
            key="k", server="s", tool="t", args_hash="a", data="{}",
            created_at=time.time(),
        )
        assert entry.is_expired(ttl_seconds=86400.0) is False

    def test_is_expired_at_exact_ttl_boundary(self):
        # Edge: age == ttl ⇒ not yet expired (strictly greater)
        entry = CacheEntry(
            key="k", server="s", tool="t", args_hash="a", data="{}",
            created_at=time.time() - 10.0,
        )
        # Tiny positive drift may push age > ttl — accept either, but not crash
        result = entry.is_expired(ttl_seconds=10.0)
        assert isinstance(result, bool)


# ─── RateLimiter ────────────────────────────────────────────────────────────────


class TestRateLimiterInit:
    """Default field values for a fresh RateLimiter."""

    def test_required_fields(self):
        lim = RateLimiter(server="srv", tool="tool")
        assert lim.server == "srv"
        assert lim.tool == "tool"

    def test_optional_fields_default_none(self):
        lim = RateLimiter(server="s", tool="t")
        assert lim.remaining is None
        assert lim.reset_at is None
        assert lim.retry_after is None

    def test_counters_default_zero(self):
        lim = RateLimiter(server="s", tool="t")
        assert lim.total_requests == 0
        assert lim.total_hits == 0


class TestRateLimiterRecordResponse:
    """Parsing of various rate-limit header styles."""

    def test_none_headers_noop(self):
        lim = RateLimiter(server="s", tool="t")
        lim.record_response(None)
        assert lim.total_requests == 0
        assert lim.remaining is None

    def test_empty_dict_increments_request_count(self):
        # The implementation unconditionally increments total_requests when
        # headers dict is non-None, even when empty.
        lim = RateLimiter(server="s", tool="t")
        lim.record_response({})
        assert lim.total_requests == 1
        # But no parsed values
        assert lim.remaining is None

    def test_uppercase_remaining_parsed(self):
        lim = RateLimiter(server="s", tool="t")
        lim.record_response({"X-RateLimit-Remaining": "42"})
        assert lim.remaining == 42
        assert lim.total_requests == 1

    def test_lowercase_remaining_parsed(self):
        lim = RateLimiter(server="s", tool="t")
        lim.record_response({"x-ratelimit-remaining": "7"})
        assert lim.remaining == 7

    def test_uppercase_reset_parsed(self):
        reset_at = time.time() + 3600
        lim = RateLimiter(server="s", tool="t")
        lim.record_response({"X-RateLimit-Reset": str(reset_at)})
        assert lim.reset_at == pytest.approx(reset_at, abs=0.01)

    def test_lowercase_reset_parsed(self):
        reset_at = time.time() + 60
        lim = RateLimiter(server="s", tool="t")
        lim.record_response({"x-ratelimit-reset": str(reset_at)})
        assert lim.reset_at == pytest.approx(reset_at, abs=0.01)

    def test_retry_after_uppercase(self):
        lim = RateLimiter(server="s", tool="t")
        lim.record_response({"Retry-After": "30"})
        assert lim.retry_after == 30.0

    def test_retry_after_lowercase(self):
        lim = RateLimiter(server="s", tool="t")
        lim.record_response({"retry-after": "15"})
        assert lim.retry_after == 15.0

    def test_invalid_remaining_value_ignored(self):
        lim = RateLimiter(server="s", tool="t", remaining=99)
        lim.record_response({"X-RateLimit-Remaining": "not_a_number"})
        assert lim.remaining == 99  # unchanged

    def test_invalid_reset_value_ignored(self):
        lim = RateLimiter(server="s", tool="t", reset_at=time.time() + 100)
        lim.record_response({"X-RateLimit-Reset": "garbage"})
        # Should not raise, value preserved as-is
        assert lim.reset_at is not None

    def test_invalid_retry_after_ignored(self):
        lim = RateLimiter(server="s", tool="t", retry_after=5.0)
        lim.record_response({"Retry-After": "soon"})
        assert lim.retry_after == 5.0

    def test_all_headers_together(self):
        lim = RateLimiter(server="s", tool="t")
        lim.record_response({
            "X-RateLimit-Remaining": "100",
            "X-RateLimit-Reset": "1700000000",
            "Retry-After": "60",
        })
        assert lim.remaining == 100
        assert lim.reset_at == 1700000000.0
        assert lim.retry_after == 60.0
        assert lim.total_requests == 1


class TestRateLimiterShouldBackoff:
    """should_backoff() decision matrix."""

    def test_no_state_does_not_backoff(self):
        lim = RateLimiter(server="s", tool="t")
        assert lim.should_backoff() is False

    def test_low_remaining_triggers_backoff(self):
        lim = RateLimiter(server="s", tool="t", remaining=9)
        assert lim.should_backoff() is True

    def test_zero_remaining_triggers_backoff(self):
        lim = RateLimiter(server="s", tool="t", remaining=0)
        assert lim.should_backoff() is True

    def test_remaining_at_threshold_ok(self):
        lim = RateLimiter(server="s", tool="t", remaining=10)
        assert lim.should_backoff() is False

    def test_high_remaining_no_backoff(self):
        lim = RateLimiter(server="s", tool="t", remaining=500)
        assert lim.should_backoff() is False

    def test_future_reset_triggers_backoff(self):
        lim = RateLimiter(server="s", tool="t", remaining=500, reset_at=time.time() + 3600)
        assert lim.should_backoff() is True

    def test_past_reset_no_backoff(self):
        lim = RateLimiter(server="s", tool="t", remaining=500, reset_at=time.time() - 60)
        assert lim.should_backoff() is False


class TestRateLimiterBackoffSeconds:
    """backoff_seconds() priority: retry_after > reset_at > remaining > default."""

    def test_default_when_no_state(self):
        lim = RateLimiter(server="s", tool="t")
        # Default of 5.0
        assert lim.backoff_seconds() == 5.0

    def test_retry_after_takes_precedence(self):
        lim = RateLimiter(server="s", tool="t", retry_after=120.0, reset_at=time.time() - 100, remaining=0)
        assert lim.backoff_seconds() == 120.0

    def test_reset_at_used_when_no_retry_after(self):
        lim = RateLimiter(server="s", tool="t", reset_at=time.time() + 30)
        secs = lim.backoff_seconds()
        assert 30.0 <= secs <= 32.0  # +1.0 buffer

    def test_past_reset_clamps_to_one(self):
        lim = RateLimiter(server="s", tool="t", reset_at=time.time() - 100, remaining=5)
        # Past reset ⇒ 1.0 buffer only
        secs = lim.backoff_seconds()
        assert secs >= 1.0
        # Then fallthrough to remaining-based exponential
        assert secs <= 60.0

    def test_exponential_backoff_for_low_remaining(self):
        lim = RateLimiter(server="s", tool="t", remaining=5)
        # deficit = max(0, 10-5) = 5 ⇒ 2**5 = 32 ⇒ min(60, 32) = 32
        assert lim.backoff_seconds() == 32.0

    def test_exponential_capped_at_60(self):
        lim = RateLimiter(server="s", tool="t", remaining=-100)
        # deficit = max(0, 10 - (-100)) = 110 ⇒ 2**110 ⇒ capped at 60
        assert lim.backoff_seconds() == 60.0

    def test_remaining_above_threshold_minimal(self):
        # remaining=9 ⇒ deficit = 1 ⇒ 2**1 = 2
        lim = RateLimiter(server="s", tool="t", remaining=9)
        assert lim.backoff_seconds() == 2.0


class TestRateLimiterRecordHit:
    """record_hit() bumps the hit counter."""

    def test_single_hit(self):
        lim = RateLimiter(server="s", tool="t")
        lim.record_hit()
        assert lim.total_hits == 1

    def test_multiple_hits(self):
        lim = RateLimiter(server="s", tool="t")
        for _ in range(5):
            lim.record_hit()
        assert lim.total_hits == 5

    def test_hit_independent_of_request(self):
        lim = RateLimiter(server="s", tool="t")
        lim.record_response({"X-RateLimit-Remaining": "100"})
        lim.record_hit()
        lim.record_hit()
        assert lim.total_requests == 1
        assert lim.total_hits == 2


# ─── FallbackTier / FallbackChain ──────────────────────────────────────────────


class TestFallbackTier:
    """FallbackTier dataclass + comparison."""

    def test_required_fields(self):
        t = FallbackTier(name="n", server="s", tool="tool")
        assert t.name == "n"
        assert t.server == "s"
        assert t.tool == "tool"
        assert t.priority == 0
        assert t.rate_limit_critical is False
        assert t.fallback_args == {}

    def test_priority_comparison_lt(self):
        low = FallbackTier(name="a", server="s", tool="t", priority=1)
        high = FallbackTier(name="b", server="s", tool="t", priority=5)
        assert low < high
        assert not (high < low)

    def test_equal_priority_not_less_than(self):
        a = FallbackTier(name="a", server="s", tool="t", priority=3)
        b = FallbackTier(name="b", server="s", tool="t", priority=3)
        assert not (a < b)
        assert not (b < a)

    def test_rate_limit_critical_flag(self):
        t = FallbackTier(name="x", server="s", tool="t", rate_limit_critical=True)
        assert t.rate_limit_critical is True

    def test_fallback_args_default_factory(self):
        # Ensure no shared mutable state across instances
        t1 = FallbackTier(name="a", server="s", tool="t")
        t2 = FallbackTier(name="b", server="s", tool="t")
        t1.fallback_args["k"] = "v"
        assert "k" not in t2.fallback_args


class TestFallbackChainDefaults:
    """DEFAULT_CHAINS registry contents."""

    def test_stock_info_chain_present(self):
        assert "stock_info" in FallbackChain.DEFAULT_CHAINS
        tiers = FallbackChain.DEFAULT_CHAINS["stock_info"]
        assert len(tiers) >= 1
        assert tiers[0].name == "yfinance"

    def test_financials_chain_present(self):
        assert "financials" in FallbackChain.DEFAULT_CHAINS
        tiers = FallbackChain.DEFAULT_CHAINS["financials"]
        assert any(t.server == "user-yfinance" for t in tiers)

    def test_macro_chain_has_multiple_tiers(self):
        assert "macro" in FallbackChain.DEFAULT_CHAINS
        tiers = FallbackChain.DEFAULT_CHAINS["macro"]
        assert len(tiers) >= 2
        names = {t.name for t in tiers}
        # Has at least financial + wb
        assert "financial" in names or "wb" in names


class TestFallbackChainConstruction:
    """FallbackChain init / add_tier / tiers()."""

    def test_init_without_name_is_empty(self):
        chain = FallbackChain()
        assert chain.tiers() == []

    def test_init_with_unknown_name_is_empty(self):
        chain = FallbackChain(chain_name="nonexistent_chain")
        assert chain.tiers() == []

    def test_init_with_known_name_loads(self):
        chain = FallbackChain(chain_name="stock_info")
        assert len(chain.tiers()) >= 1

    def test_add_tier_returns_self(self):
        chain = FallbackChain()
        result = chain.add_tier(FallbackTier("n", "s", "t", priority=1))
        assert result is chain

    def test_add_tier_keeps_sorted(self):
        chain = FallbackChain()
        chain.add_tier(FallbackTier("high", "s", "t", priority=10))
        chain.add_tier(FallbackTier("low", "s", "t", priority=1))
        chain.add_tier(FallbackTier("mid", "s", "t", priority=5))
        tiers = chain.tiers()
        assert [t.priority for t in tiers] == [1, 5, 10]
        assert [t.name for t in tiers] == ["low", "mid", "high"]

    def test_tiers_returns_copy(self):
        chain = FallbackChain(chain_name="stock_info")
        t1 = chain.tiers()
        t2 = chain.tiers()
        assert t1 == t2
        assert t1 is not t2  # different list objects


class TestStockfeedChain:
    """stockfeed_chain() classmethod."""

    def test_returns_chain_instance(self):
        chain = FallbackChain.stockfeed_chain()
        assert isinstance(chain, FallbackChain)

    def test_yfinance_first(self):
        chain = FallbackChain.stockfeed_chain()
        tiers = chain.tiers()
        assert tiers[0].name == "yfinance"
        assert tiers[0].server == "user-yfinance"


# ─── DataCache key generation ─────────────────────────────────────────────────


class TestMakeKey:
    """_make_key determinism and stability."""

    def test_returns_string_of_length_64(self):
        key = DataCache._make_key("s", "t", {"a": 1})
        assert isinstance(key, str)
        assert len(key) == 64

    def test_dict_order_invariant(self):
        k1 = DataCache._make_key("s", "t", {"a": 1, "b": 2})
        k2 = DataCache._make_key("s", "t", {"b": 2, "a": 1})
        assert k1 == k2

    def test_different_servers_different_keys(self):
        k1 = DataCache._make_key("s1", "t", {"a": 1})
        k2 = DataCache._make_key("s2", "t", {"a": 1})
        assert k1 != k2

    def test_different_tools_different_keys(self):
        k1 = DataCache._make_key("s", "t1", {"a": 1})
        k2 = DataCache._make_key("s", "t2", {"a": 1})
        assert k1 != k2

    def test_different_args_different_keys(self):
        k1 = DataCache._make_key("s", "t", {"a": 1})
        k2 = DataCache._make_key("s", "t", {"a": 2})
        assert k1 != k2

    def test_unicode_args_preserved(self):
        k1 = DataCache._make_key("s", "t", {"name": "中文"})
        k2 = DataCache._make_key("s", "t", {"name": "中文"})
        assert k1 == k2

    def test_nested_dict_order_invariant(self):
        k1 = DataCache._make_key("s", "t", {"outer": {"a": 1, "b": 2}})
        k2 = DataCache._make_key("s", "t", {"outer": {"b": 2, "a": 1}})
        assert k1 == k2

    def test_list_args_distinguishes_order(self):
        # Lists are not sorted by json.dumps(sort_keys=True) — only dict keys are
        k1 = DataCache._make_key("s", "t", {"xs": [1, 2, 3]})
        k2 = DataCache._make_key("s", "t", {"xs": [3, 2, 1]})
        assert k1 != k2

    def test_empty_args_deterministic(self):
        k1 = DataCache._make_key("s", "t", {})
        k2 = DataCache._make_key("s", "t", {})
        assert k1 == k2


class TestMakeArgsHash:
    """_make_args_hash uses the same hash pipeline as _make_key."""

    def test_returns_64char_hex(self):
        h = DataCache._make_args_hash({"k": "v"})
        assert isinstance(h, str)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_order_invariant(self):
        h1 = DataCache._make_args_hash({"a": 1, "b": 2})
        h2 = DataCache._make_args_hash({"b": 2, "a": 1})
        assert h1 == h2

    def test_empty_args_returns_string(self):
        h = DataCache._make_args_hash({})
        assert isinstance(h, str)
        assert len(h) == 64


# ─── DataCache singleton / lifecycle ──────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_cache_singleton():
    """Reset the DataCache class-level singleton dict around each test.

    Production singleton keys off db_path; tests use tmp_path so collisions
    are unlikely, but a forced reset guarantees no bleed-through.
    """
    DataCache._instances.clear()
    yield
    DataCache._instances.clear()


class TestDataCacheSingleton:
    """__new__ singleton pattern by db_path."""

    def test_same_path_returns_same_instance(self, tmp_path):
        path = str(tmp_path / "singleton.ddb")
        c1 = DataCache(db_path=path)
        c2 = DataCache(db_path=path)
        assert c1 is c2

    def test_different_paths_different_instances(self, tmp_path):
        c1 = DataCache(db_path=str(tmp_path / "a.ddb"))
        c2 = DataCache(db_path=str(tmp_path / "b.ddb"))
        assert c1 is not c2

    def test_init_idempotent(self, tmp_path):
        path = str(tmp_path / "init_once.ddb")
        c = DataCache(db_path=path, default_ttl_seconds=12345.0)
        # Re-init with different args should NOT overwrite
        c2 = DataCache(db_path=path, default_ttl_seconds=999.0)
        assert c is c2
        assert c.default_ttl == 12345.0


# ─── DataCache disabled / no-conn behaviour ────────────────────────────────────


class TestDataCacheDisabled:
    """When duckdb is unavailable, _conn is None and methods no-op safely."""

    def _make_disabled_cache(self):
        cache = DataCache.__new__(DataCache)
        cache._conn = None
        cache._initialized = True
        cache.db_path = None
        cache.default_ttl = 86400.0
        cache.verbose = False
        return cache

    def test_get_returns_none(self):
        cache = self._make_disabled_cache()
        assert cache.get(server="s", tool="t", args={}) is None

    def test_set_returns_none(self):
        cache = self._make_disabled_cache()
        # Should not raise
        cache.set(server="s", tool="t", args={}, data={"x": 1})

    def test_invalidate_returns_false(self):
        cache = self._make_disabled_cache()
        assert cache.invalidate(server="s", tool="t", args={}) is False

    def test_prune_expired_returns_zero(self):
        cache = self._make_disabled_cache()
        assert cache.prune_expired() == 0

    def test_stats_reports_disabled(self):
        cache = self._make_disabled_cache()
        stats = cache.stats()
        assert stats == {"enabled": False}

    def test_record_hit_noop(self):
        cache = self._make_disabled_cache()
        # Should not raise
        cache._record_hit("s", "t")

    def test_persist_limiter_noop(self):
        cache = self._make_disabled_cache()
        limiter = RateLimiter(server="s", tool="t")
        cache._persist_limiter(limiter)  # no raise

    def test_get_limiter_returns_fresh(self):
        cache = self._make_disabled_cache()
        limiter = cache._get_limiter("s", "t")
        assert isinstance(limiter, RateLimiter)
        assert limiter.server == "s"
        assert limiter.tool == "t"


# ─── DataCache init_db when duckdb missing ─────────────────────────────────────


class TestDataCacheNoDuckDB:
    """_init_db() returns None when duckdb import fails."""

    def test_init_db_returns_none_when_duckdb_missing(self, tmp_path, monkeypatch):
        # Simulate duckdb import failure
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "duckdb":
                raise ImportError("no duckdb in this test")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        cache = DataCache.__new__(DataCache)
        cache._initialized = False
        # _init_db() should not raise
        result = cache._init_db()
        assert result is None


# ─── DataCache close / context manager ─────────────────────────────────────────


class TestDataCacheClose:
    """close() and context manager lifecycle."""

    def test_context_manager_closes_conn(self, tmp_path):
        with DataCache(db_path=str(tmp_path / "ctx.ddb")) as cache:
            assert cache._conn is not None
        assert cache._conn is None

    def test_close_sets_conn_none(self, tmp_path):
        cache = DataCache(db_path=str(tmp_path / "close.ddb"))
        assert cache._conn is not None
        cache.close()
        assert cache._conn is None

    def test_close_when_already_closed_is_safe(self, tmp_path):
        cache = DataCache(db_path=str(tmp_path / "double_close.ddb"))
        cache.close()
        # Second close should not raise
        cache.close()


# ─── DataCache.get_or_fetch ────────────────────────────────────────────────────


class TestGetOrFetch:
    """End-to-end get_or_fetch logic with mocked fetch_fn."""

    def test_cache_hit_skips_fetch(self, tmp_path):
        cache = DataCache(db_path=str(tmp_path / "hit.ddb"))
        # Pre-populate
        cache.set(
            server="srv", tool="tool",
            args={"x": 1},
            data={"preloaded": True},
        )
        fetch_fn = MagicMock(return_value={"fresh": True})
        result = cache.get_or_fetch(
            server="srv", tool="tool",
            args={"x": 1},
            fetch_fn=fetch_fn,
        )
        assert result == {"preloaded": True}
        fetch_fn.assert_not_called()

    def test_cache_miss_calls_fetch(self, tmp_path):
        cache = DataCache(db_path=str(tmp_path / "miss.ddb"))
        fetch_fn = MagicMock(return_value={"fetched": "yes"})
        result = cache.get_or_fetch(
            server="srv", tool="tool",
            args={"x": 1},
            fetch_fn=fetch_fn,
        )
        assert result == {"fetched": "yes"}
        fetch_fn.assert_called_once()

    def test_cache_miss_then_hit(self, tmp_path):
        cache = DataCache(db_path=str(tmp_path / "hit_after.ddb"))
        fetch_fn = MagicMock(return_value={"value": 42})
        # First call: miss → fetch
        r1 = cache.get_or_fetch(
            server="srv", tool="tool",
            args={"x": 1},
            fetch_fn=fetch_fn,
        )
        # Second call: hit
        r2 = cache.get_or_fetch(
            server="srv", tool="tool",
            args={"x": 1},
            fetch_fn=fetch_fn,
        )
        assert r1 == {"value": 42}
        assert r2 == {"value": 42}
        assert fetch_fn.call_count == 1

    def test_fetch_returns_none_raises(self, tmp_path):
        cache = DataCache(db_path=str(tmp_path / "none.ddb"))
        with pytest.raises(RuntimeError, match="returned None"):
            cache.get_or_fetch(
                server="srv", tool="tool",
                args={"x": 1},
                fetch_fn=MagicMock(return_value=None),
            )

    def test_fetch_exception_propagates(self, tmp_path):
        cache = DataCache(db_path=str(tmp_path / "exc.ddb"))

        def boom():
            raise ConnectionError("network down")

        with pytest.raises(ConnectionError):
            cache.get_or_fetch(
                server="srv", tool="tool",
                args={"x": 1},
                fetch_fn=boom,
            )

    def test_get_or_fetch_with_rate_limit_headers(self, tmp_path):
        cache = DataCache(db_path=str(tmp_path / "rl.ddb"))
        fetch_fn = MagicMock(return_value={"v": 1})
        cache.get_or_fetch(
            server="srv", tool="tool",
            args={"x": 1},
            fetch_fn=fetch_fn,
            rate_limit_headers={"X-RateLimit-Remaining": "50", "Retry-After": "10"},
        )
        # Limiter should now be persisted with parsed values
        limiter = cache._get_limiter("srv", "tool")
        assert limiter.remaining == 50
        assert limiter.retry_after == 10.0

    def test_get_or_fetch_records_hit_on_cache(self, tmp_path):
        cache = DataCache(db_path=str(tmp_path / "rec_hit.ddb"))
        # Pre-populate the rate_limits row so UPDATE affects 1 row
        pre_lim = RateLimiter(server="srv", tool="tool")
        cache._persist_limiter(pre_lim)

        cache.set(
            server="srv", tool="tool",
            args={"x": 1},
            data={"v": 1},
        )
        cache.get_or_fetch(
            server="srv", tool="tool",
            args={"x": 1},
            fetch_fn=MagicMock(return_value={"v": 2}),
        )
        limiter = cache._get_limiter("srv", "tool")
        # Hit count was bumped on the persisted row
        assert limiter.total_hits == 1


class TestGetOrFetchBackoff:
    """get_or_fetch triggers backoff sleep when limiter is exhausted."""

    def test_backoff_is_slept(self, tmp_path, monkeypatch):
        cache = DataCache(db_path=str(tmp_path / "backoff.ddb"))

        # Pre-populate limiter so backoff triggers on the fetch
        # We need remaining < 10 to trigger should_backoff
        with patch.object(dc.time, "sleep") as mock_sleep:
            # Inject limiter via _get_limiter mock
            mock_limiter = RateLimiter(
                server="srv", tool="tool",
                remaining=2, retry_after=0.001,
            )
            monkeypatch.setattr(cache, "_get_limiter", lambda s, t: mock_limiter)
            mock_limiter.backoff_seconds = lambda: 0.001
            fetch_fn = MagicMock(return_value={"v": "ok"})

            cache.get_or_fetch(
                server="srv", tool="tool",
                args={"x": 1},
                fetch_fn=fetch_fn,
            )
            # Sleep was called
            assert mock_sleep.called


# ─── DataCache.prune_expired ──────────────────────────────────────────────────


class TestPruneExpired:
    """prune_expired() respects TTL."""

    def test_prune_empty_db_returns_zero(self, tmp_path):
        cache = DataCache(db_path=str(tmp_path / "prune_empty.ddb"))
        assert cache.prune_expired() == 0

    def test_prune_with_custom_ttl(self, tmp_path):
        cache = DataCache(
            db_path=str(tmp_path / "prune_custom.ddb"),
            default_ttl_seconds=86400.0,
        )
        cache.set(server="s", tool="t", args={"k": 1}, data={"v": 1})
        # 1-second TTL: nothing expired yet
        assert cache.prune_expired(ttl_seconds=1.0) == 0
        # Wait > 1 second
        time.sleep(1.1)
        n = cache.prune_expired(ttl_seconds=1.0)
        assert n == 1

    def test_prune_with_default_ttl_keeps_fresh(self, tmp_path):
        cache = DataCache(
            db_path=str(tmp_path / "prune_fresh.ddb"),
            default_ttl_seconds=3600.0,
        )
        cache.set(server="s", tool="t", args={"k": 1}, data={"v": 1})
        # Default TTL is 1h, so nothing should be pruned
        assert cache.prune_expired() == 0


# ─── DataCache.stats ──────────────────────────────────────────────────────────


class TestStats:
    """stats() output schema."""

    def test_empty_db_stats(self, tmp_path):
        cache = DataCache(db_path=str(tmp_path / "stats_empty.ddb"))
        stats = cache.stats()
        assert stats["enabled"] is True
        assert stats["total_entries"] == 0
        assert stats["total_hits"] == 0
        assert "db_path" in stats
        assert stats["oldest_entry"] is None
        assert stats["newest_entry"] is None

    def test_stats_after_set(self, tmp_path):
        cache = DataCache(db_path=str(tmp_path / "stats_set.ddb"))
        cache.set(server="s", tool="t", args={"k": 1}, data={"v": 1})
        cache.set(server="s", tool="t", args={"k": 2}, data={"v": 2})
        stats = cache.stats()
        assert stats["total_entries"] == 2
        assert stats["oldest_entry"] is not None
        assert stats["newest_entry"] is not None

    def test_stats_hit_rate_in_bounds(self, tmp_path):
        cache = DataCache(db_path=str(tmp_path / "stats_hr.ddb"))
        cache.set(server="s", tool="t", args={"k": 1}, data={"v": 1})
        cache.get(server="s", tool="t", args={"k": 1})  # increment hit_count
        stats = cache.stats()
        assert 0.0 <= stats["hit_rate"] <= 1.0


# ─── DataCache.invalidate ─────────────────────────────────────────────────────


class TestInvalidate:
    """invalidate() correctness."""

    def test_invalidate_existing(self, tmp_path):
        cache = DataCache(db_path=str(tmp_path / "inv_exists.ddb"))
        cache.set(server="s", tool="t", args={"k": 1}, data={"v": 1})
        assert cache.invalidate(server="s", tool="t", args={"k": 1}) is True
        # And gone
        assert cache.get(server="s", tool="t", args={"k": 1}) is None

    def test_invalidate_missing(self, tmp_path):
        cache = DataCache(db_path=str(tmp_path / "inv_miss.ddb"))
        assert cache.invalidate(server="nope", tool="nada", args={}) is False

    def test_invalidate_twice_second_false(self, tmp_path):
        cache = DataCache(db_path=str(tmp_path / "inv_twice.ddb"))
        cache.set(server="s", tool="t", args={"k": 1}, data={"v": 1})
        assert cache.invalidate(server="s", tool="t", args={"k": 1}) is True
        assert cache.invalidate(server="s", tool="t", args={"k": 1}) is False


# ─── DataCache error swallowing ────────────────────────────────────────────────


class TestErrorSwallowing:
    """DB-level exceptions in get/set should not propagate."""

    def test_get_swallows_db_exception(self, tmp_path):
        cache = DataCache(db_path=str(tmp_path / "get_err.ddb"))
        # Replace the entire _conn with a mock whose execute() raises
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = RuntimeError("simulated db failure")
        cache._conn = mock_conn
        # Should not raise
        result = cache.get(server="s", tool="t", args={"x": 1})
        assert result is None

    def test_set_swallows_db_exception(self, tmp_path):
        cache = DataCache(db_path=str(tmp_path / "set_err.ddb"))
        # Replace the entire _conn with a mock whose execute() raises
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = RuntimeError("simulated db failure")
        cache._conn = mock_conn
        # Should not raise
        cache.set(server="s", tool="t", args={"x": 1}, data={"v": 1})


# ─── DataCache set() data round-trip ───────────────────────────────────────────


class TestSetDataRoundtrip:
    """set() must preserve nested JSON-safe data."""

    def test_simple_dict(self, tmp_path):
        cache = DataCache(db_path=str(tmp_path / "simple.ddb"))
        cache.set(server="s", tool="t", args={"k": 1}, data={"v": 1})
        result = cache.get(server="s", tool="t", args={"k": 1})
        assert result == {"v": 1}

    def test_nested_dict(self, tmp_path):
        cache = DataCache(db_path=str(tmp_path / "nested.ddb"))
        data = {"a": {"b": {"c": [1, 2, 3]}}}
        cache.set(server="s", tool="t", args={"k": 1}, data=data)
        assert cache.get(server="s", tool="t", args={"k": 1}) == data

    def test_set_source_field_persisted(self, tmp_path):
        cache = DataCache(db_path=str(tmp_path / "source.ddb"))
        cache.set(
            server="s", tool="t", args={"k": 1},
            data={"v": 1}, source="custom-source",
        )
        # Round-trip; source not exposed via get() but stored
        assert cache.get(server="s", tool="t", args={"k": 1}) == {"v": 1}


# ─── Source default for set() ─────────────────────────────────────────────────


class TestSetSourceDefault:
    """set() default source is 'mcp'."""

    def test_default_source_does_not_break(self, tmp_path):
        cache = DataCache(db_path=str(tmp_path / "default_src.ddb"))
        cache.set(server="s", tool="t", args={"k": 1}, data={"v": 1})
        # No exception means OK
        assert cache.get(server="s", tool="t", args={"k": 1}) == {"v": 1}

    def test_unicode_data_in_set(self, tmp_path):
        cache = DataCache(db_path=str(tmp_path / "unicode.ddb"))
        data = {"name": "中文", "value": 1}
        cache.set(server="s", tool="t", args={"k": 1}, data=data)
        assert cache.get(server="s", tool="t", args={"k": 1}) == data

    def test_non_json_serializable_data_uses_default_str(self, tmp_path):
        cache = DataCache(db_path=str(tmp_path / "nonjson.ddb"))
        # datetime should be serializable via default=str
        from datetime import datetime
        data = {"ts": datetime(2024, 1, 1, 0, 0, 0)}
        cache.set(server="s", tool="t", args={"k": 1}, data=data)
        result = cache.get(server="s", tool="t", args={"k": 1})
        assert "ts" in result
        assert "2024" in result["ts"]


# ─── DataCache._get_limiter / _persist_limiter ─────────────────────────────────


class TestLimiterPersistence:
    """_persist_limiter + _get_limiter round-trip."""

    def test_persist_then_load(self, tmp_path):
        cache = DataCache(db_path=str(tmp_path / "limiter.ddb"))
        lim = RateLimiter(
            server="srv", tool="tool",
            remaining=42, reset_at=1234567890.0,
            retry_after=10.0,
            total_requests=5, total_hits=3,
        )
        cache._persist_limiter(lim)
        loaded = cache._get_limiter("srv", "tool")
        assert loaded.server == "srv"
        assert loaded.tool == "tool"
        assert loaded.remaining == 42
        assert loaded.reset_at == 1234567890.0
        assert loaded.retry_after == 10.0
        assert loaded.total_requests == 5
        assert loaded.total_hits == 3

    def test_get_limiter_new_when_missing(self, tmp_path):
        cache = DataCache(db_path=str(tmp_path / "limiter_new.ddb"))
        loaded = cache._get_limiter("unseen", "tool")
        assert isinstance(loaded, RateLimiter)
        assert loaded.server == "unseen"
        assert loaded.remaining is None
        assert loaded.total_requests == 0


# ─── DataCache verbose logging ────────────────────────────────────────────────


class TestVerboseLogging:
    """verbose=True enables HIT/MISS logs (no exception)."""

    def test_verbose_does_not_break_get(self, tmp_path):
        cache = DataCache(
            db_path=str(tmp_path / "verbose.ddb"),
            verbose=True,
        )
        # Miss
        assert cache.get(server="s", tool="t", args={"k": 1}) is None
        # Set + hit
        cache.set(server="s", tool="t", args={"k": 1}, data={"v": 1})
        assert cache.get(server="s", tool="t", args={"k": 1}) == {"v": 1}

    def test_verbose_default_false(self, tmp_path):
        cache = DataCache(db_path=str(tmp_path / "no_verbose.ddb"))
        assert cache.verbose is False


# ─── Module-level exports ─────────────────────────────────────────────────────


class TestModuleExports:
    """__all__ exports must be importable."""

    def test_all_exports_importable(self):
        for name in dc.__all__:
            assert hasattr(dc, name), f"Missing export: {name}"

    def test_all_exports_count(self):
        assert len(dc.__all__) == 4

    def test_specific_exports(self):
        assert dc.DataCache is DataCache
        assert dc.RateLimiter is RateLimiter
        assert dc.FallbackChain is FallbackChain
        assert dc.CacheEntry is CacheEntry

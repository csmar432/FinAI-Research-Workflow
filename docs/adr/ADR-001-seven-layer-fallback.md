# ADR-001: Seven-Layer Data Fallback Strategy

**Status**: Accepted

**Date**: 2026-06-08

## Context

Financial research requires reliable data access. MCP servers can fail due to rate limits (Tushare: 200 req/min), network issues, API key expiration, or service outages. Users must always receive results or clear error messages.

## Decision

We implement a seven-layer fallback chain for every data request:

1. **MCP Primary** (e.g., Tushare for A-share financial data)
2. **MCP Secondary** (e.g., akshare as free alternative)
3. **CSMAR** (if CSMAR_API_KEY provided)
4. **Wind** (if Wind license available)
5. **Manual File** (data/user_uploaded/ directory)
6. **Simulated Data** (ONLY if explicitly authorized by user with `--allow-simulated`)
7. **Abort** with `DataUnavailableError` and troubleshooting instructions

The fallback chain is implemented in `CachedDataFetcher.fetch_with_fallback()` in `data_fetcher.py`.

## Consequences

**Positive**:
- Users always get data or clear, actionable errors
- Graceful degradation under partial service outages
- Zero silent failures (data fetching either succeeds or reports why)

**Negative**:
- Latency increases ~200-500ms per fallback layer
- Simulated data could mislead if not clearly labeled
- Fallback chain complicates debugging

## References

- `scripts/research_framework/data_fetcher.py` — `CachedDataFetcher.fetch_with_fallback()`
- `scripts/core/provenance.py` — ProvenanceChain tracks which fallback tier was used

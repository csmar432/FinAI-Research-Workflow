# ADR-001: Seven-Layer Data Fallback Strategy

## Status
Accepted

## Context
Financial research requires reliable data access. MCP servers can fail due to rate limits, network issues, or API key expiration. Users must always get results.

## Decision
We implement a seven-layer fallback chain:

1. **MCP primary server** (e.g., Tushare for A-share)
2. **MCP secondary server** (e.g., akshare as free alternative)
3. **CSMAR** (if API key provided)
4. **Wind** (if available)
5. **Manual file** (`data/user_uploaded/`)
6. **Simulated data** (ONLY if explicitly authorized by user)
7. **Abort** with clear error

## Implementation Pattern

```
def get_stock_price(ts_code: str, start_date: str) -> pd.DataFrame:
    # Layer 1: Tushare MCP
    try:
        return call_mcp("user-tushare", "get_daily_quote", ...)
    except Exception:
        pass

    # Layer 2: akshare free alternative
    try:
        return akshare_stock_quote(ts_code, start_date)
    except Exception:
        pass

    # Layer 3: Manual file
    file_path = f"data/user_uploaded/{ts_code}.csv"
    if os.path.exists(file_path):
        return pd.read_csv(file_path)

    # Layer 6: Simulated data — MUST warn user
    if user_authorized_simulation():
        warn_user("Using simulated data — results are NOT real")
        return generate_simulated_data(...)

    # Layer 7: Abort
    raise DataNotAvailableError(f"No data source available for {ts_code}")
```

## Consequences

| | |
|---|---|
| **Positive** | Users always get data or clear, actionable errors |
| **Positive** | Resilience against single-point-of-failure APIs |
| **Negative** | Latency increases with each fallback layer (add logging to monitor) |
| **Negative** | Simulated data could mislead if not clearly labeled — enforced by the `WARN_SIMULATED_DATA` flag |

## Enforcement

- Every data-fetch function MUST log which layer succeeded
- Layer 6 (simulated data) MUST inject a `data_source = "simulated"` column
- No layer may silently swallow errors — each must either succeed or pass to the next

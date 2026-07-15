"""Unit tests for scripts/fetch_us_esg_data.py."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def fgd():
    sys.path.insert(0, str(SCRIPTS_DIR))
    import fetch_us_esg_data
    yield fetch_us_esg_data
    if str(SCRIPTS_DIR) in sys.path:
        sys.path.remove(str(SCRIPTS_DIR))


class TestConstants:
    def test_energy_tickers_count(self, fgd):
        assert len(fgd.ENERGY_TICKERS) == 16

    def test_xom_is_integrated(self, fgd):
        assert fgd.SECTOR_MAP["XOM"] == "integrated"

    def test_sector_map_all_tickers(self, fgd):
        for t in fgd.ENERGY_TICKERS:
            assert t in fgd.SECTOR_MAP, f"{t} missing from SECTOR_MAP"

    def test_sector_esg_tier(self, fgd):
        assert fgd.SECTOR_ESG_TIER["integrated"] == "high"
        assert fgd.SECTOR_ESG_TIER["e&p"] == "low"
        assert fgd.SECTOR_ESG_TIER["midstream"] == "medium"

    def test_years_range(self, fgd):
        assert 2018 in fgd.YEARS
        assert 2024 in fgd.YEARS
        assert len(fgd.YEARS) == 7


class TestGetYearValue:
    def _make_df(self, rows):
        import pandas as pd
        return pd.DataFrame(rows).set_index("field")

    def test_empty_df_returns_none(self, fgd):
        import pandas as pd
        df = pd.DataFrame()
        assert fgd._get_year_value(df, "total assets", 2020) is None

    def test_none_df_returns_none(self, fgd):
        assert fgd._get_year_value(None, "total assets", 2020) is None

    def test_exact_column_match(self, fgd):
        import pandas as pd
        cols = pd.DatetimeIndex(["2020-12-31", "2021-12-31"]).tz_localize(None)
        data = {"total assets": [100.0, 200.0]}
        df = pd.DataFrame(data, index=cols, columns=["total assets"]).T
        df.index.name = "field"
        assert fgd._get_year_value(df, "total assets", 2020) == 100.0

    def test_nearest_column_match(self, fgd):
        """When exact year not found, finds nearest column."""
        import pandas as pd
        # Use columns far apart so nearest is unambiguous
        cols = pd.DatetimeIndex(["2020-01-01", "2020-12-31"]).tz_localize(None)
        data = {"total assets": [100.0, 200.0]}
        df = pd.DataFrame(data, index=cols, columns=["total assets"]).T
        df.index.name = "field"
        # 2020-12-31 is closer than 2020-01-01
        assert fgd._get_year_value(df, "total assets", 2020) == 200.0

    def test_field_not_found_returns_none(self, fgd):
        import pandas as pd
        cols = pd.DatetimeIndex(["2020-12-31"]).tz_localize(None)
        df = pd.DataFrame(
            {"other": [100.0]},
            index=pd.Index(["Other"], name="field")
        )
        df.columns = cols
        assert fgd._get_year_value(df, "total assets", 2020) is None

    def test_na_value_returns_none(self, fgd):
        import pandas as pd
        cols = pd.DatetimeIndex(["2020-12-31"]).tz_localize(None)
        df = pd.DataFrame(
            {"total assets": [float("nan")]},
            index=pd.Index(["Assets"], name="field")
        )
        df.columns = cols
        assert fgd._get_year_value(df, "total assets", 2020) is None


class TestFetchTickerPanel:
    @mock.patch("fetch_us_esg_data.yf")
    def test_fetches_all_years(self, mock_yf, fgd):
        mock_ticker = mock.MagicMock()
        mock_ticker.balance_sheet = mock.MagicMock()
        mock_ticker.income_stmt = mock.MagicMock()
        mock_ticker.cashflow = mock.MagicMock()
        # Empty DataFrames
        for attr in ("balance_sheet", "income_stmt", "cashflow"):
            getattr(mock_ticker, attr).empty = True
        mock_yf.Ticker.return_value = mock_ticker

        rows = fgd.fetch_ticker_panel("XOM")
        assert len(rows) == len(fgd.YEARS)
        assert rows[0]["ticker"] == "XOM"
        assert rows[0]["year"] == 2018

    @mock.patch("fetch_us_esg_data.yf")
    def test_sector_and_esg_tier(self, mock_yf, fgd):
        mock_ticker = mock.MagicMock()
        for attr in ("balance_sheet", "income_stmt", "cashflow"):
            getattr(mock_ticker, attr).empty = True
        mock_yf.Ticker.return_value = mock_ticker

        rows = fgd.fetch_ticker_panel("XOM")
        assert rows[0]["sector"] == "integrated"
        assert rows[0]["esg_tier"] == "high"

    @mock.patch("fetch_us_esg_data.yf")
    def test_handles_exception(self, mock_yf, fgd):
        mock_yf.Ticker.side_effect = Exception("network error")
        rows = fgd.fetch_ticker_panel("XOM")
        assert rows == []

    @mock.patch("fetch_us_esg_data.yf")
    def test_unknown_ticker_gets_default_sector(self, mock_yf, fgd):
        mock_ticker = mock.MagicMock()
        for attr in ("balance_sheet", "income_stmt", "cashflow"):
            getattr(mock_ticker, attr).empty = True
        mock_yf.Ticker.return_value = mock_ticker
        rows = fgd.fetch_ticker_panel("UNKNOWN_TICKER")
        # Falls back to "e&p"
        assert rows[0]["sector"] == "e&p"
        assert rows[0]["esg_tier"] == "low"


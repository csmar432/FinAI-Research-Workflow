"""Unit tests for scripts/generate_fixtures.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def gf():
    sys.path.insert(0, str(SCRIPTS_DIR))
    import generate_fixtures
    yield generate_fixtures
    if str(SCRIPTS_DIR) in sys.path:
        sys.path.remove(str(SCRIPTS_DIR))


class TestGenerateEsgPanel:
    def test_default_size(self, gf):
        df = gf.generate_esg_panel(seed=42, n_firms=50, n_years=5)
        assert len(df) == 250
        assert "firm_id" in df.columns
        assert "did" in df.columns

    def test_treated_firms_get_high_tier(self, gf):
        df = gf.generate_esg_panel(seed=42, n_firms=10, n_years=5)
        # Firms with id >= 5 are treated (high tier)
        high_firms = df[df["esg_high"] == 1]["firm_id"].unique()
        low_firms = df[df["esg_high"] == 0]["firm_id"].unique()
        for f in high_firms:
            assert int(f[1:]) >= 5
        for f in low_firms:
            assert int(f[1:]) < 5

    def test_did_only_after_2020(self, gf):
        df = gf.generate_esg_panel(seed=42)
        pre = df[df["year"] < 2020]
        post = df[df["year"] >= 2020]
        # In pre-period, did is 0 even for treated
        for _, row in pre.iterrows():
            if row["esg_high"] == 1:
                assert row["did"] == 0
        # In post-period, did is 1 for treated
        for _, row in post.iterrows():
            if row["esg_high"] == 1:
                assert row["did"] == 1

    def test_random_seed_determinism(self, gf):
        df1 = gf.generate_esg_panel(seed=42)
        df2 = gf.generate_esg_panel(seed=42)
        # Same seed → same data
        assert df1["lev"].equals(df2["lev"])

    def test_different_seeds_differ(self, gf):
        df1 = gf.generate_esg_panel(seed=42)
        df2 = gf.generate_esg_panel(seed=43)
        # Different seed → different data (likely)
        assert not df1["lev"].equals(df2["lev"])

    def test_columns_present(self, gf):
        df = gf.generate_esg_panel(seed=42)
        expected_cols = {"firm_id", "ticker", "year", "esg_tier", "esg_high",
                        "post", "did", "lev", "ltd_ratio", "cost_debt",
                        "ln_assets", "roa", "tangibility", "mb", "cash_ratio"}
        assert expected_cols <= set(df.columns)


class TestGenerateDidPanel:
    def test_default_size(self, gf):
        df = gf.generate_did_panel(seed=42)
        assert len(df) == 300  # 30 * 10

    def test_treated_half(self, gf):
        df = gf.generate_did_panel(seed=42, n_firms=20, n_years=5)
        treated = df[df["treat"] == 1]["firm_id"].unique()
        not_treated = df[df["treat"] == 0]["firm_id"].unique()
        assert len(treated) == 10
        assert len(not_treated) == 10

    def test_did_after_treatment(self, gf):
        df = gf.generate_did_panel(seed=42, n_firms=10, n_years=5,
                                    start_year=2015, treat_year=2018)
        # did = treat * post
        for _, row in df.iterrows():
            if row["year"] >= 2018 and row["treat"] == 1:
                assert row["did"] == 1
            elif row["year"] < 2018 or row["treat"] == 0:
                assert row["did"] == 0


class TestReferencesDemo:
    def test_contains_callaway(self, gf):
        assert "callaway2021difference" in gf.REFERENCES_DEMO

    def test_contains_sun_abraham(self, gf):
        assert "sun2021event" in gf.REFERENCES_DEMO

    def test_contains_borusyak(self, gf):
        assert "borusyak2024revisiting" in gf.REFERENCES_DEMO

    def test_contains_abadie(self, gf):
        assert "abadie2010synthetic" in gf.REFERENCES_DEMO

    def test_contains_roth(self, gf):
        assert "roth2023pretest" in gf.REFERENCES_DEMO

    def test_is_bibtex_string(self, gf):
        assert gf.REFERENCES_DEMO.startswith("@")
        assert "doi" in gf.REFERENCES_DEMO.lower()


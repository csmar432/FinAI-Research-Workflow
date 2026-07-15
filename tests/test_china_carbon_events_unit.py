"""Unit tests for scripts/research_framework/china_carbon_events.py."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def cce():
    sys.path.insert(0, str(SCRIPTS_DIR))
    from research_framework import china_carbon_events as c
    yield c
    if str(SCRIPTS_DIR) in sys.path:
        sys.path.remove(str(SCRIPTS_DIR))


class TestChinaNationalETS:
    def test_dict_structure(self, cce):
        d = cce.CHINA_NATIONAL_ETS
        assert d["policy_name"] == "全国碳排放权交易市场"
        assert d["english_name"] == "China National ETS"
        assert d["launch_date"] == date(2021, 7, 16)
        assert d["covered_emissions_pct"] == 40.0

    def test_launch_date_is_date_object(self, cce):
        assert isinstance(cce.CHINA_NATIONAL_ETS["launch_date"], date)

    def test_papers_to_replicate_is_list(self, cce):
        assert isinstance(cce.CHINA_NATIONAL_ETS["papers_to_replicate"], list)


class TestChinaPilotETS:
    def test_dataframe(self, cce):
        df = cce.CHINA_PILOT_ETS
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 7

    def test_expected_columns(self, cce):
        for col in ("city", "province_code", "launch_date", "scope", "key_sectors"):
            assert col in cce.CHINA_PILOT_ETS.columns

    def test_shenzhen_first(self, cce):
        df = cce.CHINA_PILOT_ETS
        shenzhen = df[df["city"] == "深圳"].iloc[0]
        assert shenzhen["province_code"] == 440300
        assert shenzhen["launch_date"] == date(2013, 6, 18)

    def test_hubei_included(self, cce):
        assert "湖北" in cce.CHINA_PILOT_ETS["city"].values
        hubei = cce.CHINA_PILOT_ETS[cce.CHINA_PILOT_ETS["city"] == "湖北"].iloc[0]
        assert hubei["province_code"] == 420000


class TestEuETSPhases:
    def test_dataframe(self, cce):
        df = cce.EU_ETS_PHASES
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 4

    def test_expected_columns(self, cce):
        for col in ("phase", "start", "end", "description"):
            assert col in cce.EU_ETS_PHASES.columns

    def test_phase_1_dates(self, cce):
        df = cce.EU_ETS_PHASES
        p1 = df[df["phase"] == 1].iloc[0]
        assert p1["start"] == date(2005, 1, 1)
        assert p1["end"] == date(2007, 12, 31)

    def test_phase_4_dates(self, cce):
        df = cce.EU_ETS_PHASES
        p4 = df[df["phase"] == 4].iloc[0]
        assert p4["start"] == date(2021, 1, 1)
        assert p4["end"] == date(2030, 12, 31)


class TestCarbonETSConfig:
    def test_default_values(self, cce):
        cfg = cce.CarbonETSConfig()
        assert cfg.treatment_year == 2021
        assert cfg.use_pilots is False
        assert "leverage" in cfg.covariates
        assert cfg.cluster_level == "firm"

    def test_custom_values(self, cce):
        cfg = cce.CarbonETSConfig(treatment_year=2013, use_pilots=True, cluster_level="province")
        assert cfg.treatment_year == 2013
        assert cfg.use_pilots is True
        assert cfg.cluster_level == "province"


class TestBuildCarbonETSPanel:
    def test_adds_did_columns(self, cce):
        df = pd.DataFrame({
            "province_code": [110000, 440000],
            "year": [2020, 2021],
            "y": [0.5, 0.6],
        })
        result = cce.build_carbon_ets_panel(df)
        assert "is_treated" in result.columns
        assert "post" in result.columns
        assert "did" in result.columns

    def test_national_ets_all_provinces(self, cce):
        df = pd.DataFrame({
            "province_code": [110000, 440000, 310000],
            "year": [2020, 2021, 2022],
            "y": [0.1, 0.2, 0.3],
        })
        result = cce.build_carbon_ets_panel(df)
        # National ETS: all provinces treated
        assert all(result["is_treated"] == 1)

    def test_pilots_staggered(self, cce):
        cfg = cce.CarbonETSConfig(use_pilots=True)
        # Province 440300 = Shenzhen (pilot)
        # Province 310000 = Shanghai (pilot)
        # Province 110000 = Beijing (pilot)
        df = pd.DataFrame({
            "province_code": [440300, 310000, 110000],
            "year": [2013, 2014, 2015],
            "y": [0.1, 0.2, 0.3],
        })
        result = cce.build_carbon_ets_panel(df, config=cfg)
        # All are pilot provinces
        assert all(result["is_treated"] == 1)

    def test_did_interaction(self, cce):
        df = pd.DataFrame({
            "province_code": [110000, 110000],
            "year": [2020, 2021],
            "y": [0.5, 0.6],
        })
        result = cce.build_carbon_ets_panel(df)
        # National ETS 2021: 2020 pre (post=0), 2021 post (post=1)
        assert result.iloc[0]["post"] == 0
        assert result.iloc[1]["post"] == 1
        assert result.iloc[1]["did"] == 1  # is_treated * post = 1 * 1

    def test_returns_copy(self, cce):
        df = pd.DataFrame({
            "province_code": [110000],
            "year": [2021],
            "y": [0.5],
        })
        result = cce.build_carbon_ets_panel(df)
        assert result is not df
        assert "is_treated" in result.columns


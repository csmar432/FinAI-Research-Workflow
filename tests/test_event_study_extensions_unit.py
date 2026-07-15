"""Unit tests for scripts/research_framework/event_study_extensions.py."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def ese():
    sys.path.insert(0, str(SCRIPTS_DIR))
    from research_framework import event_study_extensions as e
    yield e
    if str(SCRIPTS_DIR) in sys.path:
        sys.path.remove(str(SCRIPTS_DIR))


class TestDataclasses:
    def test_bmp_result_fields(self, ese):
        r = ese.BMPResult(
            standardised_car=np.array([1.0, 2.0]),
            t_stat=3.5,
            p_value=0.01,
        )
        assert r.t_stat == 3.5
        assert r.p_value == 0.01
        assert len(r.standardised_car) == 2

    def test_kolari_result_fields(self, ese):
        r = ese.KolariPynnonenResult(t_stat_adjusted=2.0, p_value=0.05)
        assert r.t_stat_adjusted == 2.0
        assert r.p_value == 0.05

    def test_sign_rank_result_fields(self, ese):
        r = ese.SignRankResult(statistic=1.5, p_value=0.1)
        assert r.statistic == 1.5
        assert r.p_value == 0.1


class TestBMPStandardise:
    def test_basic_calculation(self, ese):
        cars = np.array([0.01, 0.02, 0.03])
        std = np.array([0.01, 0.01, 0.01])
        result = ese.bmp_standardise(cars, std)
        assert isinstance(result, ese.BMPResult)
        assert len(result.standardised_car) == 3

    def test_zeros_std(self, ese):
        cars = np.array([0.01, 0.02])
        std = np.array([0.0, 0.0])  # Zero std → division by zero
        result = ese.bmp_standardise(cars, std)
        assert isinstance(result, ese.BMPResult)
        assert len(result.standardised_car) == 2

    def test_negative_cars(self, ese):
        cars = np.array([-0.01, -0.02, -0.03])
        std = np.array([0.01, 0.01, 0.01])
        result = ese.bmp_standardise(cars, std)
        assert isinstance(result, ese.BMPResult)


class TestKolariPynnonen:
    def test_basic_calculation(self, ese):
        cars = np.array([0.01, 0.02, 0.03])  # 1D: N firms
        # estimation_window_returns: 2D (N, T estimation days)
        est_returns = np.array([
            [0.01, 0.02, 0.01],
            [0.01, 0.01, 0.02],
            [0.02, 0.01, 0.01],
        ])
        result = ese.kolari_pynnonen_adjust(cars, est_returns)
        assert isinstance(result, ese.KolariPynnonenResult)

    def test_returns_float(self, ese):
        cars = np.array([0.01, 0.02, 0.03])
        est_returns = np.array([
            [0.01, 0.02, 0.01],
            [0.01, 0.01, 0.02],
            [0.02, 0.01, 0.01],
        ])
        kp = ese.kolari_pynnonen_adjust(cars, est_returns)
        assert isinstance(kp.t_stat_adjusted, float)


class TestSignRank:
    def test_basic(self, ese):
        cars = np.array([0.01, 0.02, -0.005])
        result = ese.generalized_sign_test(cars)
        assert isinstance(result, ese.SignRankResult)

    def test_all_positive(self, ese):
        cars = np.array([0.01, 0.02, 0.03])
        result = ese.generalized_sign_test(cars)
        assert result.p_value >= 0

    def test_all_zero(self, ese):
        cars = np.array([0.0, 0.0, 0.0])
        result = ese.generalized_sign_test(cars)
        assert result.p_value >= 0
        assert result.p_value <= 1


class TestRankTest:
    def test_basic(self, ese):
        cars = np.array([0.01, 0.02, -0.005, 0.03])
        result = ese.rank_test(cars)
        assert isinstance(result.statistic, float)
        assert 0 <= result.p_value <= 1


"""Unit tests for scripts/benchmark_econometrics.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def be():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts import benchmark_econometrics as b
    yield b
    if _p in sys.path:
        sys.path.remove(_p)


class TestBenchmarkResult:
    def test_init(self, be):
        r = be.BenchmarkResult(
            method="DID",
            project_estimate=0.15,
            reference_estimate=0.16,
            max_abs_diff=0.01,
            tolerance=0.05,
            passed=True,
            details={"n_obs": 1000},
            elapsed_ms=120.5,
        )
        assert r.method == "DID"
        assert r.passed is True
        assert abs(r.project_estimate - 0.15) < 1e-9

    def test_default_details_and_elapsed(self, be):
        r = be.BenchmarkResult(
            method="RDD",
            project_estimate=0.1,
            reference_estimate=0.1,
            max_abs_diff=0.0,
            tolerance=0.01,
            passed=True,
        )
        assert r.details == {}
        assert r.elapsed_ms == 0.0

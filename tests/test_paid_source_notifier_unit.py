"""Unit tests for scripts/core/paid_source_notifier.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def psn():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts.core import paid_source_notifier as p
    yield p
    if _p in sys.path:
        sys.path.remove(_p)


class TestPaidSourceSpec:
    def test_dataclass_fields(self, psn):
        spec = psn.PaidSourceSpec(
            server="test-server",
            display_name="Test",
            env_var="TEST_KEY",
            cost="free",
            get_url="https://test.com",
            fallback="mock",
            impact="testing",
        )
        assert spec.server == "test-server"
        assert spec.env_var == "TEST_KEY"
        assert spec.fallback == "mock"

    def test_frozen_dataclass(self, psn):
        spec = psn.PAID_SOURCE_REGISTRY.get("user-tushare")
        assert spec is not None
        # frozen=True means immutable
        with pytest.raises(Exception):  # dataclasses.FrozenInstanceError
            spec.server = "hacked"


class TestPaidSourceRegistry:
    def test_registry_is_dict(self, psn):
        assert isinstance(psn.PAID_SOURCE_REGISTRY, dict)
        assert len(psn.PAID_SOURCE_REGISTRY) > 0

    def test_tushare_registered(self, psn):
        assert "user-tushare" in psn.PAID_SOURCE_REGISTRY

    def test_all_specs_have_required_fields(self, psn):
        for name, spec in psn.PAID_SOURCE_REGISTRY.items():
            assert spec.server == name
            assert spec.env_var
            assert spec.cost
            assert spec.get_url
            assert spec.fallback
            assert spec.impact

    def test_all_specs_have_env_vars(self, psn):
        # All specs should have an env_var set
        for name, spec in psn.PAID_SOURCE_REGISTRY.items():
            assert spec.env_var, f"{name} missing env_var"

    def test_no_empty_fallbacks(self, psn):
        for name, spec in psn.PAID_SOURCE_REGISTRY.items():
            assert spec.fallback, f"{name} has empty fallback"


class TestSuppressionFlag:
    def test_suppression_from_env(self, psn):
        # If FINAI_SUPPRESS_PAID_WARNINGS=1 is set, _SUPPRESSED is True
        assert isinstance(psn._SUPPRESSED, bool)


class TestPaidNotifier:
    def test_paid_notifier_instance_exists(self, psn):
        assert hasattr(psn, "paid_notifier")
        assert psn.paid_notifier is not None

    def test_paid_notifier_is_paid_notifier_class(self, psn):
        assert isinstance(psn.paid_notifier, psn.PaidSourceNotifier)


"""Unit tests for scripts/research_framework/a_share_firm_controls.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def afc():
    sys.path.insert(0, str(SCRIPTS_DIR))
    from research_framework import a_share_firm_controls as a
    yield a
    if str(SCRIPTS_DIR) in sys.path:
        sys.path.remove(str(SCRIPTS_DIR))


class TestFirmControl:
    def test_dataclass_fields(self, afc):
        ctrl = afc.FirmControl(
            name="test", chinese_name="测试",
            formula="x", typical_sign="+",
            csmar_field="test_field",
        )
        assert ctrl.name == "test"
        assert ctrl.typical_sign == "+"
        assert ctrl.papers == []

    def test_default_notes_empty(self, afc):
        ctrl = afc.FirmControl(
            name="test", chinese_name="测试",
            formula="x", typical_sign="-",
            csmar_field="y",
        )
        assert ctrl.notes == ""


class TestControlConstants:
    def test_size_defined(self, afc):
        s = afc.SIZE
        assert s.name == "size"
        assert s.typical_sign == "+"
        assert "log" in s.formula.lower()

    def test_age_defined(self, afc):
        a = afc.AGE
        assert a.name == "age"
        assert a.csmar_field

    def test_leverage_defined(self, afc):
        l = afc.LEVERAGE
        assert hasattr(l, "name")
        assert l.typical_sign in ["+", "-", "+/-", "?"]

    def test_roa_defined(self, afc):
        r = afc.ROA
        assert r.name == "roa"


class TestAllControlsHaveValidSigns:
    def test_all_controls_have_valid_sign(self, afc):
        """All FirmControl instances should have valid typical_sign."""
        controls = [v for k, v in vars(afc).items()
                   if isinstance(v, afc.FirmControl)]
        valid_signs = {"+", "-", "+/-", "?"}
        for c in controls:
            assert c.typical_sign in valid_signs, f"{c.name} has invalid sign"

    def test_all_controls_have_csmar_field(self, afc):
        controls = [v for k, v in vars(afc).items()
                   if isinstance(v, afc.FirmControl)]
        for c in controls:
            assert c.csmar_field, f"{c.name} missing csmar_field"


class TestControlDictionary:
    def test_all_controls_returns_dict(self, afc):
        if hasattr(afc, "all_controls"):
            d = afc.all_controls()
            assert isinstance(d, dict)
            assert len(d) > 0
            for name, ctrl in d.items():
                assert isinstance(ctrl, afc.FirmControl)
                assert ctrl.name == name


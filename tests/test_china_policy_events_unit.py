"""Unit tests for scripts/research_framework/china_policy_events.py."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def cpe():
    sys.path.insert(0, str(SCRIPTS_DIR))
    from research_framework import china_policy_events as c
    yield c
    if str(SCRIPTS_DIR) in sys.path:
        sys.path.remove(str(SCRIPTS_DIR))


class TestChinaPolicyEvent:
    def test_dataclass_fields(self, cpe):
        evt = cpe.ChinaPolicyEvent(
            name="Test",
            english_name="Test Event",
            launch_date=date(2020, 1, 1),
            scope="test scope",
            treated_provinces=[110000],
            treated_industries=["G54"],
            expected_effect="effect",
            example_papers=["10.1234/test"],
            data_sources=["CSMAR"],
        )
        assert evt.name == "Test"
        assert evt.launch_date == date(2020, 1, 1)
        assert 110000 in evt.treated_provinces
        assert evt.example_papers == ["10.1234/test"]

    def test_default_notes(self, cpe):
        evt = cpe.ChinaPolicyEvent(
            name="Test",
            english_name="Test",
            launch_date=date(2020, 1, 1),
            scope="x",
            treated_provinces=[],
            treated_industries=[],
            expected_effect="x",
            example_papers=[],
            data_sources=[],
        )
        assert evt.notes == ""


class TestPolicyEvents:
    def test_ying_gai_zeng_exists(self, cpe):
        e = cpe.YING_GAI_ZENG
        assert e.name == "营改增"
        assert e.launch_date == date(2012, 1, 1)
        assert 310000 in e.treated_provinces

    def test_tan_da_feng_exists(self, cpe):
        e = cpe.TAN_DA_FENG
        assert isinstance(e.launch_date, date)
        assert isinstance(e.treated_provinces, list)

    def test_all_event_variables_are_instances(self, cpe):
        event_names = [n for n in dir(cpe) if n.isupper() and not n.startswith("_")]
        for name in event_names:
            if name == "ALL_EVENTS":
                continue  # This is a list, not an event
            evt = getattr(cpe, name)
            assert isinstance(evt, cpe.ChinaPolicyEvent), f"{name} is not a ChinaPolicyEvent"

    def test_all_events_have_launch_dates(self, cpe):
        event_names = [n for n in dir(cpe) if n.isupper() and not n.startswith("_") and n != "ALL_EVENTS"]
        for name in event_names:
            evt = getattr(cpe, name)
            assert isinstance(evt.launch_date, date), f"{name} has invalid launch_date"

    def test_all_events_have_data_sources(self, cpe):
        event_names = [n for n in dir(cpe) if n.isupper() and not n.startswith("_") and n != "ALL_EVENTS"]
        for name in event_names:
            evt = getattr(cpe, name)
            assert isinstance(evt.data_sources, list), f"{name} has invalid data_sources"
            assert len(evt.data_sources) > 0, f"{name} has no data_sources"

    def test_all_events_dict(self, cpe):
        assert isinstance(cpe.ALL_EVENTS, dict)
        assert len(cpe.ALL_EVENTS) > 0
        for name, evt in cpe.ALL_EVENTS.items():
            assert isinstance(evt, cpe.ChinaPolicyEvent)
            assert isinstance(evt.launch_date, date)


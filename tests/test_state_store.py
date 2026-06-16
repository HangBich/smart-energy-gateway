"""
Unit tests for StateStore
"""

import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "energy_gateway"))

import pytest
from state_store import StateStore


@pytest.fixture
def store(tmp_path):
    return StateStore(persist_path=str(tmp_path / "state.json"))


class TestMeterState:
    def test_update_and_get(self, store):
        data = {"load_id": "hvac", "device_id": "meter-hvac", "power_watt": 1200.0, "switch": "on"}
        store.update_meter("hvac", data)
        states = store.get_meter_states()
        assert "hvac" in states
        assert states["hvac"]["power_watt"] == 1200.0

    def test_load_switch_update(self, store):
        store.update_meter("hvac", {"load_id": "hvac", "power_watt": 1000.0})
        store.update_load_switch("hvac", "off", "overload_shedding")
        states = store.get_meter_states()
        assert states["hvac"]["switch"] == "off"
        assert states["hvac"]["last_reason"] == "overload_shedding"

    def test_multiple_loads(self, store):
        for lid in ["hvac", "lighting", "plug"]:
            store.update_meter(lid, {"load_id": lid, "power_watt": 100.0})
        assert sorted(store.get_load_ids()) == ["hvac", "lighting", "plug"]


class TestSolarState:
    def test_update_solar(self, store):
        store.update_solar({"power_watt": 850.0})
        assert store.get_solar_power() == 850.0

    def test_default_solar_power(self, store):
        assert store.get_solar_power() == 0.0


class TestEvents:
    def test_add_and_get_events(self, store):
        ev = {"event_type": "overload_detected", "severity": "warning",
              "load_id": "system", "value": 3800.0}
        store.add_event(ev)
        events = store.get_events()
        assert len(events) == 1
        assert events[0]["event_type"] == "overload_detected"

    def test_filter_events_by_load(self, store):
        store.add_event({"event_type": "x", "load_id": "hvac"})
        store.add_event({"event_type": "y", "load_id": "plug"})
        hvac_events = store.get_events(load_id="hvac")
        assert all(e["load_id"] == "hvac" for e in hvac_events)

    def test_event_limit(self, store):
        for i in range(250):
            store.add_event({"event_type": "test", "load_id": "system", "i": i})
        events = store.get_events()
        assert len(events) <= 50   # default limit

    def test_capped_at_200_internally(self, store):
        for i in range(250):
            store.add_event({"event_type": "test", "load_id": "system", "i": i})
        # Internal buffer capped at 200
        all_events = store.get_events(limit=300)
        assert len(all_events) <= 200


class TestPersistence:
    def test_state_persisted_to_file(self, store, tmp_path):
        store.update_meter("hvac", {"load_id": "hvac", "power_watt": 999.0})
        state_file = tmp_path / "state.json"
        assert state_file.exists()

    def test_summary_persisted(self, store):
        store.update_summary({"total_power_watt": 2500.0, "overload": False})
        summary = store.get_summary()
        assert summary["total_power_watt"] == 2500.0

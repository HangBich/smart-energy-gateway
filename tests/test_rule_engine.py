"""
Unit tests for the Rule Engine — bonus điểm khuyến khích
Run: python -m pytest tests/ -v
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "energy_gateway"))

import pytest
from rule_engine import RuleEngine, RuleAction, RuleResult


# ── Fixtures ──────────────────────────────────────────────────────────────────
def make_meter_states(
    hvac_power=1200.0, hvac_switch="on", hvac_priority="low",
    lighting_power=400.0, lighting_switch="on", lighting_priority="medium",
    plug_power=800.0, plug_switch="on", plug_priority="low",
):
    return {
        "hvac": {
            "load_id": "hvac", "power_watt": hvac_power,
            "switch": hvac_switch, "priority": hvac_priority,
            "last_reason": "",
        },
        "lighting": {
            "load_id": "lighting", "power_watt": lighting_power,
            "switch": lighting_switch, "priority": lighting_priority,
            "last_reason": "",
        },
        "plug": {
            "load_id": "plug", "power_watt": plug_power,
            "switch": plug_switch, "priority": plug_priority,
            "last_reason": "",
        },
    }


@pytest.fixture
def engine():
    return RuleEngine(overload_threshold=3500.0)


# ── Rule 1: Total power calculation ──────────────────────────────────────────
class TestTotalPowerCalculation:
    def test_total_power_all_on(self, engine):
        states = make_meter_states(hvac_power=1200, lighting_power=400, plug_power=800)
        _, total, _ = engine.evaluate(states, solar_power=0.0)
        assert total == pytest.approx(2400.0, abs=1.0)

    def test_total_power_excludes_off_loads(self, engine):
        states = make_meter_states(hvac_power=1200, hvac_switch="off",
                                   lighting_power=400, plug_power=800)
        _, total, _ = engine.evaluate(states, solar_power=0.0)
        assert total == pytest.approx(1200.0, abs=1.0)

    def test_grid_power_reduced_by_solar(self, engine):
        states = make_meter_states(hvac_power=1200, lighting_power=400, plug_power=800)
        _, total, grid = engine.evaluate(states, solar_power=500.0)
        assert grid == pytest.approx(total - 500.0, abs=1.0)

    def test_grid_power_never_negative(self, engine):
        states = make_meter_states(hvac_power=100, lighting_power=50, plug_power=50)
        _, total, grid = engine.evaluate(states, solar_power=2000.0)
        assert grid >= 0.0


# ── Rule 2: Overload detection ────────────────────────────────────────────────
class TestOverloadDetection:
    def test_overload_event_generated(self, engine):
        # 1200 + 1800 + 1000 = 4000 > 3500
        states = make_meter_states(hvac_power=1200, lighting_power=1800, plug_power=1000)
        result, _, _ = engine.evaluate(states, solar_power=0.0)
        event_types = [e.event_type for e in result.events]
        assert "overload_detected" in event_types

    def test_no_overload_event_below_threshold(self, engine):
        states = make_meter_states(hvac_power=1200, lighting_power=400, plug_power=800)
        result, _, _ = engine.evaluate(states, solar_power=0.0)
        event_types = [e.event_type for e in result.events]
        assert "overload_detected" not in event_types

    def test_overload_event_has_correct_severity(self, engine):
        states = make_meter_states(hvac_power=2000, lighting_power=1000, plug_power=800)
        result, _, _ = engine.evaluate(states, solar_power=0.0)
        overload_events = [e for e in result.events if e.event_type == "overload_detected"]
        assert len(overload_events) == 1
        assert overload_events[0].severity == "warning"

    def test_overload_threshold_configurable(self):
        engine_low = RuleEngine(overload_threshold=2000.0)
        states = make_meter_states(hvac_power=1200, lighting_power=400, plug_power=800)
        result, _, _ = engine_low.evaluate(states, solar_power=0.0)
        event_types = [e.event_type for e in result.events]
        assert "overload_detected" in event_types

    def test_update_threshold(self, engine):
        engine.update_threshold(5000.0)
        assert engine.overload_threshold == 5000.0
        states = make_meter_states(hvac_power=2000, lighting_power=1000, plug_power=800)
        result, _, _ = engine.evaluate(states, solar_power=0.0)
        event_types = [e.event_type for e in result.events]
        assert "overload_detected" not in event_types


# ── Rule 3: Overload shedding ─────────────────────────────────────────────────
class TestOverloadShedding:
    def test_low_priority_shed_first(self, engine):
        # Total = 4200W > 3500W threshold
        states = make_meter_states(
            hvac_power=2000, hvac_priority="low",
            lighting_power=1200, lighting_priority="medium",
            plug_power=1000, plug_priority="low",
        )
        result, _, _ = engine.evaluate(states, solar_power=0.0)
        shed_ids = [a.load_id for a in result.actions if a.action == "off"]
        # hvac and/or plug (both low) should be shed before lighting
        for sid in shed_ids:
            ms = states[sid]
            assert ms["priority"] in ("low",), \
                f"Expected low-priority shed, got {ms['priority']} for {sid}"

    def test_shed_action_has_correct_reason(self, engine):
        states = make_meter_states(hvac_power=2000, lighting_power=1200, plug_power=1000)
        result, _, _ = engine.evaluate(states, solar_power=0.0)
        shed_actions = [a for a in result.actions if a.action == "off"]
        for action in shed_actions:
            assert action.reason == "overload_shedding"

    def test_no_shedding_when_normal(self, engine):
        states = make_meter_states(hvac_power=1000, lighting_power=300, plug_power=500)
        result, _, _ = engine.evaluate(states, solar_power=0.0)
        shed_actions = [a for a in result.actions if a.action == "off"]
        assert len(shed_actions) == 0


# ── Rule 4: Solar surplus restore ────────────────────────────────────────────
class TestSolarRestore:
    def test_restore_when_solar_high(self, engine):
        states = make_meter_states(
            hvac_power=500, hvac_switch="off",
            lighting_power=300, lighting_switch="on",
            plug_power=400, plug_switch="on",
        )
        # Mark hvac as shed by overload
        states["hvac"]["last_reason"] = "overload_shedding"
        result, _, _ = engine.evaluate(states, solar_power=1200.0)
        restore_actions = [a for a in result.actions if a.action == "on"]
        assert any(a.load_id == "hvac" for a in restore_actions)

    def test_no_restore_when_solar_low(self, engine):
        states = make_meter_states(hvac_power=1200, hvac_switch="off")
        states["hvac"]["last_reason"] = "overload_shedding"
        result, _, _ = engine.evaluate(states, solar_power=100.0)
        restore_actions = [a for a in result.actions if a.action == "on"]
        assert len(restore_actions) == 0

    def test_restore_event_generated(self, engine):
        states = make_meter_states(hvac_power=200, hvac_switch="off")
        states["hvac"]["last_reason"] = "overload_shedding"
        result, _, _ = engine.evaluate(states, solar_power=1000.0)
        event_types = [e.event_type for e in result.events]
        assert "load_restored" in event_types


# ── Edge cases ────────────────────────────────────────────────────────────────
class TestEdgeCases:
    def test_empty_meter_states(self, engine):
        result, total, grid = engine.evaluate({}, solar_power=0.0)
        assert total == 0.0
        assert grid == 0.0
        assert result.actions == []
        assert result.events == []

    def test_all_loads_off(self, engine):
        states = make_meter_states(
            hvac_switch="off", lighting_switch="off", plug_switch="off"
        )
        result, total, _ = engine.evaluate(states, solar_power=0.0)
        assert total == 0.0

    def test_overload_value_in_event(self, engine):
        states = make_meter_states(hvac_power=2000, lighting_power=1000, plug_power=800)
        result, total, _ = engine.evaluate(states, solar_power=0.0)
        overload_ev = next(e for e in result.events if e.event_type == "overload_detected")
        assert overload_ev.value == pytest.approx(total, abs=1.0)
        assert overload_ev.threshold == 3500.0

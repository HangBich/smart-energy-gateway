"""
State Store — thread-safe in-memory state management for the energy gateway.
Also persists to a JSON file so the REST API can read it.
"""

import json
import logging
import os
import threading
import time
from typing import Any, Optional

logger = logging.getLogger("state-store")

STATE_FILE = os.environ.get("GATEWAY_STATE_FILE", "/tmp/gateway_state.json")


class StateStore:
    def __init__(self, persist_path: str = STATE_FILE):
        self._lock = threading.RLock()
        self._persist_path = persist_path

        # meter_states: {load_id: {...telemetry...}}
        self._meter_states: dict[str, dict] = {}
        # last_seen: {load_id: float (unix timestamp)}
        self._last_seen: dict[str, float] = {}
        # solar state
        self._solar: dict = {}
        # energy summary
        self._summary: dict = {}
        # recent events (last 200)
        self._events: list[dict] = []
        # load switch state (driven by actuator status messages)
        self._load_switch: dict[str, str] = {}
        # last shed reason per load
        self._last_reason: dict[str, str] = {}

    # ── Meter state ──────────────────────────────────────────────────────────
    def update_meter(self, load_id: str, data: dict) -> None:
        with self._lock:
            # Preserve switch state from actuator, but merge telemetry
            existing_switch = self._load_switch.get(load_id, "on")
            self._meter_states[load_id] = {**data, "switch": existing_switch,
                                            "last_reason": self._last_reason.get(load_id, "")}
            self._last_seen[load_id] = time.time()
        self._persist()

    def update_load_switch(self, load_id: str, switch: str, reason: str = "") -> None:
        with self._lock:
            self._load_switch[load_id] = switch
            self._last_reason[load_id] = reason
            if load_id in self._meter_states:
                self._meter_states[load_id]["switch"] = switch
                self._meter_states[load_id]["last_reason"] = reason
        self._persist()

    def get_meter_states(self) -> dict[str, dict]:
        with self._lock:
            return dict(self._meter_states)

    def get_load_ids(self) -> list[str]:
        with self._lock:
            return list(self._meter_states.keys())

    def get_last_seen(self, load_id: str) -> Optional[float]:
        with self._lock:
            return self._last_seen.get(load_id)

    # ── Solar ────────────────────────────────────────────────────────────────
    def update_solar(self, data: dict) -> None:
        with self._lock:
            self._solar = data
        self._persist()

    def get_solar(self) -> dict:
        with self._lock:
            return dict(self._solar)

    def get_solar_power(self) -> float:
        with self._lock:
            return self._solar.get("power_watt", 0.0)

    # ── Summary ──────────────────────────────────────────────────────────────
    def update_summary(self, summary: dict) -> None:
        with self._lock:
            self._summary = summary
        self._persist()

    def get_summary(self) -> dict:
        with self._lock:
            return dict(self._summary)

    # ── Events ───────────────────────────────────────────────────────────────
    def add_event(self, event: dict) -> None:
        with self._lock:
            self._events.append(event)
            if len(self._events) > 200:
                self._events = self._events[-200:]
        self._persist()

    def get_events(self, load_id: Optional[str] = None, limit: int = 50) -> list[dict]:
        with self._lock:
            events = list(self._events)
        if load_id:
            events = [e for e in events if e.get("load_id") == load_id]
        return events[-limit:]

    # ── Persistence ──────────────────────────────────────────────────────────
    def _persist(self) -> None:
        try:
            with self._lock:
                snapshot = {
                    "meter_states": self._meter_states,
                    "solar":        self._solar,
                    "summary":      self._summary,
                    "events":       self._events[-50:],
                    "load_switch":  self._load_switch,
                }
            os.makedirs(os.path.dirname(self._persist_path), exist_ok=True)
            tmp = self._persist_path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(snapshot, f, default=str)
            os.replace(tmp, self._persist_path)
        except Exception as exc:
            logger.warning("State persist failed: %s", exc)

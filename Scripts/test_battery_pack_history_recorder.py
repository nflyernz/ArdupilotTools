"""Focused tests for whole-BIN Battery Pack history ingestion."""

from collections import Counter
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from core import battery_pack_history_recorder
from core.battery import (
    BatteryLoadEventType,
    BatteryLoadInterval,
    BatteryProcessor,
    BatterySessionConfiguration,
    TakeoffType,
)
from core.battery_pack_history import BatteryPackHistoryStore
from core.battery_pack_history_recorder import BatteryPackHistoryRecorder
from core.battery_pack_store import BatteryPackStore, fingerprint_log
from core.config import Config
from core.flight_data import FlightLog
from core.flight_window import FlightWindow
from core.log_reader import FlightReader


def _event(window, flight_number, instance, event_type, takeoff_type):
    start_us = window.start_us + 1_000_000
    end_us = window.start_us + 2_000_000
    return BatteryLoadInterval(
        event_type=event_type,
        takeoff_type=takeoff_type,
        flight_number=flight_number,
        instance=instance,
        start_us=start_us,
        end_us=end_us,
        duration_s=1.0,
        consumed_mah_at_start=100.0,
        pre_load_voltage=16.0,
        minimum_voltage=14.5,
        current_at_minimum_voltage=19.0,
        peak_current=20.0,
        average_current=18.0,
        maximum_throttle=100.0,
        average_throttle=95.0,
        voltage_sag=1.5,
        recovery_time_us=window.start_us + 3_000_000,
        voltage_after_recovery=15.0,
        voltage_recovery=0.5,
        low_voltage_margin=1.3,
        critical_voltage_margin=1.7,
    )


def _configuration():
    return BatterySessionConfiguration(
        lookup_time_us=1_000_000,
        capacity_mah=5000.0,
        low_voltage=13.2,
        critical_voltage=12.8,
        failsafe_voltage_source=0.0,
        warnings=("copied warning",),
    )


class _StoreSpy:
    def __init__(self):
        self.calls = []

    def add_observations(self, observations):
        self.calls.append(list(observations))
        return len(observations)


def test_recorder_processes_all_flights_and_instances_in_one_batch(monkeypatch):
    windows = [
        FlightWindow(10_000_000, 20_000_000),
        FlightWindow(30_000_000, 40_000_000),
    ]
    flight_log = FlightLog(flights=windows)
    calls = []

    class FakeProcessor:
        def __init__(self, _log, window, instance, config=None):
            self.window = window
            self.instance = instance
            calls.append((window, instance, config))

        def available_instances(self):
            return [0, 1]

        def analyse(self):
            flight_number = windows.index(self.window) + 1
            return SimpleNamespace(
                session_configuration=_configuration(),
                load_event=object(),
                bounded_load_events=[
                    _event(
                        self.window,
                        flight_number,
                        self.instance,
                        BatteryLoadEventType.TAKEOFF,
                        TakeoffType.AUTO,
                    ),
                    _event(
                        self.window,
                        flight_number,
                        self.instance,
                        BatteryLoadEventType.SUSTAINED_HIGH_THROTTLE,
                        None,
                    ),
                ],
            )

    monkeypatch.setattr(
        battery_pack_history_recorder, "BatteryProcessor", FakeProcessor
    )
    store = _StoreSpy()

    added = BatteryPackHistoryRecorder(object()).record(
        flight_log,
        Path("missing.bin"),
        "1" * 64,
        "Pack A",
        store,
    )

    assert added == 4
    assert len(store.calls) == 1
    observations = store.calls[0]
    assert {(item.flight_number, item.battery_instance) for item in observations} == {
        (1, 0),
        (1, 1),
        (2, 0),
        (2, 1),
    }
    assert all(item.event_type == "TAKEOFF" for item in observations)
    assert all(item.takeoff_type == "AUTO" for item in observations)
    assert all(item.recorded_at_utc is None for item in observations)
    assert all(item.gps_anchor_week is None for item in observations)
    assert all(item.configured_capacity_mah == 5000.0 for item in observations)
    assert all(item.configuration_warnings == ("copied warning",) for item in observations)
    assert len(calls) == 5  # One instance probe plus four analyses.


def test_processor_failure_before_final_store_call_commits_nothing(monkeypatch):
    windows = [
        FlightWindow(10_000_000, 20_000_000),
        FlightWindow(30_000_000, 40_000_000),
    ]
    flight_log = FlightLog(flights=windows)

    class FailingProcessor:
        def __init__(self, _log, window, instance, config=None):
            self.window = window
            self.instance = instance

        def available_instances(self):
            return [0]

        def analyse(self):
            if self.window is windows[1]:
                raise RuntimeError("later FlightWindow failed")
            return SimpleNamespace(
                session_configuration=_configuration(),
                bounded_load_events=[
                    _event(
                        self.window,
                        1,
                        self.instance,
                        BatteryLoadEventType.TAKEOFF,
                        TakeoffType.AUTO,
                    )
                ],
            )

    monkeypatch.setattr(
        battery_pack_history_recorder, "BatteryProcessor", FailingProcessor
    )
    store = _StoreSpy()

    with pytest.raises(RuntimeError, match="later FlightWindow failed"):
        BatteryPackHistoryRecorder(object()).record(
            flight_log,
            Path("missing.bin"),
            "1" * 64,
            "Pack A",
            store,
        )

    assert store.calls == []


def test_history_ingestion_does_not_change_battery_analysis(tmp_path):
    window = FlightWindow(10_000_000, 20_000_000)
    flight_log = FlightLog(
        messages={
            "BAT": pd.DataFrame(
                [
                    {
                        "TimeUS": 10_000_000,
                        "Inst": 0,
                        "Volt": 16.0,
                        "Curr": 2.0,
                        "CurrTot": 100.0,
                        "EnrgTot": 10.0,
                    },
                    {
                        "TimeUS": 20_000_000,
                        "Inst": 0,
                        "Volt": 15.0,
                        "Curr": 4.0,
                        "CurrTot": 110.0,
                        "EnrgTot": 11.0,
                    },
                ]
            )
        },
        flights=[window],
    )
    config = Config("Config/battery.yaml")
    before = BatteryProcessor(flight_log, window, 0, config=config).analyse()

    added = BatteryPackHistoryRecorder(config).record(
        flight_log,
        Path("synthetic.bin"),
        "1" * 64,
        "Pack A",
        BatteryPackHistoryStore(tmp_path / "history.json"),
    )
    after = BatteryProcessor(flight_log, window, 0, config=config).analyse()

    assert added == 0
    assert before is not None and after is not None
    assert asdict(after) == asdict(before)


def test_five_log_pack_history_regression(tmp_path):
    expected_counts = {
        "log_0": 3,
        "log_11": 1,
        "log_17": 4,
        "log_19": 1,
        "log_26": 4,
    }
    expected_packs = {
        "log_0": "50S-P1",
        "log_11": "LIPO-2600-01",
        "log_17": "LIPO-3900-01",
        "log_19": "LIPO-3900-01",
        "log_26": "LIPO-3900-01",
    }
    config = Config("Config/battery.yaml")
    history = BatteryPackHistoryStore(tmp_path / "battery_pack_history.json")
    pack_store = BatteryPackStore(tmp_path / "battery_packs.json")
    loaded = []
    added_by_log = {}

    for log_name, expected_count in expected_counts.items():
        path = Path("Logs") / f"{log_name}.bin"
        fingerprint = fingerprint_log(path)
        pack_id = expected_packs[log_name]
        if pack_id not in pack_store.pack_ids:
            pack_store.create_and_associate(fingerprint, pack_id)
        else:
            pack_store.associate(fingerprint, pack_id)
        flight_log = FlightReader(str(path), config=config).read()
        loaded.append((path, fingerprint, pack_id, flight_log))
        added_by_log[log_name] = BatteryPackHistoryRecorder(config).record(
            flight_log,
            path,
            fingerprint,
            pack_id,
            history,
        )
        assert added_by_log[log_name] == expected_count

    observations = history.observations
    ownership = Counter(
        pack_store.association_for(item.source_sha256).pack_id
        for item in observations
    )
    dates = {item.recorded_at_utc[:10] for item in observations}

    assert added_by_log == expected_counts
    assert len(observations) == 13
    assert sum(item.recorded_at_utc is not None for item in observations) == 13
    assert ownership == {
        "50S-P1": 3,
        "LIPO-2600-01": 1,
        "LIPO-3900-01": 9,
    }
    assert dates == {
        "2026-06-13",
        "2026-06-27",
        "2026-07-04",
        "2026-08-01",
        "2026-09-05",
    }

    second_added = sum(
        BatteryPackHistoryRecorder(config).record(
            flight_log,
            path,
            fingerprint,
            pack_id,
            history,
        )
        for path, fingerprint, pack_id, flight_log in loaded
    )
    assert second_added == 0
    assert len(history.observations) == 13

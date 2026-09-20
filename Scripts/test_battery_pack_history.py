"""Focused tests for durable Battery Pack Performance persistence."""

import dataclasses
import json
from datetime import timedelta

import pytest

from core import battery_pack_history, gps_time
from core.battery_pack_history import (
    ANALYSIS_SEMANTICS_VERSION,
    OBSERVATION_SCHEMA_VERSION,
    BatteryPackHistoryError,
    BatteryPackHistoryFormatError,
    BatteryPackHistoryStore,
    BatteryPackObservation,
    event_key_for,
    observation_id_for,
)
from core.gps_time import format_utc_milliseconds, gps_week_time_to_utc


def _observation(
    *,
    source_sha256="1" * 64,
    source_filename="log.bin",
    pack_id="Pack A",
    semantics=ANALYSIS_SEMANTICS_VERSION,
    flight_start_us=1_000_000,
    flight_end_us=5_000_000,
    battery_instance=0,
    event_start_us=2_000_000,
    event_end_us=3_000_000,
):
    identity = {
        "source_sha256": source_sha256,
        "battery_instance": battery_instance,
        "flight_start_us": flight_start_us,
        "flight_end_us": flight_end_us,
        "event_type": "TAKEOFF",
        "takeoff_type": "AUTO",
        "event_start_us": event_start_us,
        "event_end_us": event_end_us,
    }
    event_key = event_key_for(**identity)
    recorded_at = format_utc_milliseconds(
        gps_week_time_to_utc(2000, 18_000, 18)
        + timedelta(microseconds=event_start_us - 1_000_000)
    )
    return BatteryPackObservation(
        event_key=event_key,
        observation_id=observation_id_for(event_key, semantics),
        observation_schema_version=OBSERVATION_SCHEMA_VERSION,
        analysis_semantics_version=semantics,
        pack_id_at_ingest=pack_id,
        source_sha256=source_sha256,
        source_filename=source_filename,
        firmware="ArduPlane V4.7.0",
        recorded_at_utc=recorded_at,
        gps_anchor_week=2000,
        gps_anchor_week_ms=18_000,
        gps_anchor_time_us=1_000_000,
        gps_instance=0,
        gps_utc_offset_seconds=18,
        flight_number=1,
        flight_start_us=flight_start_us,
        flight_end_us=flight_end_us,
        battery_instance=battery_instance,
        event_type="TAKEOFF",
        takeoff_type="AUTO",
        event_start_us=event_start_us,
        event_end_us=event_end_us,
        event_duration_s=(event_end_us - event_start_us) / 1_000_000,
        capacity_used_mah=100.0,
        pre_load_voltage_v=16.0,
        minimum_loaded_voltage_v=14.5,
        peak_current_a=20.0,
        average_current_a=18.0,
        current_at_minimum_voltage_a=19.0,
        maximum_throttle_pct=100.0,
        average_throttle_pct=95.0,
        recovery_time_us=4_000_000,
        voltage_after_recovery_v=15.0,
        voltage_sag_v=1.5,
        voltage_recovery_v=0.5,
        low_voltage_margin_v=1.3,
        critical_voltage_margin_v=1.7,
        configuration_lookup_time_us=1_000_000,
        configured_capacity_mah=5000.0,
        configured_low_voltage_v=13.2,
        configured_critical_voltage_v=12.8,
        configured_failsafe_voltage_source=0.0,
        configuration_warnings=("historical context",),
    )


def test_observation_strict_round_trip_preserves_nullable_fields(tmp_path):
    path = tmp_path / "history.json"
    observation = dataclasses.replace(
        _observation(),
        firmware=None,
        capacity_used_mah=None,
        voltage_recovery_v=None,
    )

    store = BatteryPackHistoryStore(path)
    assert store.add_observations([observation]) == 1

    assert BatteryPackHistoryStore(path).observations == (observation,)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == 1
    persisted = data["observations"][observation.observation_id]
    assert persisted["firmware"] is None
    assert persisted["capacity_used_mah"] is None
    assert persisted["voltage_recovery_v"] is None


def test_unavailable_gps_time_requires_all_provenance_to_be_null():
    unavailable = dataclasses.replace(
        _observation(),
        recorded_at_utc=None,
        gps_anchor_week=None,
        gps_anchor_week_ms=None,
        gps_anchor_time_us=None,
        gps_instance=None,
        gps_utc_offset_seconds=None,
    )
    unavailable.validate()

    with pytest.raises(BatteryPackHistoryFormatError, match="partial GPS"):
        dataclasses.replace(unavailable, gps_anchor_week=2000).validate()


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"version": 1},
        {"version": 2, "observations": {}},
        {"version": True, "observations": {}},
        {"version": 1, "observations": []},
    ],
)
def test_malformed_top_level_schema_is_rejected(tmp_path, payload):
    path = tmp_path / "history.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(BatteryPackHistoryFormatError):
        BatteryPackHistoryStore(path)


def test_unsupported_observation_schema_version_is_rejected():
    with pytest.raises(BatteryPackHistoryFormatError, match="schema version"):
        dataclasses.replace(
            _observation(), observation_schema_version=2
        ).validate()


@pytest.mark.parametrize("change", ["missing", "extra"])
def test_wrong_observation_fields_are_rejected(tmp_path, change):
    observation = _observation()
    data = observation.to_dict()
    if change == "missing":
        data.pop("peak_current_a")
    else:
        data["unexpected"] = 1
    path = tmp_path / "history.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "observations": {observation.observation_id: data},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(BatteryPackHistoryFormatError):
        BatteryPackHistoryStore(path)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_measurements_are_rejected(value):
    with pytest.raises(BatteryPackHistoryFormatError):
        dataclasses.replace(_observation(), peak_current_a=value).validate()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("flight_number", True),
        ("battery_instance", False),
        ("event_duration_s", True),
        ("peak_current_a", False),
        ("gps_anchor_week", True),
    ],
)
def test_bool_is_not_accepted_as_numeric_evidence(field, value):
    with pytest.raises(BatteryPackHistoryFormatError):
        dataclasses.replace(_observation(), **{field: value}).validate()


@pytest.mark.parametrize("value", [123, "not-a-time", "2018-05-06T00:00:01"])
def test_malformed_recorded_at_utc_is_a_format_error(value):
    with pytest.raises(BatteryPackHistoryFormatError):
        dataclasses.replace(_observation(), recorded_at_utc=value).validate()


@pytest.mark.parametrize(
    "warnings",
    [["not a tuple"], ("valid", 3), "not a tuple"],
)
def test_configuration_warnings_require_tuple_of_strings(warnings):
    with pytest.raises(BatteryPackHistoryFormatError):
        dataclasses.replace(
            _observation(), configuration_warnings=warnings
        ).validate()


@pytest.mark.parametrize("filename", ["archive/log.bin", r"archive\log.bin"])
def test_source_filename_must_be_a_basename(filename):
    with pytest.raises(BatteryPackHistoryFormatError):
        dataclasses.replace(_observation(), source_filename=filename).validate()


def test_gps_anchor_must_be_causal_to_event_start():
    with pytest.raises(BatteryPackHistoryFormatError, match="causal"):
        dataclasses.replace(
            _observation(), gps_anchor_time_us=2_000_001
        ).validate()


def test_recorded_utc_must_match_persisted_gps_provenance():
    with pytest.raises(BatteryPackHistoryFormatError, match="GPS provenance"):
        dataclasses.replace(
            _observation(), recorded_at_utc="2018-05-06T00:00:02.000Z"
        ).validate()


def test_event_duration_must_match_event_bounds():
    with pytest.raises(BatteryPackHistoryFormatError, match="event bounds"):
        dataclasses.replace(_observation(), event_duration_s=1.1).validate()


@pytest.mark.parametrize("recovery_time_us", [2_999_999, 5_000_001])
def test_recovery_time_must_follow_event_inside_flight(recovery_time_us):
    with pytest.raises(BatteryPackHistoryFormatError, match="recovery_time_us"):
        dataclasses.replace(
            _observation(), recovery_time_us=recovery_time_us
        ).validate()


def test_supported_historical_offset_loads_and_unsupported_offset_fails(tmp_path):
    path = tmp_path / "history.json"
    observation = _observation()
    BatteryPackHistoryStore(path).add_observations([observation])

    assert BatteryPackHistoryStore(path).observations == (observation,)
    with pytest.raises(BatteryPackHistoryFormatError, match="offset"):
        dataclasses.replace(
            observation, gps_utc_offset_seconds=19
        ).validate()


def test_historical_offset_validation_is_independent_of_current_offset(monkeypatch):
    observation = _observation()
    monkeypatch.setattr(gps_time, "GPS_UTC_OFFSET_SECONDS", 19)

    observation.validate()


def test_malformed_existing_history_is_not_overwritten(tmp_path):
    path = tmp_path / "history.json"
    malformed = b'{"version": 1, "observations": '
    path.write_bytes(malformed)

    with pytest.raises(BatteryPackHistoryFormatError):
        BatteryPackHistoryStore(path)

    assert path.read_bytes() == malformed


def test_event_and_observation_identity_are_separate_and_versioned():
    event_key = event_key_for(source_sha256="1" * 64, event_start_us=1)

    assert event_key == event_key_for(
        source_sha256="1" * 64, event_start_us=1
    )
    assert observation_id_for(event_key, "battery-load-v1") != event_key
    assert observation_id_for(
        event_key, "battery-load-v1"
    ) != observation_id_for(event_key, "battery-load-v2")


def test_identity_distinguishes_content_events_windows_and_instances():
    baseline = _observation()
    variants = (
        _observation(source_sha256="2" * 64),
        _observation(event_start_us=2_100_000, event_end_us=3_100_000),
        _observation(flight_start_us=500_000),
        _observation(battery_instance=1),
    )

    assert len({baseline.event_key, *(item.event_key for item in variants)}) == 5


def test_reinsertion_and_mutable_provenance_are_idempotent(tmp_path):
    store = BatteryPackHistoryStore(tmp_path / "history.json")
    observation = _observation()

    assert store.add_observations([observation]) == 1
    assert store.add_observations([observation]) == 0
    assert store.add_observations(
        [dataclasses.replace(observation, source_filename="renamed.bin")]
    ) == 0
    assert store.add_observations(
        [dataclasses.replace(observation, pack_id_at_ingest="Pack B")]
    ) == 0
    assert store.observations == (observation,)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("minimum_loaded_voltage_v", 13.0),
        ("peak_current_a", 99.0),
    ],
)
def test_changed_analytical_evidence_conflicts(field, value, tmp_path):
    store = BatteryPackHistoryStore(tmp_path / "history.json")
    observation = _observation()
    store.add_observations([observation])

    with pytest.raises(BatteryPackHistoryError, match="Conflicting evidence"):
        store.add_observations(
            [dataclasses.replace(observation, **{field: value})]
        )


def test_supported_semantics_coexist_and_explicit_order_selects_newest(
    monkeypatch, tmp_path
):
    versions = ("battery-load-v1", "battery-load-next")
    monkeypatch.setattr(
        battery_pack_history, "SUPPORTED_ANALYSIS_SEMANTICS", versions
    )
    old = _observation(semantics=versions[0])
    new = _observation(semantics=versions[1])
    store = BatteryPackHistoryStore(tmp_path / "history.json")

    assert store.add_observations([old, new]) == 2
    assert old.event_key == new.event_key
    assert old.observation_id != new.observation_id
    assert store.newest_supported_observations() == (new,)


def test_first_save_creates_strict_versioned_json(tmp_path):
    path = tmp_path / "history.json"
    observation = _observation()

    BatteryPackHistoryStore(path).add_observations([observation])
    data = json.loads(path.read_text(encoding="utf-8"))

    assert set(data) == {"version", "observations"}
    assert data["version"] == 1
    assert set(data["observations"]) == {observation.observation_id}


def test_failed_replace_leaves_disk_and_memory_unchanged(monkeypatch, tmp_path):
    path = tmp_path / "history.json"
    store = BatteryPackHistoryStore(path)
    first = _observation()
    second = _observation(source_sha256="2" * 64)
    store.add_observations([first])
    original = path.read_bytes()
    monkeypatch.setattr(
        battery_pack_history.os,
        "replace",
        lambda *_args: (_ for _ in ()).throw(OSError("replace failed")),
    )

    with pytest.raises(OSError, match="replace failed"):
        store.add_observations([second])

    assert path.read_bytes() == original
    assert store.observations == (first,)


def test_temporary_file_failure_does_not_corrupt_existing_store(
    monkeypatch, tmp_path
):
    path = tmp_path / "history.json"
    store = BatteryPackHistoryStore(path)
    first = _observation()
    store.add_observations([first])
    original = path.read_bytes()
    monkeypatch.setattr(
        battery_pack_history.tempfile,
        "mkstemp",
        lambda **_kwargs: (_ for _ in ()).throw(OSError("temp failed")),
    )

    with pytest.raises(OSError, match="temp failed"):
        store.add_observations([_observation(source_sha256="2" * 64)])

    assert path.read_bytes() == original
    assert store.observations == (first,)


def test_invalid_or_conflicting_batch_writes_none(tmp_path):
    path = tmp_path / "history.json"
    store = BatteryPackHistoryStore(path)
    first = _observation()
    store.add_observations([first])
    original = path.read_bytes()
    valid_new = _observation(source_sha256="2" * 64)
    conflict = dataclasses.replace(first, average_current_a=99.0)

    with pytest.raises(BatteryPackHistoryError):
        store.add_observations([valid_new, conflict])

    assert path.read_bytes() == original
    assert store.observations == (first,)

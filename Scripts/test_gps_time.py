"""Focused tests for causal absolute GPS time evidence."""

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from core.flight_data import FlightLog
from core.gps_time import GPS_UTC_OFFSET_SECONDS, gps_time_at


def _flight(*rows):
    return FlightLog(messages={"GPS": pd.DataFrame(rows)})


def _row(time_us, *, week=2000, week_ms=18_000, instance=0, used=1, status=3):
    return {
        "TimeUS": time_us,
        "GWk": week,
        "GMS": week_ms,
        "I": instance,
        "U": used,
        "Status": status,
    }


def test_known_gps_week_time_converts_with_current_offset():
    evidence = gps_time_at(_flight(_row(1_000_000)), 1_000_000)

    assert GPS_UTC_OFFSET_SECONDS == 18
    assert evidence is not None
    assert evidence.recorded_at_utc == datetime(
        2018, 5, 6, tzinfo=timezone.utc
    )
    assert evidence.gps_utc_offset_seconds == 18


def test_recorded_time_is_event_start_not_anchor_time():
    evidence = gps_time_at(_flight(_row(1_000_000)), 3_500_000)

    assert evidence is not None
    assert evidence.recorded_at_utc == datetime(
        2018, 5, 6, tzinfo=timezone.utc
    ) + timedelta(seconds=2.5)
    assert evidence.gps_anchor_time_us == 1_000_000


def test_latest_valid_causal_row_is_used_and_future_row_is_ignored():
    flight = _flight(
        _row(1_000_000, week_ms=18_000),
        _row(2_000_000, week_ms=19_000),
        _row(4_000_000, week_ms=21_000),
    )

    evidence = gps_time_at(flight, 2_500_000)

    assert evidence is not None
    assert evidence.gps_anchor_time_us == 2_000_000
    assert evidence.gps_anchor_week_ms == 19_000
    assert evidence.recorded_at_utc.microsecond == 500_000


def test_future_only_gps_evidence_cannot_backdate_event():
    assert gps_time_at(_flight(_row(2_000_000)), 1_000_000) is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("TimeUS", float("nan")),
        ("TimeUS", 1.5),
        ("GWk", 0),
        ("GWk", float("inf")),
        ("GMS", -1),
        ("GMS", 604_800_000),
        ("GMS", 1.25),
        ("I", float("nan")),
        ("Status", 2),
    ],
)
def test_invalid_gps_evidence_is_unavailable(field, value):
    row = _row(1_000_000)
    row[field] = value

    assert gps_time_at(_flight(row), 1_000_000) is None


def test_inactive_receiver_cannot_supply_time_when_u_exists():
    assert gps_time_at(_flight(_row(1_000_000, used=0)), 1_000_000) is None


def test_one_coherent_active_receiver_ignores_inactive_rows():
    evidence = gps_time_at(
        _flight(
            _row(1_000_000, week_ms=18_000),
            _row(
                1_500_000,
                week=100,
                week_ms=1,
                instance=1,
                used=0,
            ),
            _row(2_000_000, week_ms=19_000),
        ),
        2_000_000,
    )

    assert evidence is not None
    assert evidence.gps_instance == 0
    assert evidence.gps_anchor_week == 2000


def test_one_defensible_receiver_works_when_u_is_absent():
    row = _row(1_000_000)
    row.pop("U")

    assert gps_time_at(_flight(row), 1_000_000) is not None


def test_conflicting_equal_timestamp_evidence_is_unavailable():
    flight = _flight(
        _row(1_000_000, week_ms=18_000),
        _row(1_000_000, week_ms=19_000),
        _row(2_000_000, week_ms=20_000),
    )

    assert gps_time_at(flight, 2_000_000) is None


def test_backward_absolute_gps_timeline_is_unavailable():
    flight = _flight(
        _row(1_000_000, week_ms=20_000),
        _row(2_000_000, week_ms=19_000),
    )

    assert gps_time_at(flight, 2_000_000) is None


def test_coherent_week_increment_and_gms_reset_is_accepted():
    flight = _flight(
        _row(1_000_000, week_ms=604_799_000),
        _row(3_000_000, week=2001, week_ms=1_000),
    )

    evidence = gps_time_at(flight, 3_000_000)

    assert evidence is not None
    assert evidence.gps_anchor_week == 2001
    assert evidence.gps_anchor_week_ms == 1_000


def test_gms_rollback_without_week_increment_is_unavailable():
    flight = _flight(
        _row(1_000_000, week_ms=20_000),
        _row(2_000_000, week_ms=1_000),
    )

    assert gps_time_at(flight, 2_000_000) is None


def test_ambiguous_multiple_receivers_are_unavailable_with_or_without_u():
    with_u = _flight(
        _row(1_000_000, instance=0),
        _row(2_000_000, week_ms=19_000, instance=1),
    )
    without_u_rows = []
    for row in with_u.get("GPS").to_dict("records"):
        row.pop("U")
        without_u_rows.append(row)

    assert gps_time_at(with_u, 2_000_000) is None
    assert gps_time_at(_flight(*without_u_rows), 2_000_000) is None


def test_directly_agreed_receiver_handover_is_accepted():
    flight = _flight(
        _row(1_000_000, instance=0),
        _row(1_000_000, instance=1),
        _row(2_000_000, week_ms=19_000, instance=1),
    )

    evidence = gps_time_at(flight, 2_000_000)

    assert evidence is not None
    assert evidence.gps_instance == 1


def test_missing_gps_has_no_external_time_fallback():
    flight = FlightLog(metadata={"filename": "2020-01-01.bin"})

    assert gps_time_at(flight, 1_000_000) is None


@pytest.mark.parametrize("target", [True, -1, 1.5, float("nan")])
def test_invalid_query_time_is_unavailable(target):
    assert gps_time_at(_flight(_row(1_000_000)), target) is None

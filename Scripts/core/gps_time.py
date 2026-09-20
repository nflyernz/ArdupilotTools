"""Absolute UTC evidence reconstructed from logged GPS week time."""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from numbers import Real

from .flight_data import FlightLog

GPS_EPOCH = datetime(1980, 1, 6, tzinfo=timezone.utc)
GPS_WEEK_MILLISECONDS = 604_800_000
GPS_UTC_OFFSET_SECONDS = 18
SUPPORTED_GPS_UTC_OFFSETS = frozenset({18})


@dataclass(frozen=True)
class GpsTimeEvidence:
    """UTC event time and the causal logged GPS row used to derive it."""

    recorded_at_utc: datetime
    gps_anchor_week: int
    gps_anchor_week_ms: int
    gps_anchor_time_us: int
    gps_instance: int
    gps_utc_offset_seconds: int = GPS_UTC_OFFSET_SECONDS

    def utc_isoformat(self) -> str:
        """Return a stable millisecond-resolution UTC representation."""
        return format_utc_milliseconds(self.recorded_at_utc)


def gps_week_time_to_utc(
    week: int,
    week_ms: int,
    utc_offset_seconds: int,
) -> datetime:
    """Convert validated full GPS week evidence to UTC."""
    return (
        GPS_EPOCH
        + timedelta(weeks=week, milliseconds=week_ms)
        - timedelta(seconds=utc_offset_seconds)
    )


def format_utc_milliseconds(timestamp: datetime) -> str:
    """Return the canonical persisted UTC representation."""
    return timestamp.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def gps_time_at(
    flight_log: FlightLog,
    target_time_us: int,
) -> GpsTimeEvidence | None:
    """Resolve event UTC from the latest defensible causal GPS sample."""
    if not _is_integral_number(target_time_us) or target_time_us < 0:
        return None

    gps = flight_log.get("GPS")
    required = {"TimeUS", "GWk", "GMS", "I", "Status"}
    if gps.empty or not required.issubset(gps.columns):
        return None

    rows: list[tuple[int, int, int, int]] = []
    has_used_field = "U" in gps.columns
    for _, row in gps.iterrows():
        time_us = _integer(row["TimeUS"])
        week = _integer(row["GWk"])
        week_ms = _integer(row["GMS"])
        instance = _integer(row["I"])
        status = _integer(row["Status"])
        used = _integer(row["U"]) if has_used_field else 1

        if (
            time_us is None
            or week is None
            or week_ms is None
            or instance is None
            or status is None
            or used is None
            or time_us < 0
            or week <= 0
            or not 0 <= week_ms < GPS_WEEK_MILLISECONDS
            or instance < 0
            or status < 3
            or used != 1
        ):
            continue
        rows.append((time_us, week, week_ms, instance))

    causal = [row for row in rows if row[0] <= target_time_us]
    if not causal:
        return None

    if not _receiver_evidence_is_unambiguous(causal):
        return None

    latest_time_us = max(row[0] for row in causal)
    latest = [row for row in causal if row[0] == latest_time_us]
    anchor = latest[-1]
    anchor_utc = gps_week_time_to_utc(
        anchor[1],
        anchor[2],
        GPS_UTC_OFFSET_SECONDS,
    )
    event_utc = anchor_utc + timedelta(
        microseconds=target_time_us - anchor[0]
    )
    return GpsTimeEvidence(
        recorded_at_utc=event_utc,
        gps_anchor_week=anchor[1],
        gps_anchor_week_ms=anchor[2],
        gps_anchor_time_us=anchor[0],
        gps_instance=anchor[3],
    )


def _receiver_evidence_is_unambiguous(
    rows: list[tuple[int, int, int, int]],
) -> bool:
    """Require coherent causal clocks and direct multi-receiver agreement."""
    instances = {row[3] for row in rows}
    for instance in instances:
        instance_rows = [row for row in rows if row[3] == instance]
        if not _chronology_is_coherent(instance_rows):
            return False

    rows_by_time: dict[int, list[tuple[int, int, int, int]]] = {}
    for row in rows:
        rows_by_time.setdefault(row[0], []).append(row)
    for same_time_rows in rows_by_time.values():
        if len({_absolute_gps_ms(row) for row in same_time_rows}) != 1:
            return False

    if len(instances) > 1:
        agreement_graph = {instance: set() for instance in instances}
        for same_time_rows in rows_by_time.values():
            same_time_instances = {row[3] for row in same_time_rows}
            if len(same_time_instances) > 1:
                for instance in same_time_instances:
                    agreement_graph[instance].update(
                        same_time_instances - {instance}
                    )
        connected = {next(iter(instances))}
        pending = list(connected)
        while pending:
            instance = pending.pop()
            newly_connected = agreement_graph[instance] - connected
            connected.update(newly_connected)
            pending.extend(newly_connected)
        if connected != instances:
            return False

    return _chronology_is_coherent(sorted(rows, key=lambda row: row[0]))


def _chronology_is_coherent(rows: list[tuple[int, int, int, int]]) -> bool:
    """Reject backward local/GPS time and contradictory week transitions."""
    previous: tuple[int, int, int, int] | None = None
    for row in rows:
        if previous is None:
            previous = row
            continue
        if row[0] < previous[0]:
            return False
        if row[0] == previous[0] and _absolute_gps_ms(row) != _absolute_gps_ms(
            previous
        ):
            return False
        if row[1] == previous[1]:
            if row[2] < previous[2]:
                return False
        elif row[1] == previous[1] + 1:
            if row[2] >= previous[2]:
                return False
        else:
            return False
        previous = row
    return True


def _absolute_gps_ms(row: tuple[int, int, int, int]) -> int:
    return (row[1] * GPS_WEEK_MILLISECONDS) + row[2]


def _integer(value: object) -> int | None:
    if not isinstance(value, Real) or isinstance(value, bool):
        return None
    number = float(value)
    if not math.isfinite(number) or not number.is_integer():
        return None
    return int(number)


def _is_integral_number(value: object) -> bool:
    return _integer(value) is not None

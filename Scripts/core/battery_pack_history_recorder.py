"""Whole-BIN ingestion for durable Battery Pack Performance evidence."""

import math
from numbers import Real
from pathlib import Path

from .battery import BatteryLoadEventType, BatteryProcessor, TakeoffType
from .battery_pack_history import (
    ANALYSIS_SEMANTICS_VERSION,
    OBSERVATION_SCHEMA_VERSION,
    BatteryPackHistoryError,
    BatteryPackHistoryFormatError,
    BatteryPackHistoryStore,
    BatteryPackObservation,
    event_key_for,
    observation_id_for,
)
from .gps_time import gps_time_at


class BatteryPackHistoryRecorder:
    """Harvest all supported AUTO takeoffs from one tracked BIN session."""

    def __init__(self, config):
        self.config = config

    def record(
        self,
        flight_log,
        log_path: str | Path,
        source_sha256: str,
        pack_id: str,
        store: BatteryPackHistoryStore,
    ) -> int:
        """Analyze every FlightWindow/instance and atomically retain evidence."""
        if not flight_log.flights:
            return 0
        if not _is_sha256(source_sha256):
            raise BatteryPackHistoryError("Invalid source SHA-256.")
        if not isinstance(pack_id, str) or not pack_id.strip():
            raise BatteryPackHistoryError("Pack ID must be non-empty.")

        instance_probe = BatteryProcessor(
            flight_log,
            flight_log.flights[0],
            0,
            config=self.config,
        )
        instances = instance_probe.available_instances()
        firmware = flight_log.firmware_version()
        firmware_text = firmware["version"] if firmware is not None else None
        observations = []

        for flight_window in flight_log.flights:
            for instance in instances:
                analysis = BatteryProcessor(
                    flight_log,
                    flight_window,
                    instance,
                    config=self.config,
                ).analyse()
                if analysis is None:
                    continue
                for event in analysis.bounded_load_events:
                    if (
                        event.event_type is not BatteryLoadEventType.TAKEOFF
                        or event.takeoff_type is not TakeoffType.AUTO
                    ):
                        continue
                    observations.append(
                        _observation_from_event(
                            flight_log=flight_log,
                            log_path=Path(log_path),
                            source_sha256=source_sha256,
                            pack_id=pack_id.strip(),
                            firmware=firmware_text,
                            flight_window=flight_window,
                            analysis=analysis,
                            event=event,
                        )
                    )
        return store.add_observations(observations)


def _observation_from_event(
    *,
    flight_log,
    log_path: Path,
    source_sha256: str,
    pack_id: str,
    firmware: str | None,
    flight_window,
    analysis,
    event,
) -> BatteryPackObservation:
    time_evidence = gps_time_at(flight_log, event.start_us)
    configuration = analysis.session_configuration
    event_key = event_key_for(
        source_sha256=source_sha256,
        battery_instance=event.instance,
        flight_start_us=flight_window.start_us,
        flight_end_us=flight_window.end_us,
        event_type=event.event_type.value,
        takeoff_type=event.takeoff_type.value,
        event_start_us=event.start_us,
        event_end_us=event.end_us,
    )
    observation = BatteryPackObservation(
        event_key=event_key,
        observation_id=observation_id_for(
            event_key,
            ANALYSIS_SEMANTICS_VERSION,
        ),
        observation_schema_version=OBSERVATION_SCHEMA_VERSION,
        analysis_semantics_version=ANALYSIS_SEMANTICS_VERSION,
        pack_id_at_ingest=pack_id,
        source_sha256=source_sha256,
        source_filename=log_path.name,
        firmware=firmware,
        recorded_at_utc=(
            time_evidence.utc_isoformat() if time_evidence is not None else None
        ),
        gps_anchor_week=(
            time_evidence.gps_anchor_week if time_evidence is not None else None
        ),
        gps_anchor_week_ms=(
            time_evidence.gps_anchor_week_ms if time_evidence is not None else None
        ),
        gps_anchor_time_us=(
            time_evidence.gps_anchor_time_us if time_evidence is not None else None
        ),
        gps_instance=(
            time_evidence.gps_instance if time_evidence is not None else None
        ),
        gps_utc_offset_seconds=(
            time_evidence.gps_utc_offset_seconds
            if time_evidence is not None
            else None
        ),
        flight_number=event.flight_number,
        flight_start_us=flight_window.start_us,
        flight_end_us=flight_window.end_us,
        battery_instance=event.instance,
        event_type=event.event_type.value,
        takeoff_type=event.takeoff_type.value,
        event_start_us=event.start_us,
        event_end_us=event.end_us,
        event_duration_s=_finite(event.duration_s, "event duration"),
        capacity_used_mah=_optional_finite(
            event.consumed_mah_at_start,
            "capacity used",
        ),
        pre_load_voltage_v=_optional_finite(
            event.pre_load_voltage,
            "pre-load voltage",
        ),
        minimum_loaded_voltage_v=_optional_finite(
            event.minimum_voltage,
            "minimum loaded voltage",
        ),
        peak_current_a=_optional_finite(event.peak_current, "peak current"),
        average_current_a=_optional_finite(
            event.average_current,
            "average current",
        ),
        current_at_minimum_voltage_a=_optional_finite(
            event.current_at_minimum_voltage,
            "current at minimum voltage",
        ),
        maximum_throttle_pct=_optional_finite(
            event.maximum_throttle,
            "maximum throttle",
        ),
        average_throttle_pct=_optional_finite(
            event.average_throttle,
            "average throttle",
        ),
        recovery_time_us=event.recovery_time_us,
        voltage_after_recovery_v=_optional_finite(
            event.voltage_after_recovery,
            "voltage after recovery",
        ),
        voltage_sag_v=_optional_finite(event.voltage_sag, "voltage sag"),
        voltage_recovery_v=_optional_finite(
            event.voltage_recovery,
            "voltage recovery",
        ),
        low_voltage_margin_v=_optional_finite(
            event.low_voltage_margin,
            "LOW voltage margin",
        ),
        critical_voltage_margin_v=_optional_finite(
            event.critical_voltage_margin,
            "CRITICAL voltage margin",
        ),
        configuration_lookup_time_us=(
            configuration.lookup_time_us if configuration is not None else None
        ),
        configured_capacity_mah=_optional_finite(
            configuration.capacity_mah if configuration is not None else None,
            "configured capacity",
        ),
        configured_low_voltage_v=_optional_finite(
            configuration.low_voltage if configuration is not None else None,
            "configured LOW voltage",
        ),
        configured_critical_voltage_v=_optional_finite(
            configuration.critical_voltage if configuration is not None else None,
            "configured CRITICAL voltage",
        ),
        configured_failsafe_voltage_source=_optional_finite(
            configuration.failsafe_voltage_source
            if configuration is not None
            else None,
            "configured failsafe voltage source",
        ),
        configuration_warnings=(
            configuration.warnings if configuration is not None else ()
        ),
    )
    observation.validate()
    return observation


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _finite(value: object, label: str) -> float:
    if (
        not isinstance(value, Real)
        or isinstance(value, bool)
        or not math.isfinite(float(value))
    ):
        raise BatteryPackHistoryFormatError(f"{label} must be finite.")
    return float(value)


def _optional_finite(value: object, label: str) -> float | None:
    if value is None:
        return None
    return _finite(value, label)

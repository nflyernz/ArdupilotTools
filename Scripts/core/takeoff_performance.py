"""Evidence-first performance metrics for Plane TAKEOFF-mode executions."""

import math
from dataclasses import dataclass
from enum import Enum
from numbers import Integral, Real

import pandas as pd

from .flight_data import FlightLog
from .takeoff_execution import (
    TakeoffEntryContext,
    TakeoffExecution,
    TakeoffExecutionEvent,
    TakeoffTerminationReason,
)


class TakeoffControlIntervalStatus(Enum):
    """How the automatic takeoff-control observation interval ended."""

    COMPLETED = "completed"
    CENSORED_MODE_EXIT = "censored_mode_exit"


@dataclass(frozen=True, slots=True)
class TakeoffControlInterval:
    """Owned interval used for automatic-control aggregate evidence."""

    start_us: int
    end_us: int
    status: TakeoffControlIntervalStatus

    @property
    def duration_s(self) -> float:
        """Return the observed interval duration in seconds."""
        return (self.end_us - self.start_us) / 1_000_000


@dataclass(frozen=True, slots=True)
class EventTelemetryValue:
    """One causal telemetry value associated with an event."""

    value: float
    source_time_us: int
    age_us: int


@dataclass(frozen=True, slots=True)
class EventAirspeedValue:
    """One causal controller airspeed estimate associated with an event."""

    value_m_s: float
    estimate_type: int
    source_time_us: int
    age_us: int


@dataclass(frozen=True, slots=True)
class TakeoffTriggerContext:
    """Available CTUN and GPS state at firmware launch acceptance."""

    nav_pitch_deg: EventTelemetryValue | None
    pitch_deg: EventTelemetryValue | None
    nav_roll_deg: EventTelemetryValue | None
    roll_deg: EventTelemetryValue | None
    airspeed: EventAirspeedValue | None
    throttle_output_pct: EventTelemetryValue | None
    gps_groundspeed_m_s: EventTelemetryValue | None


@dataclass(frozen=True, slots=True)
class TakeoffPhaseTimings:
    """Elapsed firmware/log observations from the launch trigger."""

    trigger_time_us: int
    trigger_to_throttle_unsuppressed_s: float | None
    trigger_to_target_finalized_s: float | None
    trigger_to_control_completed_s: float | None
    trigger_to_mode_exit_s: float | None


@dataclass(frozen=True, slots=True)
class RollExtremum:
    """Maximum absolute achieved roll in a launch-response interval."""

    magnitude_deg: float
    signed_roll_deg: float
    source_time_us: int


@dataclass(frozen=True, slots=True)
class ThrottleCommandContext:
    """Threshold-free normalized throttle-function command evidence."""

    at_unsuppressed: EventTelemetryValue | None
    at_target_finalized: EventTelemetryValue | None
    launch_response_max_pct: float | None
    launch_response_max_time_us: int | None


@dataclass(frozen=True, slots=True)
class AirspeedExtremum:
    """One controller airspeed extremum and its estimate source."""

    value_m_s: float
    estimate_type: int
    source_time_us: int


@dataclass(frozen=True, slots=True)
class AirspeedEnvelope:
    """Minimum and maximum valid controller airspeed in one interval."""

    minimum: AirspeedExtremum
    maximum: AirspeedExtremum


@dataclass(frozen=True, slots=True)
class RelativeAltitudeMetrics:
    """POS relative-home altitude observations sharing one trigger baseline."""

    trigger_altitude_m: EventTelemetryValue
    minimum_altitude_m: float | None
    minimum_time_us: int | None
    minimum_delta_m: float | None
    endpoint_altitude_m: EventTelemetryValue | None
    endpoint_delta_m: float | None


@dataclass(frozen=True, slots=True)
class TakeoffPerformanceAnalysis:
    """Measured evidence for one triggered Plane TAKEOFF-mode execution."""

    execution: TakeoffExecution
    phase_timings: TakeoffPhaseTimings
    trigger_context: TakeoffTriggerContext
    control_interval: TakeoffControlInterval | None
    launch_response_roll: RollExtremum | None
    throttle_command: ThrottleCommandContext
    airspeed_envelope: AirspeedEnvelope | None
    relative_altitude: RelativeAltitudeMetrics | None


@dataclass(frozen=True, slots=True)
class _TelemetryRow:
    """A telemetry row with validated time and retained source order."""

    time_us: int
    source_order: int
    row: pd.Series


class TakeoffPerformanceProcessor:
    """Build bounded performance evidence for one TAKEOFF-mode execution."""

    def __init__(
        self,
        flight_log: FlightLog,
        execution: TakeoffExecution,
    ):
        self.flight_log = flight_log
        self.execution = execution

    def analyse(self) -> TakeoffPerformanceAnalysis | None:
        """Return metrics for one owned trigger, or None when unsupported."""
        if self.execution.entry_context is not TakeoffEntryContext.TAKEOFF_MODE:
            return None

        trigger = self.execution.launch_trigger
        if trigger is None or not self._event_is_owned(trigger):
            return None

        target = self.execution.target_course_finalization
        unsuppressed = self.execution.throttle_unsuppressed
        completion = self.execution.takeoff_control_completion
        launch_response = self._launch_response_interval(trigger, target)
        control_interval = self._control_interval(trigger, completion)

        trigger_context = self._trigger_context(trigger)
        maximum_throttle_pct, maximum_throttle_time_us = self._maximum_throttle(
            launch_response
        )

        phase_timings = TakeoffPhaseTimings(
            trigger_time_us=trigger.time_us,
            trigger_to_throttle_unsuppressed_s=self._elapsed_s(
                trigger,
                unsuppressed,
            ),
            trigger_to_target_finalized_s=self._elapsed_s(trigger, target),
            trigger_to_control_completed_s=self._elapsed_s(
                trigger,
                completion,
            ),
            trigger_to_mode_exit_s=(
                (self.execution.end_us - trigger.time_us) / 1_000_000
                if self.execution.termination_reason
                is TakeoffTerminationReason.MODE_EXIT
                and self.execution.end_us >= trigger.time_us
                else None
            ),
        )

        return TakeoffPerformanceAnalysis(
            execution=self.execution,
            phase_timings=phase_timings,
            trigger_context=trigger_context,
            control_interval=control_interval,
            launch_response_roll=self._roll_extremum(launch_response),
            throttle_command=ThrottleCommandContext(
                at_unsuppressed=self._event_value(
                    "CTUN",
                    "ThO",
                    unsuppressed,
                ),
                at_target_finalized=self._event_value(
                    "CTUN",
                    "ThO",
                    target,
                ),
                launch_response_max_pct=maximum_throttle_pct,
                launch_response_max_time_us=maximum_throttle_time_us,
            ),
            airspeed_envelope=self._airspeed_envelope(control_interval),
            relative_altitude=self._relative_altitude(
                trigger,
                control_interval,
            ),
        )

    def _event_is_owned(self, event: TakeoffExecutionEvent) -> bool:
        return self.execution.start_us <= event.time_us <= self.execution.end_us

    @staticmethod
    def _elapsed_s(
        start: TakeoffExecutionEvent,
        end: TakeoffExecutionEvent | None,
    ) -> float | None:
        if end is None or end.time_us < start.time_us:
            return None
        return (end.time_us - start.time_us) / 1_000_000

    def _launch_response_interval(
        self,
        trigger: TakeoffExecutionEvent,
        target: TakeoffExecutionEvent | None,
    ) -> tuple[int, int] | None:
        if (
            target is None
            or not self._event_is_owned(target)
            or target.time_us <= trigger.time_us
        ):
            return None
        return trigger.time_us, target.time_us

    def _control_interval(
        self,
        trigger: TakeoffExecutionEvent,
        completion: TakeoffExecutionEvent | None,
    ) -> TakeoffControlInterval | None:
        if (
            completion is not None
            and self._event_is_owned(completion)
            and completion.time_us > trigger.time_us
        ):
            return TakeoffControlInterval(
                trigger.time_us,
                completion.time_us,
                TakeoffControlIntervalStatus.COMPLETED,
            )

        if (
            self.execution.termination_reason is TakeoffTerminationReason.MODE_EXIT
            and self.execution.end_us > trigger.time_us
        ):
            return TakeoffControlInterval(
                trigger.time_us,
                self.execution.end_us,
                TakeoffControlIntervalStatus.CENSORED_MODE_EXIT,
            )
        return None

    def _event_value(
        self,
        message: str,
        column: str,
        event: TakeoffExecutionEvent | None,
    ) -> EventTelemetryValue | None:
        if event is None or not self._event_is_owned(event):
            return None
        candidates = []
        for telemetry in self._rows(message):
            if not (self.execution.start_us <= telemetry.time_us <= event.time_us):
                continue
            value = self._finite_float(telemetry.row.get(column))
            if value is not None:
                candidates.append((telemetry, value))
        if not candidates:
            return None
        telemetry, value = max(
            candidates,
            key=lambda item: (item[0].time_us, item[0].source_order),
        )
        return EventTelemetryValue(
            value,
            telemetry.time_us,
            event.time_us - telemetry.time_us,
        )

    def _trigger_context(
        self,
        trigger: TakeoffExecutionEvent,
    ) -> TakeoffTriggerContext:
        telemetry = self._event_row("CTUN", trigger)
        return TakeoffTriggerContext(
            nav_pitch_deg=self._row_event_value(telemetry, "NavPitch", trigger),
            pitch_deg=self._row_event_value(telemetry, "Pitch", trigger),
            nav_roll_deg=self._row_event_value(telemetry, "NavRoll", trigger),
            roll_deg=self._row_event_value(telemetry, "Roll", trigger),
            airspeed=self._row_event_airspeed(telemetry, trigger),
            throttle_output_pct=self._row_event_value(telemetry, "ThO", trigger),
            gps_groundspeed_m_s=self._event_groundspeed(trigger),
        )

    def _event_row(
        self,
        message: str,
        event: TakeoffExecutionEvent,
    ) -> _TelemetryRow | None:
        candidates = [
            telemetry
            for telemetry in self._rows(message)
            if self.execution.start_us <= telemetry.time_us <= event.time_us
        ]
        return candidates[-1] if candidates else None

    def _row_event_value(
        self,
        telemetry: _TelemetryRow | None,
        column: str,
        event: TakeoffExecutionEvent,
    ) -> EventTelemetryValue | None:
        if telemetry is None:
            return None
        value = self._finite_float(telemetry.row.get(column))
        if value is None:
            return None
        return EventTelemetryValue(
            value,
            telemetry.time_us,
            event.time_us - telemetry.time_us,
        )

    def _row_event_airspeed(
        self,
        telemetry: _TelemetryRow | None,
        event: TakeoffExecutionEvent,
    ) -> EventAirspeedValue | None:
        if telemetry is None:
            return None
        value = self._finite_float(telemetry.row.get("As"))
        estimate_type = self._integer(telemetry.row.get("AsT"))
        if value is None or value < 0 or not estimate_type:
            return None
        return EventAirspeedValue(
            value,
            estimate_type,
            telemetry.time_us,
            event.time_us - telemetry.time_us,
        )

    def _event_groundspeed(
        self,
        event: TakeoffExecutionEvent,
    ) -> EventTelemetryValue | None:
        gps = self.flight_log.get("GPS")
        if gps.empty or not {"TimeUS", "Spd", "Status"}.issubset(gps.columns):
            return None
        has_used_field = "U" in gps.columns
        candidates = []
        for telemetry in self._rows("GPS"):
            if not (self.execution.start_us <= telemetry.time_us <= event.time_us):
                continue
            value = self._finite_float(telemetry.row.get("Spd"))
            status = self._integer(telemetry.row.get("Status"))
            used = self._integer(telemetry.row.get("U")) if has_used_field else 1
            if value is None or value < 0 or status is None or status < 3 or used != 1:
                continue
            candidates.append((telemetry, value))
        if not candidates:
            return None
        telemetry, value = max(
            candidates,
            key=lambda item: (item[0].time_us, item[0].source_order),
        )
        return EventTelemetryValue(
            value,
            telemetry.time_us,
            event.time_us - telemetry.time_us,
        )

    def _roll_extremum(
        self,
        interval: tuple[int, int] | None,
    ) -> RollExtremum | None:
        candidates = self._interval_values("CTUN", "Roll", interval)
        if not candidates:
            return None
        telemetry, value = max(candidates, key=lambda item: abs(item[1]))
        return RollExtremum(abs(value), value, telemetry.time_us)

    def _maximum_throttle(
        self,
        interval: tuple[int, int] | None,
    ) -> tuple[float | None, int | None]:
        candidates = self._interval_values("CTUN", "ThO", interval)
        if not candidates:
            return None, None
        telemetry, value = max(candidates, key=lambda item: item[1])
        return value, telemetry.time_us

    def _airspeed_envelope(
        self,
        interval: TakeoffControlInterval | None,
    ) -> AirspeedEnvelope | None:
        if interval is None:
            return None
        candidates = []
        for telemetry in self._interval_rows(
            "CTUN",
            (interval.start_us, interval.end_us),
        ):
            value = self._finite_float(telemetry.row.get("As"))
            estimate_type = self._integer(telemetry.row.get("AsT"))
            if value is None or value < 0 or not estimate_type:
                continue
            candidates.append((telemetry, value, estimate_type))
        if not candidates:
            return None
        minimum = min(candidates, key=lambda item: item[1])
        maximum = max(candidates, key=lambda item: item[1])
        return AirspeedEnvelope(
            minimum=AirspeedExtremum(
                minimum[1],
                minimum[2],
                minimum[0].time_us,
            ),
            maximum=AirspeedExtremum(
                maximum[1],
                maximum[2],
                maximum[0].time_us,
            ),
        )

    def _relative_altitude(
        self,
        trigger: TakeoffExecutionEvent,
        interval: TakeoffControlInterval | None,
    ) -> RelativeAltitudeMetrics | None:
        baseline = self._event_value("POS", "RelHomeAlt", trigger)
        if baseline is None or interval is None:
            return None

        minimum_candidates = self._interval_values(
            "POS",
            "RelHomeAlt",
            (interval.start_us, interval.end_us),
        )
        minimum = (
            min(minimum_candidates, key=lambda item: item[1])
            if minimum_candidates
            else None
        )
        endpoint = self._event_value_after(
            "POS",
            "RelHomeAlt",
            trigger.time_us,
            interval.end_us,
        )
        return RelativeAltitudeMetrics(
            trigger_altitude_m=baseline,
            minimum_altitude_m=minimum[1] if minimum is not None else None,
            minimum_time_us=minimum[0].time_us if minimum is not None else None,
            minimum_delta_m=(
                minimum[1] - baseline.value if minimum is not None else None
            ),
            endpoint_altitude_m=endpoint,
            endpoint_delta_m=(
                endpoint.value - baseline.value if endpoint is not None else None
            ),
        )

    def _event_value_after(
        self,
        message: str,
        column: str,
        minimum_time_us: int,
        event_time_us: int,
    ) -> EventTelemetryValue | None:
        candidates = []
        for telemetry in self._rows(message):
            if not minimum_time_us <= telemetry.time_us <= event_time_us:
                continue
            value = self._finite_float(telemetry.row.get(column))
            if value is not None:
                candidates.append((telemetry, value))
        if not candidates:
            return None
        telemetry, value = max(
            candidates,
            key=lambda item: (item[0].time_us, item[0].source_order),
        )
        return EventTelemetryValue(
            value,
            telemetry.time_us,
            event_time_us - telemetry.time_us,
        )

    def _interval_values(
        self,
        message: str,
        column: str,
        interval: tuple[int, int] | None,
    ) -> list[tuple[_TelemetryRow, float]]:
        if interval is None:
            return []
        values = []
        for telemetry in self._interval_rows(message, interval):
            value = self._finite_float(telemetry.row.get(column))
            if value is not None:
                values.append((telemetry, value))
        return values

    def _interval_rows(
        self,
        message: str,
        interval: tuple[int, int],
    ) -> list[_TelemetryRow]:
        start_us, end_us = interval
        return [
            telemetry
            for telemetry in self._rows(message)
            if start_us < telemetry.time_us < end_us
        ]

    def _rows(self, message: str) -> list[_TelemetryRow]:
        dataframe = self.flight_log.get(message)
        if dataframe.empty or "TimeUS" not in dataframe.columns:
            return []
        rows = []
        for source_order, (_, row) in enumerate(dataframe.iterrows()):
            time_us = self._integer(row.get("TimeUS"))
            if time_us is not None:
                rows.append(_TelemetryRow(time_us, source_order, row))
        return sorted(rows, key=lambda item: (item.time_us, item.source_order))

    @staticmethod
    def _finite_float(value: object) -> float | None:
        if isinstance(value, bool) or not isinstance(value, Real):
            return None
        result = float(value)
        return result if math.isfinite(result) else None

    @staticmethod
    def _integer(value: object) -> int | None:
        if isinstance(value, bool) or not isinstance(value, (Integral, Real)):
            return None
        numeric = float(value)
        if not math.isfinite(numeric) or not numeric.is_integer():
            return None
        return int(numeric)

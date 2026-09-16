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


class FixedThrottleTargetStatus(Enum):
    """Availability and observation state of a fixed throttle target."""

    UNAVAILABLE_CONFIGURATION = "unavailable_configuration"
    UNAVAILABLE_EVIDENCE = "unavailable_evidence"
    OBSERVED = "observed"
    NOT_OBSERVED_COMPLETED = "not_observed_completed"
    NOT_OBSERVED_CENSORED_MODE_EXIT = "not_observed_censored_mode_exit"


class ConfiguredMinimumAirspeedStatus(Enum):
    """Availability and observation state of configured minimum airspeed."""

    UNAVAILABLE_EVIDENCE = "unavailable_evidence"
    OBSERVED = "observed"
    NOT_OBSERVED_COMPLETED = "not_observed_completed"
    NOT_OBSERVED_CENSORED_MODE_EXIT = "not_observed_censored_mode_exit"


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
class PitchTrackingResidual:
    """Maximum eligible co-sampled pitch-demand tracking residual."""

    magnitude_deg: float
    signed_residual_deg: float
    nav_pitch_deg: float
    pitch_deg: float
    source_time_us: int
    interval_status: TakeoffControlIntervalStatus


@dataclass(frozen=True, slots=True)
class EventConfiguredMinimumAirspeedDelta:
    """Controller airspeed relative to configured minimum at an event sample."""

    delta_m_s: float
    airspeed_m_s: float
    configured_minimum_m_s: float
    estimate_type: int
    source_time_us: int
    age_us: int


@dataclass(frozen=True, slots=True)
class IntervalConfiguredMinimumAirspeedDelta:
    """Minimum signed configured-minimum airspeed delta in one interval."""

    delta_m_s: float
    airspeed_m_s: float
    configured_minimum_m_s: float
    estimate_type: int
    source_time_us: int
    interval_status: TakeoffControlIntervalStatus


@dataclass(frozen=True, slots=True)
class FixedThrottleTargetRise:
    """Conditional observation of a source-proven fixed takeoff maximum."""

    status: FixedThrottleTargetStatus
    suppression_release_time_us: int | None
    effective_target_pct: float | None
    target_time_us: int | None
    elapsed_s: float | None
    observed_throttle_output_pct: float | None
    interval_status: TakeoffControlIntervalStatus | None


@dataclass(frozen=True, slots=True)
class FirstObservedConfiguredMinimumAirspeed:
    """First owned CTUN observation at or above event-time AIRSPEED_MIN."""

    status: ConfiguredMinimumAirspeedStatus
    trigger_time_us: int
    observation_time_us: int | None
    elapsed_s: float | None
    observed_airspeed_m_s: float | None
    configured_minimum_m_s: float | None
    estimate_type: int | None
    interval_status: TakeoffControlIntervalStatus | None


@dataclass(frozen=True, slots=True)
class TimedObservedValue:
    """One finite observed value with its retained source timestamp."""

    value: float
    source_time_us: int


@dataclass(frozen=True, slots=True)
class PropulsionToConfiguredMinimumAirspeed:
    """Throttle-command and primary-battery evidence over the speed build."""

    start_us: int
    end_us: int
    maximum_throttle_command_pct: TimedObservedValue | None
    time_to_maximum_throttle_s: float | None
    continuous_peak_throttle_duration_s: float | None
    throttle_at_minimum_airspeed_pct: TimedObservedValue | None
    peak_battery_current_a: TimedObservedValue | None
    battery_instance: int = 0


@dataclass(frozen=True, slots=True)
class TakeoffConfigurationValue:
    """One launch-time parameter value and its display metadata."""

    name: str
    label: str
    value: float | None
    display_value: float | None
    unit: str | None


@dataclass(frozen=True, slots=True)
class TakeoffConfigurationGroup:
    """One human-oriented group of launch-time parameters."""

    name: str
    values: tuple[TakeoffConfigurationValue, ...]


@dataclass(frozen=True, slots=True)
class TakeoffConfigurationContext:
    """Selected configuration snapshotted at the firmware trigger."""

    trigger_time_us: int
    groups: tuple[TakeoffConfigurationGroup, ...]


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
    pitch_tracking_residual: PitchTrackingResidual | None
    trigger_configured_minimum_airspeed_delta: (
        EventConfiguredMinimumAirspeedDelta | None
    )
    interval_configured_minimum_airspeed_delta: (
        IntervalConfiguredMinimumAirspeedDelta | None
    )
    fixed_throttle_target_rise: FixedThrottleTargetRise
    first_observed_configured_minimum_airspeed: FirstObservedConfiguredMinimumAirspeed
    propulsion_to_configured_minimum_airspeed: (
        PropulsionToConfiguredMinimumAirspeed | None
    )
    configuration: TakeoffConfigurationContext
    airspeed_estimate_types: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class _TelemetryRow:
    """A telemetry row with validated time and retained source order."""

    time_us: int
    source_order: int
    row: pd.Series


@dataclass(frozen=True, slots=True)
class _ConfigurationParameterSpec:
    """Formatting metadata for one selected launch parameter."""

    name: str
    label: str
    unit: str | None = None
    scale: float = 1.0


class TakeoffPerformanceProcessor:
    """Build bounded performance evidence for one TAKEOFF-mode execution."""

    _FIXED_THROTTLE_PARAMETERS = (
        "TKOFF_OPTIONS",
        "TKOFF_THR_MAX",
        "THR_MAX",
        "FWD_BAT_VOLT_MIN",
        "FWD_BAT_VOLT_MAX",
        "FWD_BAT_THR_CUT",
        "BATT_WATT_MAX",
    )
    _CONFIGURATION_GROUPS = (
        (
            "Takeoff trigger conditions",
            (
                _ConfigurationParameterSpec(
                    "TKOFF_THR_MINACC", "Minimum acceleration", "m/s²"
                ),
                _ConfigurationParameterSpec("TKOFF_ACCEL_CNT", "Acceleration count"),
                _ConfigurationParameterSpec(
                    "TKOFF_THR_DELAY", "Throttle delay", "s", 0.1
                ),
                _ConfigurationParameterSpec(
                    "TKOFF_THR_MINSPD", "Minimum groundspeed", "m/s"
                ),
            ),
        ),
        (
            "Takeoff control",
            (
                _ConfigurationParameterSpec("TKOFF_ROTATE_SPD", "Rotate speed", "m/s"),
                _ConfigurationParameterSpec("TKOFF_GND_PITCH", "Ground pitch", "°"),
                _ConfigurationParameterSpec("TKOFF_LVL_PITCH", "Level-off pitch", "°"),
                _ConfigurationParameterSpec("TKOFF_ALT", "Takeoff altitude", "m"),
                _ConfigurationParameterSpec("TKOFF_DIST", "Takeoff distance", "m"),
                _ConfigurationParameterSpec("TKOFF_LVL_ALT", "Level-off altitude", "m"),
            ),
        ),
        (
            "Throttle",
            (
                _ConfigurationParameterSpec("TKOFF_THR_MAX", "Takeoff maximum", "%"),
                _ConfigurationParameterSpec("TKOFF_THR_MAX_T", "Maximum duration", "s"),
                _ConfigurationParameterSpec("TKOFF_THR_SLEW", "Slew rate", "%/s"),
                _ConfigurationParameterSpec("TKOFF_OPTIONS", "Options"),
                _ConfigurationParameterSpec("THR_MAX", "Normal maximum", "%"),
            ),
        ),
        (
            "Pitch / roll",
            (
                _ConfigurationParameterSpec("PTCH_TRIM_DEG", "Pitch trim", "°"),
                _ConfigurationParameterSpec("KFF_THR2PTCH", "Throttle-to-pitch KFF"),
                _ConfigurationParameterSpec("PTCH_LIM_MAX_DEG", "Maximum pitch", "°"),
                _ConfigurationParameterSpec(
                    "LEVEL_ROLL_LIMIT", "Level roll limit", "°"
                ),
                _ConfigurationParameterSpec("ROLL_LIMIT_DEG", "Roll limit", "°"),
            ),
        ),
        (
            "Airspeed",
            (
                _ConfigurationParameterSpec(
                    "AIRSPEED_MIN", "Configured minimum", "m/s"
                ),
                _ConfigurationParameterSpec("AIRSPEED_CRUISE", "Cruise", "m/s"),
                _ConfigurationParameterSpec("ARSPD_USE", "Use airspeed"),
                _ConfigurationParameterSpec("ARSPD_PRIMARY", "Primary sensor"),
            ),
        ),
    )

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
        first_minimum_airspeed = self._first_observed_configured_minimum_airspeed(
            trigger,
            control_interval,
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
            pitch_tracking_residual=self._pitch_tracking_residual(control_interval),
            trigger_configured_minimum_airspeed_delta=(
                self._trigger_configured_minimum_airspeed_delta(trigger)
            ),
            interval_configured_minimum_airspeed_delta=(
                self._interval_configured_minimum_airspeed_delta(control_interval)
            ),
            fixed_throttle_target_rise=self._fixed_throttle_target_rise(
                unsuppressed,
                control_interval,
            ),
            first_observed_configured_minimum_airspeed=first_minimum_airspeed,
            propulsion_to_configured_minimum_airspeed=(
                self._propulsion_to_configured_minimum_airspeed(
                    unsuppressed,
                    first_minimum_airspeed,
                    control_interval,
                )
            ),
            configuration=self._configuration_context(trigger.time_us),
            airspeed_estimate_types=self._airspeed_estimate_types(
                trigger_context,
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

    def _pitch_tracking_residual(
        self,
        interval: TakeoffControlInterval | None,
    ) -> PitchTrackingResidual | None:
        if interval is None:
            return None
        first_tecs = next(
            (
                telemetry
                for telemetry in self._interval_rows(
                    "TECS",
                    (interval.start_us, interval.end_us),
                )
                if self._finite_float(telemetry.row.get("ph")) is not None
            ),
            None,
        )
        if first_tecs is None:
            return None
        later_ctun = [
            telemetry
            for telemetry in self._interval_rows(
                "CTUN",
                (interval.start_us, interval.end_us),
            )
            if telemetry.time_us > first_tecs.time_us
        ]
        if len(later_ctun) < 2:
            return None

        candidates = []
        for telemetry in later_ctun[1:]:
            nav_pitch = self._finite_float(telemetry.row.get("NavPitch"))
            pitch = self._finite_float(telemetry.row.get("Pitch"))
            if nav_pitch is None or pitch is None:
                continue
            if not all(
                self._parameter_is_zero(parameter, telemetry.time_us)
                for parameter in (
                    "KFF_THR2PTCH",
                    "TKOFF_TDRAG_ELEV",
                    "TKOFF_TDRAG_SPD1",
                )
            ):
                continue
            residual = nav_pitch - pitch
            candidates.append((telemetry, nav_pitch, pitch, residual))
        if not candidates:
            return None
        telemetry, nav_pitch, pitch, residual = max(
            candidates,
            key=lambda item: abs(item[3]),
        )
        return PitchTrackingResidual(
            magnitude_deg=abs(residual),
            signed_residual_deg=residual,
            nav_pitch_deg=nav_pitch,
            pitch_deg=pitch,
            source_time_us=telemetry.time_us,
            interval_status=interval.status,
        )

    def _first_observed_configured_minimum_airspeed(
        self,
        trigger: TakeoffExecutionEvent,
        interval: TakeoffControlInterval | None,
    ) -> FirstObservedConfiguredMinimumAirspeed:
        if interval is None:
            return FirstObservedConfiguredMinimumAirspeed(
                ConfiguredMinimumAirspeedStatus.UNAVAILABLE_EVIDENCE,
                trigger.time_us,
                None,
                None,
                None,
                None,
                None,
                None,
            )

        comparable_sample_seen = False
        for telemetry in self._interval_rows(
            "CTUN",
            (interval.start_us, interval.end_us),
        ):
            airspeed = self._valid_airspeed(telemetry)
            if airspeed is None:
                continue
            configured_minimum = self._parameter_float(
                "AIRSPEED_MIN",
                telemetry.time_us,
            )
            if configured_minimum is None or configured_minimum < 0:
                return FirstObservedConfiguredMinimumAirspeed(
                    ConfiguredMinimumAirspeedStatus.UNAVAILABLE_EVIDENCE,
                    trigger.time_us,
                    None,
                    None,
                    None,
                    None,
                    None,
                    interval.status,
                )
            comparable_sample_seen = True
            value, estimate_type = airspeed
            if value >= configured_minimum:
                return FirstObservedConfiguredMinimumAirspeed(
                    ConfiguredMinimumAirspeedStatus.OBSERVED,
                    trigger.time_us,
                    telemetry.time_us,
                    (telemetry.time_us - trigger.time_us) / 1_000_000,
                    value,
                    configured_minimum,
                    estimate_type,
                    interval.status,
                )

        if not comparable_sample_seen:
            status = ConfiguredMinimumAirspeedStatus.UNAVAILABLE_EVIDENCE
        elif interval.status is TakeoffControlIntervalStatus.COMPLETED:
            status = ConfiguredMinimumAirspeedStatus.NOT_OBSERVED_COMPLETED
        else:
            status = ConfiguredMinimumAirspeedStatus.NOT_OBSERVED_CENSORED_MODE_EXIT
        return FirstObservedConfiguredMinimumAirspeed(
            status,
            trigger.time_us,
            None,
            None,
            None,
            None,
            None,
            interval.status,
        )

    def _propulsion_to_configured_minimum_airspeed(
        self,
        unsuppressed: TakeoffExecutionEvent | None,
        first_minimum: FirstObservedConfiguredMinimumAirspeed,
        interval: TakeoffControlInterval | None,
    ) -> PropulsionToConfiguredMinimumAirspeed | None:
        """Measure observed command/current from suppression release to speed."""
        end_us = first_minimum.observation_time_us
        if (
            unsuppressed is None
            or not self._event_is_owned(unsuppressed)
            or interval is None
            or first_minimum.status is not ConfiguredMinimumAirspeedStatus.OBSERVED
            or end_us is None
            or not interval.start_us <= unsuppressed.time_us <= end_us
            or end_us >= interval.end_us
        ):
            return None

        qualifying_row = self._configured_minimum_airspeed_row(
            first_minimum,
            interval,
        )
        if qualifying_row is None:
            return None

        start_us = unsuppressed.time_us
        throttle_candidates = []
        for telemetry in self._rows("CTUN"):
            if not start_us <= telemetry.time_us <= end_us:
                continue
            throttle = self._finite_float(telemetry.row.get("ThO"))
            if throttle is not None:
                throttle_candidates.append((telemetry, throttle))
        maximum_throttle = None
        if throttle_candidates:
            maximum_value = max(value for _, value in throttle_candidates)
            maximum_throttle = next(
                candidate
                for candidate in throttle_candidates
                if candidate[1] == maximum_value
            )

        throttle_at_minimum = self._finite_float(qualifying_row.row.get("ThO"))
        continuous_peak_duration_s = None
        if maximum_throttle is not None and throttle_at_minimum is not None:
            peak_time_us = maximum_throttle[0].time_us
            peak_value = maximum_throttle[1]
            if throttle_at_minimum == peak_value and all(
                throttle == peak_value
                for telemetry, throttle in throttle_candidates
                if peak_time_us <= telemetry.time_us <= end_us
            ):
                continuous_peak_duration_s = (end_us - peak_time_us) / 1_000_000
        current_candidates = []
        for telemetry in self._rows("BAT"):
            if not start_us <= telemetry.time_us <= end_us:
                continue
            if self._integer(telemetry.row.get("Inst")) != 0:
                continue
            current = self._finite_float(telemetry.row.get("Curr"))
            if current is not None:
                current_candidates.append((telemetry, current))
        peak_current = (
            max(current_candidates, key=lambda item: item[1])
            if current_candidates
            else None
        )

        return PropulsionToConfiguredMinimumAirspeed(
            start_us=start_us,
            end_us=end_us,
            maximum_throttle_command_pct=(
                TimedObservedValue(maximum_throttle[1], maximum_throttle[0].time_us)
                if maximum_throttle is not None
                else None
            ),
            time_to_maximum_throttle_s=(
                (maximum_throttle[0].time_us - start_us) / 1_000_000
                if maximum_throttle is not None
                else None
            ),
            continuous_peak_throttle_duration_s=continuous_peak_duration_s,
            throttle_at_minimum_airspeed_pct=(
                TimedObservedValue(throttle_at_minimum, qualifying_row.time_us)
                if throttle_at_minimum is not None
                else None
            ),
            peak_battery_current_a=(
                TimedObservedValue(peak_current[1], peak_current[0].time_us)
                if peak_current is not None
                else None
            ),
        )

    def _configured_minimum_airspeed_row(
        self,
        first_minimum: FirstObservedConfiguredMinimumAirspeed,
        interval: TakeoffControlInterval,
    ) -> _TelemetryRow | None:
        """Recover the exact CTUN row that established the first observation."""
        for telemetry in self._interval_rows(
            "CTUN",
            (interval.start_us, interval.end_us),
        ):
            if telemetry.time_us != first_minimum.observation_time_us:
                continue
            airspeed = self._valid_airspeed(telemetry)
            configured_minimum = self._parameter_float(
                "AIRSPEED_MIN",
                telemetry.time_us,
            )
            if (
                airspeed is not None
                and configured_minimum is not None
                and airspeed[0] == first_minimum.observed_airspeed_m_s
                and airspeed[1] == first_minimum.estimate_type
                and configured_minimum == first_minimum.configured_minimum_m_s
            ):
                return telemetry
        return None

    def _configuration_context(
        self, trigger_time_us: int
    ) -> TakeoffConfigurationContext:
        groups = []
        for group_name, specs in self._CONFIGURATION_GROUPS:
            values = []
            for spec in specs:
                value = self._parameter_float(spec.name, trigger_time_us)
                values.append(
                    TakeoffConfigurationValue(
                        spec.name,
                        spec.label,
                        value,
                        value * spec.scale if value is not None else None,
                        spec.unit,
                    )
                )
            groups.append(TakeoffConfigurationGroup(group_name, tuple(values)))
        return TakeoffConfigurationContext(trigger_time_us, tuple(groups))

    def _trigger_configured_minimum_airspeed_delta(
        self,
        trigger: TakeoffExecutionEvent,
    ) -> EventConfiguredMinimumAirspeedDelta | None:
        telemetry = self._event_row("CTUN", trigger)
        airspeed = self._valid_airspeed(telemetry)
        if telemetry is None or airspeed is None:
            return None
        configured_minimum = self._parameter_float(
            "AIRSPEED_MIN",
            telemetry.time_us,
        )
        if configured_minimum is None:
            return None
        value, estimate_type = airspeed
        return EventConfiguredMinimumAirspeedDelta(
            delta_m_s=value - configured_minimum,
            airspeed_m_s=value,
            configured_minimum_m_s=configured_minimum,
            estimate_type=estimate_type,
            source_time_us=telemetry.time_us,
            age_us=trigger.time_us - telemetry.time_us,
        )

    def _interval_configured_minimum_airspeed_delta(
        self,
        interval: TakeoffControlInterval | None,
    ) -> IntervalConfiguredMinimumAirspeedDelta | None:
        if interval is None:
            return None
        candidates = []
        for telemetry in self._interval_rows(
            "CTUN",
            (interval.start_us, interval.end_us),
        ):
            airspeed = self._valid_airspeed(telemetry)
            configured_minimum = self._parameter_float(
                "AIRSPEED_MIN",
                telemetry.time_us,
            )
            if airspeed is None or configured_minimum is None:
                continue
            value, estimate_type = airspeed
            candidates.append(
                (
                    telemetry,
                    value,
                    configured_minimum,
                    estimate_type,
                    value - configured_minimum,
                )
            )
        if not candidates:
            return None
        telemetry, value, configured_minimum, estimate_type, delta = min(
            candidates,
            key=lambda item: item[4],
        )
        return IntervalConfiguredMinimumAirspeedDelta(
            delta_m_s=delta,
            airspeed_m_s=value,
            configured_minimum_m_s=configured_minimum,
            estimate_type=estimate_type,
            source_time_us=telemetry.time_us,
            interval_status=interval.status,
        )

    def _fixed_throttle_target_rise(
        self,
        unsuppressed: TakeoffExecutionEvent | None,
        interval: TakeoffControlInterval | None,
    ) -> FixedThrottleTargetRise:
        if (
            unsuppressed is None
            or not self._event_is_owned(unsuppressed)
            or interval is None
            or not interval.start_us <= unsuppressed.time_us < interval.end_us
        ):
            return FixedThrottleTargetRise(
                FixedThrottleTargetStatus.UNAVAILABLE_EVIDENCE,
                None,
                None,
                None,
                None,
                None,
                interval.status if interval is not None else None,
            )

        start_us = unsuppressed.time_us
        initial_target = self._fixed_throttle_target_at(start_us)
        if initial_target is None:
            return self._unavailable_fixed_throttle_target(
                start_us,
                interval,
            )

        for telemetry in self._rows("CTUN"):
            if not start_us <= telemetry.time_us < interval.end_us:
                continue
            target = self._fixed_throttle_target_through(
                start_us,
                telemetry.time_us,
                initial_target,
            )
            if target is None:
                return self._unavailable_fixed_throttle_target(
                    start_us,
                    interval,
                )
            throttle = self._finite_float(telemetry.row.get("ThO"))
            if throttle is not None and throttle >= target:
                return FixedThrottleTargetRise(
                    status=FixedThrottleTargetStatus.OBSERVED,
                    suppression_release_time_us=start_us,
                    effective_target_pct=target,
                    target_time_us=telemetry.time_us,
                    elapsed_s=(telemetry.time_us - start_us) / 1_000_000,
                    observed_throttle_output_pct=throttle,
                    interval_status=interval.status,
                )

        target = self._fixed_throttle_target_through(
            start_us,
            interval.end_us,
            initial_target,
            include_end=False,
        )
        if target is None:
            return self._unavailable_fixed_throttle_target(
                start_us,
                interval,
            )
        status = (
            FixedThrottleTargetStatus.NOT_OBSERVED_COMPLETED
            if interval.status is TakeoffControlIntervalStatus.COMPLETED
            else FixedThrottleTargetStatus.NOT_OBSERVED_CENSORED_MODE_EXIT
        )
        return FixedThrottleTargetRise(
            status=status,
            suppression_release_time_us=start_us,
            effective_target_pct=target,
            target_time_us=None,
            elapsed_s=None,
            observed_throttle_output_pct=None,
            interval_status=interval.status,
        )

    def _unavailable_fixed_throttle_target(
        self,
        start_us: int,
        interval: TakeoffControlInterval,
    ) -> FixedThrottleTargetRise:
        return FixedThrottleTargetRise(
            status=FixedThrottleTargetStatus.UNAVAILABLE_CONFIGURATION,
            suppression_release_time_us=start_us,
            effective_target_pct=None,
            target_time_us=None,
            elapsed_s=None,
            observed_throttle_output_pct=None,
            interval_status=interval.status,
        )

    def _fixed_throttle_target_through(
        self,
        start_us: int,
        end_us: int,
        expected_target: float,
        *,
        include_end: bool = True,
    ) -> float | None:
        checkpoints = {start_us}
        if include_end:
            checkpoints.add(end_us)
        for parameter in self._FIXED_THROTTLE_PARAMETERS:
            checkpoints.update(
                change.time_us
                for change in self.flight_log.parameter_history.changes.get(
                    parameter,
                    (),
                )
                if start_us < change.time_us
                and (
                    change.time_us <= end_us if include_end else change.time_us < end_us
                )
            )
        for time_us in sorted(checkpoints):
            target = self._fixed_throttle_target_at(time_us)
            if target is None or target != expected_target:
                return None
        return expected_target

    def _fixed_throttle_target_at(self, time_us: int) -> float | None:
        options = self._parameter_integer("TKOFF_OPTIONS", time_us)
        takeoff_maximum = self._parameter_float("TKOFF_THR_MAX", time_us)
        if options is None or options & 1 or takeoff_maximum is None:
            return None
        target = (
            takeoff_maximum
            if takeoff_maximum != 0
            else self._parameter_float("THR_MAX", time_us)
        )
        if target is None or not 0 <= target <= 100:
            return None

        disabled_dynamic_modifiers = (
            self._parameter_float("FWD_BAT_VOLT_MIN", time_us) == 0
            and self._parameter_float("FWD_BAT_VOLT_MAX", time_us) == 0
            and self._parameter_float("FWD_BAT_THR_CUT", time_us) == 0
            and self._parameter_float("BATT_WATT_MAX", time_us) == 0
        )
        return target if disabled_dynamic_modifiers else None

    def _valid_airspeed(
        self,
        telemetry: _TelemetryRow | None,
    ) -> tuple[float, int] | None:
        if telemetry is None:
            return None
        value = self._finite_float(telemetry.row.get("As"))
        estimate_type = self._integer(telemetry.row.get("AsT"))
        if value is None or value < 0 or not estimate_type:
            return None
        return value, estimate_type

    def _airspeed_estimate_types(
        self,
        trigger_context: TakeoffTriggerContext,
        interval: TakeoffControlInterval | None,
    ) -> tuple[int, ...]:
        """Return distinct raw AsT values for usable presented evidence."""
        estimate_types = set()
        if trigger_context.airspeed is not None:
            estimate_types.add(trigger_context.airspeed.estimate_type)
        if interval is not None:
            for telemetry in self._interval_rows(
                "CTUN",
                (interval.start_us, interval.end_us),
            ):
                airspeed = self._valid_airspeed(telemetry)
                if airspeed is not None:
                    estimate_types.add(airspeed[1])
        return tuple(sorted(estimate_types))

    def _parameter_is_zero(self, name: str, time_us: int) -> bool:
        return self._parameter_float(name, time_us) == 0

    def _parameter_float(self, name: str, time_us: int) -> float | None:
        value = self.flight_log.parameter_history.value_at(name, time_us)
        return self._finite_float(value)

    def _parameter_integer(self, name: str, time_us: int) -> int | None:
        value = self.flight_log.parameter_history.value_at(name, time_us)
        return self._integer(value)

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


def format_takeoff_performance_report(
    analysis: TakeoffPerformanceAnalysis,
    takeoff_number: int,
    *,
    include_configuration: bool = True,
) -> str:
    """Render concise human output using trigger-relative event times."""
    lines = [f"TAKEOFF {takeoff_number}", "-" * 70]
    lines.extend(("", f"{'Status':<36} {_execution_status(analysis)}"))
    lines.extend(("", "Timing", f"  {'Firmware trigger':<34} 0.000 s"))
    timings = analysis.phase_timings
    for label, elapsed_s in (
        ("Throttle unsuppressed", timings.trigger_to_throttle_unsuppressed_s),
        ("Target/course finalized", timings.trigger_to_target_finalized_s),
        ("Takeoff control complete", timings.trigger_to_control_completed_s),
        ("TAKEOFF mode exited", timings.trigger_to_mode_exit_s),
    ):
        if elapsed_s is not None:
            lines.append(f"  {label:<34} {_format_relative_seconds(elapsed_s)}")

    airspeed_source = _airspeed_source_label(analysis.airspeed_estimate_types)
    lines.extend(("", "At trigger", f"  {'Airspeed source':<34} {airspeed_source}"))
    context = analysis.trigger_context
    if context.airspeed is not None and airspeed_source != "Unavailable":
        lines.append(f"  {'Airspeed':<34} {context.airspeed.value_m_s:.2f} m/s")
    if context.gps_groundspeed_m_s is not None:
        lines.append(
            f"  {'Groundspeed':<34} {context.gps_groundspeed_m_s.value:.2f} m/s"
        )
    trigger_delta = analysis.trigger_configured_minimum_airspeed_delta
    if trigger_delta is not None and airspeed_source != "Unavailable":
        lines.append(
            f"  {'Airspeed vs AIRSPEED_MIN':<34} "
            f"{_format_signed_decimal(trigger_delta.delta_m_s)} m/s"
        )
    if context.nav_pitch_deg is not None and context.pitch_deg is not None:
        lines.append(
            f"  {'Pitch demand / achieved':<34} "
            f"{context.nav_pitch_deg.value:.2f}° / {context.pitch_deg.value:.2f}°"
        )
    if context.nav_roll_deg is not None and context.roll_deg is not None:
        lines.append(
            f"  {'Roll demand / achieved':<34} "
            f"{context.nav_roll_deg.value:.2f}° / {context.roll_deg.value:.2f}°"
        )
    if airspeed_source != "Unavailable":
        lines.extend(("", "Airspeed build"))
        first_minimum = analysis.first_observed_configured_minimum_airspeed
        if first_minimum.status is ConfiguredMinimumAirspeedStatus.OBSERVED:
            lines.extend(
                (
                    (
                        f"  {'Time to AIRSPEED_MIN':<34} "
                        f"{_format_relative_seconds(first_minimum.elapsed_s)}"
                    ),
                    (
                        f"  {'Airspeed at AIRSPEED_MIN':<34} "
                        f"{first_minimum.observed_airspeed_m_s:.2f} m/s"
                    ),
                )
            )
        elif first_minimum.status is not (
            ConfiguredMinimumAirspeedStatus.UNAVAILABLE_EVIDENCE
        ):
            lines.append(
                f"  {'Time to AIRSPEED_MIN':<34} "
                f"{_minimum_airspeed_status(first_minimum.status)}"
            )
    lines.extend(("", "Takeoff control"))
    envelope = analysis.airspeed_envelope
    if envelope is not None:
        lines.append(
            f"  {'Airspeed range':<34} "
            f"{envelope.minimum.value_m_s:.2f}–{envelope.maximum.value_m_s:.2f} m/s"
        )
    residual = analysis.pitch_tracking_residual
    if residual is not None:
        lines.append(
            f"  {'Largest pitch tracking error':<34} "
            f"{_format_signed_decimal(residual.signed_residual_deg)}°"
        )
    roll = analysis.launch_response_roll
    if roll is not None:
        lines.append(f"  {'Maximum absolute roll':<34} {roll.magnitude_deg:.2f}°")
    altitude = analysis.relative_altitude
    if altitude is not None:
        if altitude.minimum_delta_m is not None:
            lines.append(
                f"  {'Minimum altitude delta':<34} "
                f"{_format_signed_decimal(altitude.minimum_delta_m)} m"
            )
        if altitude.endpoint_delta_m is not None:
            endpoint_label = (
                "Altitude gain at completion"
                if analysis.control_interval is not None
                and analysis.control_interval.status
                is TakeoffControlIntervalStatus.COMPLETED
                else "Altitude delta at mode exit"
            )
            lines.append(
                f"  {endpoint_label:<34} "
                f"{_format_signed_decimal(altitude.endpoint_delta_m)} m"
            )

    lines.extend(_format_throttle_context(analysis))
    if include_configuration:
        lines.extend(("", "Takeoff configuration"))
        lines.extend(_format_configuration(analysis.configuration))
    return "\n".join(lines)


def format_takeoff_performance_reports(
    analyses: tuple[TakeoffPerformanceAnalysis, ...],
    *,
    detected_execution_count: int | None = None,
) -> str:
    """Render an operational overview followed by evidence and configuration."""
    lines = ["TAKEOFF ANALYSIS", "=" * 70]
    detected_count = (
        len(analyses) if detected_execution_count is None else detected_execution_count
    )
    if detected_count < len(analyses):
        raise ValueError("detected execution count cannot be less than analyses")
    omitted_count = detected_count - len(analyses)
    lines.extend(
        (
            "",
            (
                f"{detected_count} TAKEOFF-mode "
                f"{_plural(detected_count, 'execution')} detected"
            ),
            f"{len(analyses)} triggered {_plural(len(analyses), 'takeoff')} analysed",
            (
                f"{omitted_count} non-trigger "
                f"{_plural(omitted_count, 'execution')} omitted"
            ),
        )
    )
    if not analyses:
        return "\n".join(lines)

    shared_configuration = all(
        analysis.configuration.groups == analyses[0].configuration.groups
        for analysis in analyses[1:]
    )
    if len(analyses) > 1:
        lines.extend(("", "Summary", "-" * 70, _format_comparison_table(analyses)))

    for number, analysis in enumerate(analyses, 1):
        lines.extend(
            (
                "",
                "",
                format_takeoff_performance_report(
                    analysis,
                    number,
                    include_configuration=False,
                ),
            )
        )

    if shared_configuration:
        lines.extend(("", "", "TAKEOFF CONFIGURATION", "=" * 70))
        if len(analyses) > 1:
            lines.append(f"Applies to TAKEOFF 1–{len(analyses)}")
        lines.extend(_format_configuration(analyses[0].configuration))
    else:
        for number, analysis in enumerate(analyses, 1):
            lines.extend(
                (
                    "",
                    "",
                    f"TAKEOFF {number} CONFIGURATION",
                    "=" * 70,
                    *_format_configuration(analysis.configuration),
                )
            )
    return "\n".join(lines)


def _format_configuration(
    configuration: TakeoffConfigurationContext,
) -> list[str]:
    """Render trigger-time configuration without observational evidence."""
    lines: list[str] = []
    for group in configuration.groups:
        lines.extend(("", group.name))
        for value in group.values:
            lines.append(f"  {value.name:<28} {_format_configuration_value(value)}")
            if value.name == "TKOFF_ROTATE_SPD":
                lines.append(f"  {'Rotation control':<28} {_rotation_control(value)}")
    return lines


def _rotation_control(value: TakeoffConfigurationValue) -> str:
    """Describe speed gating without inferring a physical takeoff method."""
    if value.value is None:
        return "Unavailable"
    if value.value == 0:
        return "No speed-gated rotation"
    return "Speed-gated rotation"


def _execution_status(analysis: TakeoffPerformanceAnalysis) -> str:
    """Return the plain automatic-control interval status."""
    if analysis.control_interval is None:
        return "Unavailable"
    if analysis.control_interval.status is TakeoffControlIntervalStatus.COMPLETED:
        return "Completed"
    return "Mode exit before completion"


def _minimum_airspeed_status(status: ConfiguredMinimumAirspeedStatus) -> str:
    """Return a concise observation status without exposing enum names."""
    if status is ConfiguredMinimumAirspeedStatus.NOT_OBSERVED_COMPLETED:
        return "Not observed before completion"
    if status is ConfiguredMinimumAirspeedStatus.NOT_OBSERVED_CENSORED_MODE_EXIT:
        return "Not observed before mode exit"
    return "Unavailable"


def _format_throttle_context(analysis: TakeoffPerformanceAnalysis) -> list[str]:
    """Render propulsion-build evidence without implying power or thrust."""
    throttle = analysis.throttle_command
    propulsion = analysis.propulsion_to_configured_minimum_airspeed
    if propulsion is None:
        return []

    maximum = propulsion.maximum_throttle_command_pct
    time_to_maximum = propulsion.time_to_maximum_throttle_s
    continuous_peak_duration = propulsion.continuous_peak_throttle_duration_s
    at_minimum = propulsion.throttle_at_minimum_airspeed_pct
    peak_current = propulsion.peak_battery_current_a
    fixed = analysis.fixed_throttle_target_rise
    fixed_is_presented = fixed.status in {
        FixedThrottleTargetStatus.OBSERVED,
        FixedThrottleTargetStatus.NOT_OBSERVED_COMPLETED,
        FixedThrottleTargetStatus.NOT_OBSERVED_CENSORED_MODE_EXIT,
    }
    if not any(
        (
            throttle.at_unsuppressed,
            maximum,
            at_minimum,
            peak_current,
            fixed_is_presented,
        )
    ):
        return []

    evidence_lines = [
        (
            f"  {'Throttle at unsuppression':<38} "
            f"{_format_optional_percentage(throttle.at_unsuppressed.value if throttle.at_unsuppressed else None)}"
        ),
        (
            f"  {'Peak throttle':<38} "
            f"{_format_optional_percentage(maximum.value if maximum else None)}"
        ),
        (
            f"  {'Throttle ramp to peak':<38} "
            f"{_format_duration_seconds(time_to_maximum)}"
        ),
        (
            f"  {'Time at peak throttle':<38} "
            f"{_format_duration_seconds(continuous_peak_duration)}"
        ),
        (
            f"  {'Throttle at AIRSPEED_MIN':<38} "
            f"{_format_optional_percentage(at_minimum.value if at_minimum else None)}"
        ),
    ]
    if peak_current is not None:
        evidence_lines.append(
            f"  {'Peak battery current':<38} {peak_current.value:.1f} A"
        )

    if fixed.status is FixedThrottleTargetStatus.OBSERVED:
        evidence_lines.append(
            f"  {'Fixed throttle target':<38} Observed at "
            f"{fixed.observed_throttle_output_pct:.2f}%"
        )
    elif fixed.status is FixedThrottleTargetStatus.NOT_OBSERVED_COMPLETED:
        evidence_lines.append(
            f"  {'Fixed throttle target':<38} Not observed before completion"
        )
    elif fixed.status is FixedThrottleTargetStatus.NOT_OBSERVED_CENSORED_MODE_EXIT:
        evidence_lines.append(
            f"  {'Fixed throttle target':<38} Not observed before mode exit"
        )
    return ["", "Propulsion to AIRSPEED_MIN", *evidence_lines] if evidence_lines else []


def _format_optional_percentage(value: float | None) -> str:
    """Format optional normalized throttle command evidence."""
    return f"{value:.1f}%" if value is not None else "Unavailable"


def _format_duration_seconds(duration_s: float | None) -> str:
    """Format one observed duration without relative-time sign notation."""
    return f"{duration_s:.3f} s" if duration_s is not None else "unavailable"


def _format_comparison_table(
    analyses: tuple[TakeoffPerformanceAnalysis, ...],
) -> str:
    """Render a compact comparison using only existing result quantities."""
    headers = (
        "No.",
        "Status",
        "Time to AIRSPEED_MIN",
        "Peak current",
        "Max |roll|",
        "Min altitude Δ",
        "Endpoint altitude Δ",
    )
    rows = []
    for number, analysis in enumerate(analyses, 1):
        first = analysis.first_observed_configured_minimum_airspeed
        propulsion = analysis.propulsion_to_configured_minimum_airspeed
        peak_current = propulsion.peak_battery_current_a if propulsion else None
        roll = analysis.launch_response_roll
        altitude = analysis.relative_altitude
        rows.append(
            (
                str(number),
                _execution_status(analysis),
                (
                    _format_relative_seconds(first.elapsed_s)
                    if first.status is ConfiguredMinimumAirspeedStatus.OBSERVED
                    else "—"
                ),
                f"{peak_current.value:.1f} A" if peak_current is not None else "—",
                f"{roll.magnitude_deg:.2f}°" if roll is not None else "—",
                (
                    f"{_format_signed_decimal(altitude.minimum_delta_m)} m"
                    if altitude is not None and altitude.minimum_delta_m is not None
                    else "—"
                ),
                (
                    f"{_format_signed_decimal(altitude.endpoint_delta_m)} m"
                    if altitude is not None and altitude.endpoint_delta_m is not None
                    else "—"
                ),
            )
        )
    widths = [
        max(len(header), *(len(row[index]) for row in rows))
        for index, header in enumerate(headers)
    ]
    lines = [
        "  ".join(header.ljust(widths[index]) for index, header in enumerate(headers))
    ]
    lines.append("  ".join("-" * width for width in widths))
    lines.extend(
        "  ".join(value.ljust(widths[index]) for index, value in enumerate(row))
        for row in rows
    )
    return "\n".join(lines)


def _plural(count: int, singular: str) -> str:
    """Return a simple count-sensitive report noun."""
    return singular if count == 1 else f"{singular}s"


def _format_signed_decimal(value: float) -> str:
    """Render a signed delta without decorating exact zero as positive."""
    if value == 0:
        return "0.00"
    return f"{value:+.2f}"


def _format_configuration_value(value: TakeoffConfigurationValue) -> str:
    """Format one launch parameter without inventing unavailable evidence."""
    if value.display_value is None:
        return "unavailable"
    if value.name == "TKOFF_OPTIONS":
        return _format_takeoff_options(value.display_value)
    integer_parameters = {
        "TKOFF_ACCEL_CNT",
        "ARSPD_USE",
        "ARSPD_PRIMARY",
    }
    rendered = (
        f"{value.display_value:.0f}"
        if value.name in integer_parameters
        else f"{value.display_value:.1f}"
    )
    if value.unit is None:
        return rendered
    separator = "" if value.unit in {"%", "%/s", "°"} else " "
    return f"{rendered}{separator}{value.unit}"


def _format_takeoff_options(value: float) -> str:
    """Decode the Plane 4.7.x TKOFF_OPTIONS bitmask without hiding raw bits."""
    if not math.isfinite(value) or not value.is_integer():
        return "unavailable"
    raw_mask = int(value)
    mask = raw_mask & 0xFFFFFFFF
    if mask == 0:
        return "0 — None"

    descriptions = []
    if mask & 1:
        descriptions.append("Allow TECS throttle range")
    unknown_mask = mask & ~1
    descriptions.extend(
        f"unknown bit {bit}" for bit in range(32) if unknown_mask & (1 << bit)
    )
    return f"{raw_mask} — {', '.join(descriptions)}"


def _airspeed_source_label(estimate_types: tuple[int, ...]) -> str:
    """Describe retained CTUN airspeed sources without implying uniformity."""
    sources = set(estimate_types)
    if not sources or not sources <= {1, 2, 3}:
        return "Unavailable"
    if sources == {1}:
        return "Airspeed sensor"
    if 1 not in sources:
        return "Synthetic estimate"
    return "Mixed sensor / synthetic estimate"


def _format_relative_seconds(elapsed_s: float | None) -> str:
    """Format one relative event time for normal human output."""
    if elapsed_s is None:
        return "unavailable"
    if elapsed_s == 0:
        return "0.000 s"
    return f"{elapsed_s:+.3f} s"

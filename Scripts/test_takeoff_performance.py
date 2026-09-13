"""Focused synthetic tests for TAKEOFF-mode performance evidence."""

import math

import pandas as pd
from core.flight_data import FlightLog
from core.takeoff_execution import (
    TakeoffEntryContext,
    TakeoffExecution,
    TakeoffExecutionEvent,
    TakeoffExecutionEventType,
    TakeoffTerminationReason,
)
from core.takeoff_performance import (
    TakeoffControlIntervalStatus,
    TakeoffPerformanceProcessor,
)

START_US = 1_000_000
TRIGGER_US = 2_000_000
UNSUPPRESSED_US = 3_000_000
TARGET_US = 4_000_000
COMPLETION_US = 6_000_000
MODE_EXIT_US = 7_000_000


def _table(rows, columns):
    """Build a compact synthetic message table."""
    return pd.DataFrame(rows, columns=columns)


def _event(time_us, event_type):
    """Build one takeoff execution event."""
    return TakeoffExecutionEvent(time_us, event_type)


def _execution(
    *,
    trigger=True,
    target=True,
    completion=True,
    entry_context=TakeoffEntryContext.TAKEOFF_MODE,
):
    """Build a representative immutable execution."""
    events = []
    if trigger:
        events.append(_event(TRIGGER_US, TakeoffExecutionEventType.TRIGGERED_AUTO))
    events.append(
        _event(
            UNSUPPRESSED_US,
            TakeoffExecutionEventType.THROTTLE_UNSUPPRESSED,
        )
    )
    if target:
        events.append(
            _event(
                TARGET_US,
                TakeoffExecutionEventType.TARGET_COURSE_FINALIZED,
            )
        )
    if completion:
        events.append(
            _event(
                COMPLETION_US,
                TakeoffExecutionEventType.TAKEOFF_CONTROL_COMPLETED,
            )
        )
    return TakeoffExecution(
        start_us=START_US,
        end_us=MODE_EXIT_US,
        mission_item_number=None,
        command_id=None,
        termination_reason=TakeoffTerminationReason.MODE_EXIT,
        events=tuple(events),
        entry_context=entry_context,
    )


def _flight_log(*, ctun=(), gps=(), pos=(), baro=()):
    """Build only telemetry consumed by performance analysis."""
    return FlightLog(
        messages={
            "CTUN": _table(
                ctun,
                (
                    "TimeUS",
                    "NavPitch",
                    "Pitch",
                    "NavRoll",
                    "Roll",
                    "As",
                    "AsT",
                    "ThO",
                ),
            ),
            "GPS": _table(gps, ("TimeUS", "I", "Status", "Spd", "U")),
            "POS": _table(pos, ("TimeUS", "RelHomeAlt")),
            "BARO": _table(baro, ("TimeUS", "Alt")),
        }
    )


def _analyse(flight_log, execution=None):
    """Run the focused processor."""
    return TakeoffPerformanceProcessor(
        flight_log,
        execution or _execution(),
    ).analyse()


def test_trigger_context_uses_latest_valid_owned_samples_without_future_data():
    """Each event value is causal and retains its source timestamp and age."""
    flight_log = _flight_log(
        ctun=(
            (1_700_000, 5.0, 4.0, 1.0, 2.0, 7.0, 1, 0.0),
            (1_900_000, 6.0, 4.5, 2.0, 3.0, 8.0, 1, 10.0),
            (2_100_000, 99.0, 99.0, 99.0, 99.0, 99.0, 1, 99.0),
        ),
        gps=(
            (1_600_000, 0, 3, 2.5, 1),
            (1_800_000, 1, 3, 90.0, 0),
            (1_900_000, 0, 2, 80.0, 1),
            (2_100_000, 0, 3, 70.0, 1),
        ),
    )

    analysis = _analyse(flight_log)

    assert analysis is not None
    context = analysis.trigger_context
    assert context.nav_pitch_deg is not None
    assert context.nav_pitch_deg.value == 6.0
    assert context.nav_pitch_deg.source_time_us == 1_900_000
    assert context.nav_pitch_deg.age_us == 100_000
    assert context.pitch_deg is not None
    assert context.pitch_deg.value == 4.5
    assert context.pitch_deg.source_time_us == 1_900_000
    assert context.nav_roll_deg is not None
    assert context.nav_roll_deg.source_time_us == 1_900_000
    assert context.airspeed is not None
    assert context.airspeed.value_m_s == 8.0
    assert context.airspeed.estimate_type == 1
    assert context.airspeed.age_us == 100_000
    assert context.throttle_output_pct is not None
    assert context.throttle_output_pct.value == 10.0
    assert context.gps_groundspeed_m_s is not None
    assert context.gps_groundspeed_m_s.value == 2.5
    assert context.gps_groundspeed_m_s.source_time_us == 1_600_000
    assert context.gps_groundspeed_m_s.age_us == 400_000


def test_trigger_context_rejects_nonfinite_and_unusable_speed_evidence():
    """Non-finite CTUN and unusable speed rows remain unavailable."""
    flight_log = _flight_log(
        ctun=(
            (1_900_000, math.nan, math.inf, -math.inf, math.nan, -1.0, 1, math.inf),
            (1_950_000, math.nan, math.inf, -math.inf, math.nan, 12.0, 0, math.nan),
        ),
        gps=((1_900_000, 0, 2, math.nan, 1),),
    )

    analysis = _analyse(flight_log)

    assert analysis is not None
    context = analysis.trigger_context
    assert context.nav_pitch_deg is None
    assert context.pitch_deg is None
    assert context.nav_roll_deg is None
    assert context.roll_deg is None
    assert context.airspeed is None
    assert context.throttle_output_pct is None
    assert context.gps_groundspeed_m_s is None


def test_gps_without_used_field_preserves_single_receiver_compatibility():
    """GPS rows remain usable when the legacy schema has no U field."""
    flight_log = FlightLog(
        messages={
            "GPS": _table(
                ((1_900_000, 0, 3, 3.25),),
                ("TimeUS", "I", "Status", "Spd"),
            )
        }
    )

    analysis = _analyse(flight_log)

    assert analysis is not None
    groundspeed = analysis.trigger_context.gps_groundspeed_m_s
    assert groundspeed is not None
    assert groundspeed.value == 3.25


def test_launch_response_roll_extremum_is_bounded_and_preserves_sign():
    """Maximum absolute roll excludes trigger, endpoint, and future rows."""
    flight_log = _flight_log(
        ctun=(
            (TRIGGER_US, 0.0, 0.0, 0.0, 80.0, 8.0, 1, 0.0),
            (2_500_000, 0.0, 0.0, 0.0, 12.0, 8.0, 1, 20.0),
            (3_000_000, 0.0, 0.0, 0.0, -25.0, 9.0, 1, 40.0),
            (TARGET_US, 0.0, 0.0, 0.0, 90.0, 10.0, 1, 60.0),
            (4_500_000, 0.0, 0.0, 0.0, -100.0, 11.0, 1, 80.0),
        )
    )

    analysis = _analyse(flight_log)

    assert analysis is not None
    extremum = analysis.launch_response_roll
    assert extremum is not None
    assert extremum.magnitude_deg == 25.0
    assert extremum.signed_roll_deg == -25.0
    assert extremum.source_time_us == 3_000_000


def test_throttle_context_is_threshold_free_and_causally_sampled():
    """Throttle context reports sampled commands without threshold timing."""
    flight_log = _flight_log(
        ctun=(
            (1_900_000, 0.0, 0.0, 0.0, 0.0, 8.0, 1, 5.0),
            (2_500_000, 0.0, 0.0, 0.0, 0.0, 9.0, 1, 30.0),
            (2_900_000, 0.0, 0.0, 0.0, 0.0, 10.0, 1, 45.0),
            (3_500_000, 0.0, 0.0, 0.0, 0.0, 11.0, 1, 70.0),
            (3_900_000, 0.0, 0.0, 0.0, 0.0, 12.0, 1, 65.0),
            (4_100_000, 0.0, 0.0, 0.0, 0.0, 13.0, 1, 100.0),
        )
    )

    analysis = _analyse(flight_log)

    assert analysis is not None
    assert analysis.trigger_context.throttle_output_pct is not None
    assert analysis.trigger_context.throttle_output_pct.value == 5.0
    throttle = analysis.throttle_command
    assert throttle.at_unsuppressed is not None
    assert throttle.at_unsuppressed.value == 45.0
    assert throttle.at_unsuppressed.age_us == 100_000
    assert throttle.at_target_finalized is not None
    assert throttle.at_target_finalized.value == 65.0
    assert throttle.launch_response_max_pct == 70.0
    assert throttle.launch_response_max_time_us == 3_500_000


def test_completed_airspeed_envelope_rejects_invalid_and_boundary_rows():
    """Completed interval uses only valid interior controller airspeed."""
    flight_log = _flight_log(
        ctun=(
            (TRIGGER_US, 0.0, 0.0, 0.0, 0.0, 1.0, 1, 0.0),
            (2_500_000, 0.0, 0.0, 0.0, 0.0, 9.0, 1, 20.0),
            (3_000_000, 0.0, 0.0, 0.0, 0.0, 2.0, 0, 30.0),
            (4_000_000, 0.0, 0.0, 0.0, 0.0, math.nan, 1, 40.0),
            (5_500_000, 0.0, 0.0, 0.0, 0.0, 18.0, 3, 50.0),
            (COMPLETION_US, 0.0, 0.0, 0.0, 0.0, 99.0, 1, 60.0),
        )
    )

    analysis = _analyse(flight_log)

    assert analysis is not None
    assert analysis.control_interval is not None
    assert analysis.control_interval.status is TakeoffControlIntervalStatus.COMPLETED
    envelope = analysis.airspeed_envelope
    assert envelope is not None
    assert envelope.minimum.value_m_s == 9.0
    assert envelope.minimum.source_time_us == 2_500_000
    assert envelope.minimum.estimate_type == 1
    assert envelope.maximum.value_m_s == 18.0
    assert envelope.maximum.source_time_us == 5_500_000
    assert envelope.maximum.estimate_type == 3


def test_censored_interval_excludes_at_and_after_mode_exit():
    """Post-exit attractive samples cannot change censored extrema."""
    flight_log = _flight_log(
        ctun=(
            (2_500_000, 0.0, 0.0, 0.0, 4.0, 8.0, 1, 20.0),
            (6_500_000, 0.0, 0.0, 0.0, -7.0, 15.0, 1, 80.0),
            (MODE_EXIT_US, 0.0, 0.0, 0.0, 100.0, 100.0, 1, 100.0),
            (7_100_000, 0.0, 0.0, 0.0, 110.0, 110.0, 1, 100.0),
        )
    )

    analysis = _analyse(flight_log, _execution(completion=False))

    assert analysis is not None
    assert analysis.control_interval is not None
    assert analysis.control_interval.status is (
        TakeoffControlIntervalStatus.CENSORED_MODE_EXIT
    )
    assert analysis.airspeed_envelope is not None
    assert analysis.airspeed_envelope.maximum.value_m_s == 15.0


def test_completed_relative_altitude_uses_only_pos_and_one_baseline():
    """POS supplies baseline, post-trigger minimum, and completed gain."""
    flight_log = _flight_log(
        pos=(
            (1_900_000, 100.0),
            (2_100_000, 99.0),
            (3_000_000, 97.5),
            (5_900_000, 112.0),
            (COMPLETION_US, 113.0),
            (6_100_000, 200.0),
        ),
        baro=((3_000_000, -500.0),),
    )

    analysis = _analyse(flight_log)

    assert analysis is not None
    altitude = analysis.relative_altitude
    assert altitude is not None
    assert altitude.trigger_altitude_m.value == 100.0
    assert altitude.trigger_altitude_m.source_time_us == 1_900_000
    assert altitude.trigger_altitude_m.age_us == 100_000
    assert altitude.minimum_altitude_m == 97.5
    assert altitude.minimum_time_us == 3_000_000
    assert altitude.minimum_delta_m == -2.5
    assert altitude.endpoint_altitude_m is not None
    assert altitude.endpoint_altitude_m.value == 113.0
    assert altitude.endpoint_altitude_m.age_us == 0
    assert altitude.endpoint_delta_m == 13.0


def test_censored_relative_altitude_labels_interval_and_excludes_future_pos():
    """Mode-exit altitude is a censored endpoint and future POS is excluded."""
    flight_log = _flight_log(
        pos=(
            (1_900_000, 10.0),
            (2_500_000, 9.0),
            (6_900_000, 14.0),
            (7_100_000, -100.0),
        )
    )

    analysis = _analyse(flight_log, _execution(completion=False))

    assert analysis is not None
    assert analysis.control_interval is not None
    assert analysis.control_interval.status is (
        TakeoffControlIntervalStatus.CENSORED_MODE_EXIT
    )
    altitude = analysis.relative_altitude
    assert altitude is not None
    assert altitude.minimum_delta_m == -1.0
    assert altitude.endpoint_altitude_m is not None
    assert altitude.endpoint_altitude_m.value == 14.0
    assert altitude.endpoint_delta_m == 4.0


def test_missing_target_or_telemetry_keeps_aggregates_unavailable():
    """Missing required evidence never creates placeholder measurements."""
    analysis = _analyse(_flight_log(), _execution(target=False))

    assert analysis is not None
    assert analysis.launch_response_roll is None
    assert analysis.throttle_command.launch_response_max_pct is None
    assert analysis.trigger_context.nav_pitch_deg is None
    assert analysis.trigger_context.gps_groundspeed_m_s is None
    assert analysis.relative_altitude is None


def test_phase_timings_distinguish_completion_and_mode_exit():
    """Firmware phase observations retain separate elapsed meanings."""
    analysis = _analyse(_flight_log())

    assert analysis is not None
    timings = analysis.phase_timings
    assert timings.trigger_time_us == TRIGGER_US
    assert timings.trigger_to_throttle_unsuppressed_s == 1.0
    assert timings.trigger_to_target_finalized_s == 2.0
    assert timings.trigger_to_control_completed_s == 4.0
    assert timings.trigger_to_mode_exit_s == 5.0


def test_no_trigger_and_auto_mission_receive_no_mode13_performance_metrics():
    """Unsupported ownership cannot fabricate TAKEOFF-mode measurements."""
    assert _analyse(_flight_log(), _execution(trigger=False)) is None
    assert (
        _analyse(
            _flight_log(),
            _execution(entry_context=TakeoffEntryContext.AUTO_MISSION),
        )
        is None
    )

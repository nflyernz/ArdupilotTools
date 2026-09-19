"""Focused synthetic tests for TAKEOFF-mode performance evidence."""

import math

import pandas as pd
from core.flight_data import FlightLog
from core.params import ParameterChange, ParameterHistory
from core.takeoff_execution import (
    TakeoffEntryContext,
    TakeoffExecution,
    TakeoffExecutionEvent,
    TakeoffExecutionEventType,
    TakeoffTerminationReason,
)
from core.takeoff_performance import (
    AccelerationGateEvidenceStatus,
    ConfiguredMinimumAirspeedStatus,
    FixedThrottleTargetStatus,
    TakeoffControlIntervalStatus,
    TakeoffPerformanceProcessor,
    format_takeoff_performance_report,
    format_takeoff_performance_reports,
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


def _event(time_us, event_type, detail=""):
    """Build one takeoff execution event."""
    return TakeoffExecutionEvent(time_us, event_type, detail)


def _execution(
    *,
    trigger=True,
    unsuppressed=True,
    target=True,
    completion=True,
    entry_context=TakeoffEntryContext.TAKEOFF_MODE,
    armed_detail=None,
    trigger_detail="",
    trigger_time_us=TRIGGER_US,
    unsuppressed_time_us=UNSUPPRESSED_US,
):
    """Build a representative immutable execution."""
    events = []
    if armed_detail is not None:
        events.append(
            _event(
                trigger_time_us - 200_000,
                TakeoffExecutionEventType.ARMED_AUTO,
                armed_detail,
            )
        )
    if trigger:
        events.append(
            _event(
                trigger_time_us,
                TakeoffExecutionEventType.TRIGGERED_AUTO,
                trigger_detail,
            )
        )
    if unsuppressed:
        events.append(
            _event(
                unsuppressed_time_us,
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


def _history(initial_values=None, changes=None):
    """Build timestamped parameter state without synthetic PARM startup noise."""
    return ParameterHistory(initial_values or {}, changes or {})


def _flight_log(
    *,
    ctun=(),
    bat=(),
    gps=(),
    pos=(),
    baro=(),
    tecs=(),
    msg=(),
    stat=(),
    parameter_history=None,
):
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
            "BAT": _table(bat, ("TimeUS", "Inst", "Curr")),
            "GPS": _table(gps, ("TimeUS", "I", "Status", "Spd", "U")),
            "POS": _table(pos, ("TimeUS", "RelHomeAlt")),
            "BARO": _table(baro, ("TimeUS", "Alt")),
            "TECS": _table(tecs, ("TimeUS", "ph")),
            "MSG": _table(msg, ("TimeUS", "Message")),
            "STAT": _table(stat, ("TimeUS", "Stage", "Sup")),
        },
        parameter_history=parameter_history or ParameterHistory(),
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


def test_pitch_tracking_residual_uses_each_samples_parameter_state():
    """Later KFF changes exclude later rows without rewriting earlier evidence."""
    history = _history(
        {
            "KFF_THR2PTCH": 0.0,
            "TKOFF_TDRAG_ELEV": 0.0,
            "TKOFF_TDRAG_SPD1": 0.0,
        },
        {
            "KFF_THR2PTCH": (ParameterChange(4_000_000, 1.0),),
        },
    )
    flight_log = _flight_log(
        ctun=(
            (TRIGGER_US, 100.0, 0.0, 0.0, 0.0, 8.0, 1, 0.0),
            (2_500_000, 10.0, 5.0, 0.0, 0.0, 8.0, 1, 20.0),
            (3_500_000, 2.0, 10.0, 0.0, 0.0, 9.0, 1, 40.0),
            (4_500_000, 100.0, 0.0, 0.0, 0.0, 10.0, 1, 60.0),
            (COMPLETION_US, 200.0, 0.0, 0.0, 0.0, 11.0, 1, 80.0),
        ),
        tecs=((2_200_000, 0.1),),
        parameter_history=history,
    )

    analysis = _analyse(flight_log)

    assert analysis is not None
    residual = analysis.pitch_tracking_residual
    assert residual is not None
    assert residual.magnitude_deg == 8.0
    assert residual.signed_residual_deg == -8.0
    assert residual.nav_pitch_deg == 2.0
    assert residual.pitch_deg == 10.0
    assert residual.source_time_us == 3_500_000
    assert residual.interval_status is TakeoffControlIntervalStatus.COMPLETED


def test_pitch_tracking_residual_requires_zero_kff_and_tail_hold_parameters():
    """Unproven controller ownership or feed-forward makes rows ineligible."""
    ctun = (
        (3_000_000, 1.0, 1.0, 0.0, 0.0, 8.0, 1, 20.0),
        (3_500_000, 10.0, 1.0, 0.0, 0.0, 9.0, 1, 40.0),
    )
    nonzero_kff = _history(
        {
            "KFF_THR2PTCH": 1.0,
            "TKOFF_TDRAG_ELEV": 0.0,
            "TKOFF_TDRAG_SPD1": 0.0,
        }
    )
    active_tail_hold = _history(
        {
            "KFF_THR2PTCH": 0.0,
            "TKOFF_TDRAG_ELEV": 100.0,
            "TKOFF_TDRAG_SPD1": 8.0,
        }
    )

    kff_analysis = _analyse(
        _flight_log(
            ctun=ctun,
            tecs=((2_500_000, 0.1),),
            parameter_history=nonzero_kff,
        )
    )
    tail_hold_analysis = _analyse(
        _flight_log(
            ctun=ctun,
            tecs=((2_500_000, 0.1),),
            parameter_history=active_tail_hold,
        )
    )

    assert kff_analysis is not None
    assert kff_analysis.pitch_tracking_residual is None
    assert tail_hold_analysis is not None
    assert tail_hold_analysis.pitch_tracking_residual is None


def test_trigger_airspeed_delta_uses_parameter_at_ctun_sample_time():
    """A later AIRSPEED_MIN value cannot rewrite the causal trigger sample."""
    history = _history(
        {"AIRSPEED_MIN": 7.0},
        {"AIRSPEED_MIN": (ParameterChange(2_000_000, 20.0),)},
    )
    flight_log = _flight_log(
        ctun=((1_900_000, 0.0, 0.0, 0.0, 0.0, 8.0, 1, 0.0),),
        parameter_history=history,
    )

    analysis = _analyse(flight_log)

    assert analysis is not None
    delta = analysis.trigger_configured_minimum_airspeed_delta
    assert delta is not None
    assert delta.airspeed_m_s == 8.0
    assert delta.configured_minimum_m_s == 7.0
    assert delta.delta_m_s == 1.0
    assert delta.estimate_type == 1
    assert delta.source_time_us == 1_900_000
    assert delta.age_us == 100_000


def test_interval_airspeed_delta_respects_changes_and_excludes_boundaries():
    """Each valid interior CTUN row uses its own configured minimum."""
    history = _history(
        {"AIRSPEED_MIN": 7.0},
        {"AIRSPEED_MIN": (ParameterChange(3_000_000, 10.0),)},
    )
    flight_log = _flight_log(
        ctun=(
            (2_500_000, 0.0, 0.0, 0.0, 0.0, 9.0, 1, 0.0),
            (3_000_000, 0.0, 0.0, 0.0, 0.0, 11.0, 1, 0.0),
            (4_000_000, 0.0, 0.0, 0.0, 0.0, -100.0, 0, 0.0),
            (5_500_000, 0.0, 0.0, 0.0, 0.0, 12.0, 1, 0.0),
            (COMPLETION_US, 0.0, 0.0, 0.0, 0.0, 0.0, 1, 0.0),
        ),
        parameter_history=history,
    )

    analysis = _analyse(flight_log)

    assert analysis is not None
    delta = analysis.interval_configured_minimum_airspeed_delta
    assert delta is not None
    assert delta.delta_m_s == 1.0
    assert delta.airspeed_m_s == 11.0
    assert delta.configured_minimum_m_s == 10.0
    assert delta.estimate_type == 1
    assert delta.source_time_us == 3_000_000
    assert delta.interval_status is TakeoffControlIntervalStatus.COMPLETED


def test_airspeed_delta_requires_valid_airspeed_and_parameter_evidence():
    """AsT zero and missing AIRSPEED_MIN never become fabricated deltas."""
    flight_log = _flight_log(
        ctun=(
            (1_900_000, 0.0, 0.0, 0.0, 0.0, 8.0, 0, 0.0),
            (3_000_000, 0.0, 0.0, 0.0, 0.0, 9.0, 1, 0.0),
        )
    )

    analysis = _analyse(flight_log)

    assert analysis is not None
    assert analysis.trigger_configured_minimum_airspeed_delta is None
    assert analysis.interval_configured_minimum_airspeed_delta is None


def _fixed_throttle_history(
    *,
    options=0.0,
    takeoff_maximum=100.0,
    normal_maximum=90.0,
    changes=None,
):
    """Build the conservative source-proven fixed-target configuration."""
    return _history(
        {
            "TKOFF_OPTIONS": options,
            "TKOFF_THR_MAX": takeoff_maximum,
            "THR_MAX": normal_maximum,
            "FWD_BAT_VOLT_MIN": 0.0,
            "FWD_BAT_VOLT_MAX": 0.0,
            "FWD_BAT_THR_CUT": 0.0,
            "BATT_WATT_MAX": 0.0,
        },
        changes,
    )


def test_fixed_throttle_target_selects_first_sample_reaching_maximum():
    """Rise starts at suppression release and ignores arbitrary percentages."""
    flight_log = _flight_log(
        ctun=(
            (UNSUPPRESSED_US, 0.0, 0.0, 0.0, 0.0, 8.0, 1, 40.0),
            (3_500_000, 0.0, 0.0, 0.0, 0.0, 8.0, 1, 90.0),
            (4_000_000, 0.0, 0.0, 0.0, 0.0, 8.0, 1, 100.0),
            (4_500_000, 0.0, 0.0, 0.0, 0.0, 8.0, 1, 110.0),
        ),
        parameter_history=_fixed_throttle_history(),
    )

    analysis = _analyse(flight_log)

    assert analysis is not None
    rise = analysis.fixed_throttle_target_rise
    assert rise.status is FixedThrottleTargetStatus.OBSERVED
    assert rise.suppression_release_time_us == UNSUPPRESSED_US
    assert rise.effective_target_pct == 100.0
    assert rise.target_time_us == 4_000_000
    assert rise.elapsed_s == 1.0
    assert rise.observed_throttle_output_pct == 100.0
    assert rise.interval_status is TakeoffControlIntervalStatus.COMPLETED


def test_zero_takeoff_maximum_uses_normal_throttle_maximum():
    """TKOFF_THR_MAX zero selects THR_MAX through the firmware fallback."""
    flight_log = _flight_log(
        ctun=((4_000_000, 0.0, 0.0, 0.0, 0.0, 8.0, 1, 90.0),),
        parameter_history=_fixed_throttle_history(takeoff_maximum=0.0),
    )

    analysis = _analyse(flight_log)

    assert analysis is not None
    rise = analysis.fixed_throttle_target_rise
    assert rise.status is FixedThrottleTargetStatus.OBSERVED
    assert rise.effective_target_pct == 90.0
    assert rise.target_time_us == 4_000_000


def test_fixed_throttle_target_not_observed_has_explicit_endpoint_status():
    """Completed and mode-exit endpoints remain distinguishable censoring."""
    flight_log = _flight_log(
        ctun=((4_000_000, 0.0, 0.0, 0.0, 0.0, 8.0, 1, 99.0),),
        parameter_history=_fixed_throttle_history(),
    )

    completed = _analyse(flight_log)
    censored = _analyse(flight_log, _execution(completion=False))

    assert completed is not None
    completed_rise = completed.fixed_throttle_target_rise
    assert completed_rise.status is (FixedThrottleTargetStatus.NOT_OBSERVED_COMPLETED)
    assert completed_rise.effective_target_pct == 100.0
    assert completed_rise.target_time_us is None
    assert completed_rise.elapsed_s is None
    assert censored is not None
    censored_rise = censored.fixed_throttle_target_rise
    assert censored_rise.status is (
        FixedThrottleTargetStatus.NOT_OBSERVED_CENSORED_MODE_EXIT
    )
    assert censored_rise.interval_status is (
        TakeoffControlIntervalStatus.CENSORED_MODE_EXIT
    )


def test_dynamic_throttle_range_configuration_has_no_fixed_target():
    """Enabling TECS throttle range makes the static target unavailable."""
    analysis = _analyse(
        _flight_log(parameter_history=_fixed_throttle_history(options=1.0))
    )

    assert analysis is not None
    rise = analysis.fixed_throttle_target_rise
    assert rise.status is (FixedThrottleTargetStatus.UNAVAILABLE_CONFIGURATION)
    assert rise.effective_target_pct is None


def test_throttle_parameter_change_before_acquisition_invalidates_target():
    """A changed maximum cannot be silently carried through the rise interval."""
    history = _fixed_throttle_history(
        changes={
            "TKOFF_THR_MAX": (ParameterChange(3_500_000, 80.0),),
        }
    )
    flight_log = _flight_log(
        ctun=(
            (3_250_000, 0.0, 0.0, 0.0, 0.0, 8.0, 1, 70.0),
            (4_000_000, 0.0, 0.0, 0.0, 0.0, 8.0, 1, 100.0),
        ),
        parameter_history=history,
    )

    analysis = _analyse(flight_log)

    assert analysis is not None
    assert analysis.fixed_throttle_target_rise.status is (
        FixedThrottleTargetStatus.UNAVAILABLE_CONFIGURATION
    )


def test_throttle_change_at_unowned_endpoint_does_not_rewrite_interval():
    """A cross-stream endpoint remains exclusive for parameter ownership."""
    history = _fixed_throttle_history(
        changes={
            "TKOFF_OPTIONS": (ParameterChange(COMPLETION_US, 1.0),),
        }
    )
    analysis = _analyse(_flight_log(parameter_history=history))

    assert analysis is not None
    assert analysis.fixed_throttle_target_rise.status is (
        FixedThrottleTargetStatus.NOT_OBSERVED_COMPLETED
    )


def _pitch_history():
    """Return configuration that permits direct pitch residual evidence."""
    return _history(
        {
            "KFF_THR2PTCH": 0.0,
            "TKOFF_TDRAG_ELEV": 0.0,
            "TKOFF_TDRAG_SPD1": 0.0,
        }
    )


def test_pitch_residual_requires_post_trigger_tecs_evidence():
    """Triggered CTUN evidence alone cannot establish a fresh TECS solution."""
    flight_log = _flight_log(
        ctun=(
            (2_500_000, 50.0, 0.0, 0.0, 0.0, 8.0, 1, 0.0),
            (3_000_000, 10.0, 0.0, 0.0, 0.0, 8.0, 1, 0.0),
        ),
        parameter_history=_pitch_history(),
    )

    analysis = _analyse(flight_log)

    assert analysis is not None
    assert analysis.pitch_tracking_residual is None


def test_pitch_residual_requires_two_ctun_rows_strictly_after_tecs():
    """One post-refresh CTUN row remains same-loop ambiguous."""
    flight_log = _flight_log(
        ctun=((3_000_000, 50.0, 0.0, 0.0, 0.0, 8.0, 1, 0.0),),
        tecs=((2_500_000, 0.1),),
        parameter_history=_pitch_history(),
    )

    analysis = _analyse(flight_log)

    assert analysis is not None
    assert analysis.pitch_tracking_residual is None


def test_pitch_residual_excludes_first_post_tecs_and_stale_large_values():
    """Only the second strictly later CTUN row begins residual evaluation."""
    flight_log = _flight_log(
        ctun=(
            (2_100_000, 100.0, 0.0, 0.0, 0.0, 8.0, 1, 0.0),
            (2_500_000, 90.0, 0.0, 0.0, 0.0, 8.0, 1, 0.0),
            (3_000_000, 12.0, 5.0, 0.0, 0.0, 8.0, 1, 0.0),
        ),
        tecs=((2_200_000, 0.1),),
        parameter_history=_pitch_history(),
    )

    analysis = _analyse(flight_log)

    assert analysis is not None
    residual = analysis.pitch_tracking_residual
    assert residual is not None
    assert residual.signed_residual_deg == 7.0
    assert residual.source_time_us == 3_000_000


def test_pitch_residual_equal_tecs_ctun_timestamp_is_not_later():
    """Equal cross-stream timestamps do not establish CTUN propagation order."""
    flight_log = _flight_log(
        ctun=(
            (2_500_000, 100.0, 0.0, 0.0, 0.0, 8.0, 1, 0.0),
            (3_000_000, 50.0, 0.0, 0.0, 0.0, 8.0, 1, 0.0),
            (3_500_000, 9.0, 5.0, 0.0, 0.0, 8.0, 1, 0.0),
        ),
        tecs=((2_500_000, 0.1),),
        parameter_history=_pitch_history(),
    )

    analysis = _analyse(flight_log)

    assert analysis is not None
    residual = analysis.pitch_tracking_residual
    assert residual is not None
    assert residual.source_time_us == 3_500_000
    assert residual.signed_residual_deg == 4.0


def test_nonfinite_tecs_pitch_demand_does_not_establish_freshness():
    """A TECS row must carry a finite logged pitch solution."""
    flight_log = _flight_log(
        ctun=(
            (3_000_000, 10.0, 0.0, 0.0, 0.0, 8.0, 1, 0.0),
            (3_500_000, 9.0, 5.0, 0.0, 0.0, 8.0, 1, 0.0),
        ),
        tecs=((2_500_000, math.nan),),
        parameter_history=_pitch_history(),
    )

    analysis = _analyse(flight_log)

    assert analysis is not None
    assert analysis.pitch_tracking_residual is None


def test_first_observed_minimum_airspeed_selects_sample_without_interpolation():
    """The first qualifying logged sample supplies exact observed evidence."""
    flight_log = _flight_log(
        ctun=(
            (2_100_000, 0.0, 0.0, 0.0, 0.0, 9.0, 1, 0.0),
            (2_900_000, 0.0, 0.0, 0.0, 0.0, 11.2, 2, 0.0),
            (3_500_000, 0.0, 0.0, 0.0, 0.0, 12.0, 2, 0.0),
        ),
        parameter_history=_history({"AIRSPEED_MIN": 11.0}),
    )

    analysis = _analyse(flight_log)

    assert analysis is not None
    observed = analysis.first_observed_configured_minimum_airspeed
    assert observed.status is ConfiguredMinimumAirspeedStatus.OBSERVED
    assert observed.trigger_time_us == TRIGGER_US
    assert observed.observation_time_us == 2_900_000
    assert observed.elapsed_s == 0.9
    assert observed.observed_airspeed_m_s == 11.2
    assert observed.configured_minimum_m_s == 11.0
    assert observed.estimate_type == 2


def test_first_observed_minimum_airspeed_respects_event_time_parameter_change():
    """Each CTUN sample uses the AIRSPEED_MIN effective at its own TimeUS."""
    history = _history(
        {"AIRSPEED_MIN": 12.0},
        {"AIRSPEED_MIN": (ParameterChange(3_000_000, 10.0),)},
    )
    flight_log = _flight_log(
        ctun=(
            (2_500_000, 0.0, 0.0, 0.0, 0.0, 11.0, 1, 0.0),
            (3_000_000, 0.0, 0.0, 0.0, 0.0, 10.5, 1, 0.0),
        ),
        parameter_history=history,
    )

    analysis = _analyse(flight_log)

    assert analysis is not None
    observed = analysis.first_observed_configured_minimum_airspeed
    assert observed.status is ConfiguredMinimumAirspeedStatus.OBSERVED
    assert observed.observation_time_us == 3_000_000
    assert observed.configured_minimum_m_s == 10.0


def test_first_observed_minimum_airspeed_rejects_unusable_evidence():
    """AsT zero is skipped and missing AIRSPEED_MIN remains unavailable."""
    invalid_type = _analyse(
        _flight_log(
            ctun=((2_500_000, 0.0, 0.0, 0.0, 0.0, 20.0, 0, 0.0),),
            parameter_history=_history({"AIRSPEED_MIN": 10.0}),
        )
    )
    missing_parameter = _analyse(
        _flight_log(ctun=((2_500_000, 0.0, 0.0, 0.0, 0.0, 20.0, 1, 0.0),))
    )

    assert invalid_type is not None
    assert invalid_type.first_observed_configured_minimum_airspeed.status is (
        ConfiguredMinimumAirspeedStatus.UNAVAILABLE_EVIDENCE
    )
    assert missing_parameter is not None
    assert missing_parameter.first_observed_configured_minimum_airspeed.status is (
        ConfiguredMinimumAirspeedStatus.UNAVAILABLE_EVIDENCE
    )


def test_throttle_to_minimum_airspeed_uses_owned_event_times():
    """The duration shares the authoritative Vmin sample and suppression event."""
    analysis = _analyse(
        _flight_log(
            ctun=((4_250_000, 0.0, 0.0, 0.0, 0.0, 11.0, 1, 0.0),),
            parameter_history=_history({"AIRSPEED_MIN": 11.0}),
        )
    )

    assert analysis is not None
    observed = analysis.first_observed_configured_minimum_airspeed
    assert observed.observation_time_us == 4_250_000
    assert analysis.throttle_to_configured_minimum_airspeed_s == 1.25
    report = format_takeoff_performance_report(analysis, 1)
    assert "Trigger → AIRSPEED_MIN             2.250 s" in report
    assert "Throttle → AIRSPEED_MIN            1.250 s" in report
    assert "Throttle → AIRSPEED_MIN            +1.250 s" not in report


def test_throttle_to_minimum_airspeed_accepts_equal_event_timestamps():
    """Equal owned boundaries produce a zero duration without a leading sign."""
    analysis = _analyse(
        _flight_log(
            ctun=((UNSUPPRESSED_US, 0.0, 0.0, 0.0, 0.0, 11.0, 1, 0.0),),
            parameter_history=_history({"AIRSPEED_MIN": 11.0}),
        )
    )

    assert analysis is not None
    assert analysis.throttle_to_configured_minimum_airspeed_s == 0.0
    assert "Throttle → AIRSPEED_MIN            0.000 s" in (
        format_takeoff_performance_report(analysis, 1)
    )


def test_throttle_to_minimum_airspeed_rejects_missing_or_reversed_evidence():
    """Missing boundaries and reversed time order remain unavailable, not zero."""
    qualifying_log = _flight_log(
        ctun=((2_500_000, 0.0, 0.0, 0.0, 0.0, 11.0, 1, 0.0),),
        parameter_history=_history({"AIRSPEED_MIN": 11.0}),
    )
    missing_release = _analyse(
        qualifying_log,
        _execution(unsuppressed=False),
    )
    reversed_order = _analyse(qualifying_log)
    missing_minimum = _analyse(
        _flight_log(parameter_history=_history({"AIRSPEED_MIN": 11.0}))
    )

    assert missing_release is not None
    assert missing_release.throttle_to_configured_minimum_airspeed_s is None
    assert reversed_order is not None
    assert reversed_order.throttle_to_configured_minimum_airspeed_s is None
    assert missing_minimum is not None
    assert missing_minimum.throttle_to_configured_minimum_airspeed_s is None
    assert "Throttle → AIRSPEED_MIN            unavailable" in (
        format_takeoff_performance_report(reversed_order, 1)
    )
    assert "Throttle → AIRSPEED_MIN            -" not in (
        format_takeoff_performance_report(reversed_order, 1)
    )


def test_throttle_to_minimum_airspeed_does_not_reconstruct_stat_events():
    """Raw STAT evidence is not borrowed around the owned execution model."""
    analysis = _analyse(
        _flight_log(
            ctun=((4_000_000, 0.0, 0.0, 0.0, 0.0, 11.0, 1, 0.0),),
            stat=((3_000_000, 1, 0),),
            parameter_history=_history({"AIRSPEED_MIN": 11.0}),
        ),
        _execution(unsuppressed=False),
    )

    assert analysis is not None
    assert analysis.execution.throttle_unsuppressed is None
    assert analysis.throttle_to_configured_minimum_airspeed_s is None


def test_altitude_at_minimum_airspeed_uses_latest_causal_pos_without_interpolation():
    """Vmin altitude shares the qualifying CTUN event and latest earlier POS row."""
    analysis = _analyse(
        _flight_log(
            ctun=((3_000_000, 0.0, 0.0, 0.0, 0.0, 11.0, 1, 0.0),),
            pos=(
                (1_900_000, 100.0),
                (2_600_000, 102.5),
                (3_100_000, 999.0),
            ),
            parameter_history=_history({"AIRSPEED_MIN": 11.0}),
        )
    )

    assert analysis is not None
    observed = analysis.first_observed_configured_minimum_airspeed
    altitude = analysis.altitude_at_configured_minimum_airspeed
    assert observed.observation_time_us == 3_000_000
    assert altitude is not None
    assert altitude.source_time_us == 2_600_000
    assert altitude.value == 102.5
    assert altitude.age_us == 400_000
    assert analysis.altitude_delta_at_configured_minimum_airspeed_m == 2.5


def test_altitude_at_minimum_airspeed_preserves_negative_signed_delta():
    """Altitude loss at the shared Vmin event remains signed evidence."""
    analysis = _analyse(
        _flight_log(
            ctun=((3_000_000, 0.0, 0.0, 0.0, 0.0, 11.0, 1, 0.0),),
            pos=((1_900_000, 10.0), (2_900_000, 7.25)),
            parameter_history=_history({"AIRSPEED_MIN": 11.0}),
        )
    )

    assert analysis is not None
    assert analysis.altitude_delta_at_configured_minimum_airspeed_m == -2.75
    assert "Altitude Δ at AIRSPEED_MIN         -2.75 m" in (
        format_takeoff_performance_report(analysis, 1)
    )


def test_altitude_at_minimum_airspeed_requires_baseline_and_causal_pos():
    """Missing baseline or post-trigger causal POS keeps the result unavailable."""
    ctun = ((3_000_000, 0.0, 0.0, 0.0, 0.0, 11.0, 1, 0.0),)
    history = _history({"AIRSPEED_MIN": 11.0})
    missing_baseline = _analyse(
        _flight_log(
            ctun=ctun,
            pos=((2_500_000, 12.0),),
            parameter_history=history,
        )
    )
    missing_causal_sample = _analyse(
        _flight_log(
            ctun=ctun,
            pos=((1_900_000, 10.0), (3_100_000, 12.0)),
            parameter_history=history,
        )
    )

    assert missing_baseline is not None
    assert missing_baseline.altitude_at_configured_minimum_airspeed is None
    assert missing_baseline.altitude_delta_at_configured_minimum_airspeed_m is None
    assert missing_causal_sample is not None
    assert missing_causal_sample.altitude_at_configured_minimum_airspeed is None
    assert missing_causal_sample.altitude_delta_at_configured_minimum_airspeed_m is None


def test_propulsion_response_uses_owned_inclusive_interval_and_primary_battery():
    """Throttle and BAT instance zero share the suppression-to-speed bounds."""
    flight_log = _flight_log(
        ctun=(
            (2_900_000, 0.0, 0.0, 0.0, 0.0, 9.0, 1, 99.0),
            (UNSUPPRESSED_US, 0.0, 0.0, 0.0, 0.0, 9.0, 1, 20.0),
            (3_500_000, 0.0, 0.0, 0.0, 0.0, 9.5, 1, 90.0),
            (3_700_000, 0.0, 0.0, 0.0, 0.0, 9.5, 1, math.inf),
            (TARGET_US, 0.0, 0.0, 0.0, 0.0, 10.0, 1, 90.0),
            (4_100_000, 0.0, 0.0, 0.0, 0.0, 11.0, 1, 100.0),
        ),
        bat=(
            (2_900_000, 0, 50.0),
            (UNSUPPRESSED_US, 0, 5.0),
            (3_400_000, 1, 99.0),
            (3_600_000, 0, 25.0),
            (3_700_000, 0, math.inf),
            (TARGET_US, 0, 30.0),
            (4_100_000, 0, 100.0),
        ),
        parameter_history=_history({"AIRSPEED_MIN": 10.0}),
    )

    analysis = _analyse(flight_log)

    assert analysis is not None
    response = analysis.propulsion_to_configured_minimum_airspeed
    assert response is not None
    assert response.start_us == UNSUPPRESSED_US
    assert response.end_us == TARGET_US
    assert response.battery_instance == 0
    assert response.maximum_throttle_command_pct is not None
    assert response.maximum_throttle_command_pct.value == 90.0
    assert response.maximum_throttle_command_pct.source_time_us == 3_500_000
    assert response.time_to_maximum_throttle_s == 0.5
    assert response.continuous_peak_throttle_duration_s == 0.5
    assert response.throttle_at_minimum_airspeed_pct is not None
    assert response.throttle_at_minimum_airspeed_pct.value == 90.0
    assert response.throttle_at_minimum_airspeed_pct.source_time_us == TARGET_US
    assert response.peak_battery_current_a is not None
    assert response.peak_battery_current_a.value == 30.0
    assert response.peak_battery_current_a.source_time_us == TARGET_US

    report = format_takeoff_performance_report(analysis, 1)
    assert "Propulsion to AIRSPEED_MIN" in report
    assert "Throttle at unsuppression              20.0%" in report
    assert any(
        line.strip().startswith("Peak throttle") and line.endswith("90.0%")
        for line in report.splitlines()
    )
    assert any(
        line.strip().startswith("Throttle ramp to peak") and line.endswith("0.500 s")
        for line in report.splitlines()
    )
    assert "Time to peak throttle" not in report
    assert "Throttle ramp to peak                   +0.500 s" not in report
    assert any(
        line.strip().startswith("Time at peak throttle") and line.endswith("0.500 s")
        for line in report.splitlines()
    )
    assert "Time at peak throttle                  +0.500 s" not in report
    assert "Throttle at AIRSPEED_MIN               90.0%" in report
    assert "Peak battery current                   30.0 A" in report
    for time_us in (UNSUPPRESSED_US, TARGET_US, 3_500_000, 3_600_000):
        assert str(time_us) not in report


def test_propulsion_response_does_not_borrow_invalid_qualifying_throttle():
    """An invalid same-row ThO stays unavailable while earlier throttle remains."""
    flight_log = _flight_log(
        ctun=(
            (UNSUPPRESSED_US, 0.0, 0.0, 0.0, 0.0, 9.0, 1, 20.0),
            (3_500_000, 0.0, 0.0, 0.0, 0.0, 9.5, 1, 80.0),
            (TARGET_US, 0.0, 0.0, 0.0, 0.0, 10.0, 1, math.nan),
        ),
        parameter_history=_history({"AIRSPEED_MIN": 10.0}),
    )

    analysis = _analyse(flight_log)

    assert analysis is not None
    response = analysis.propulsion_to_configured_minimum_airspeed
    assert response is not None
    assert response.maximum_throttle_command_pct is not None
    assert response.maximum_throttle_command_pct.value == 80.0
    assert response.time_to_maximum_throttle_s == 0.5
    assert response.continuous_peak_throttle_duration_s is None
    assert response.throttle_at_minimum_airspeed_pct is None
    assert response.peak_battery_current_a is None
    report = format_takeoff_performance_report(analysis, 1)
    assert any(
        line.strip().startswith("Peak throttle") and line.endswith("80.0%")
        for line in report.splitlines()
    )
    assert any(
        line.strip().startswith("Throttle ramp to peak") and line.endswith("0.500 s")
        for line in report.splitlines()
    )
    assert "Throttle at AIRSPEED_MIN               Unavailable" in report
    assert "Peak battery current" not in report
    assert "Fixed throttle target" not in report


def test_peak_hold_requires_airspeed_minimum_sample_to_remain_at_peak():
    """The qualifying CTUN sample participates in continuous-hold evidence."""
    flight_log = _flight_log(
        ctun=(
            (UNSUPPRESSED_US, 0.0, 0.0, 0.0, 0.0, 9.0, 1, 20.0),
            (3_500_000, 0.0, 0.0, 0.0, 0.0, 9.5, 1, 90.0),
            (3_750_000, 0.0, 0.0, 0.0, 0.0, 9.5, 1, 90.0),
            (TARGET_US, 0.0, 0.0, 0.0, 0.0, 10.0, 1, 80.0),
        ),
        parameter_history=_history({"AIRSPEED_MIN": 10.0}),
    )

    analysis = _analyse(flight_log)

    assert analysis is not None
    response = analysis.propulsion_to_configured_minimum_airspeed
    assert response is not None
    assert response.maximum_throttle_command_pct is not None
    assert response.maximum_throttle_command_pct.source_time_us == 3_500_000
    assert response.continuous_peak_throttle_duration_s is None
    assert "Time at peak throttle                  unavailable" in (
        format_takeoff_performance_report(analysis, 1)
    )


def test_peak_hold_does_not_sum_separated_peak_periods():
    """One valid below-peak row breaks an otherwise repeated peak run."""
    flight_log = _flight_log(
        ctun=(
            (UNSUPPRESSED_US, 0.0, 0.0, 0.0, 0.0, 9.0, 1, 20.0),
            (3_400_000, 0.0, 0.0, 0.0, 0.0, 9.5, 1, 90.0),
            (3_600_000, 0.0, 0.0, 0.0, 0.0, 9.5, 1, 80.0),
            (TARGET_US, 0.0, 0.0, 0.0, 0.0, 10.0, 1, 90.0),
        ),
        parameter_history=_history({"AIRSPEED_MIN": 10.0}),
    )

    analysis = _analyse(flight_log)

    assert analysis is not None
    response = analysis.propulsion_to_configured_minimum_airspeed
    assert response is not None
    assert response.maximum_throttle_command_pct is not None
    assert response.maximum_throttle_command_pct.source_time_us == 3_400_000
    assert response.time_to_maximum_throttle_s == 0.4
    assert response.continuous_peak_throttle_duration_s is None


def test_propulsion_response_requires_observed_throttle_unsuppression():
    """The trigger is not substituted when suppression-release evidence is absent."""
    flight_log = _flight_log(
        ctun=((TARGET_US, 0.0, 0.0, 0.0, 0.0, 10.0, 1, 70.0),),
        bat=((3_500_000, 0, 25.0),),
        parameter_history=_history({"AIRSPEED_MIN": 10.0}),
    )

    analysis = _analyse(flight_log, _execution(unsuppressed=False))

    assert analysis is not None
    assert analysis.first_observed_configured_minimum_airspeed.status is (
        ConfiguredMinimumAirspeedStatus.OBSERVED
    )
    assert analysis.propulsion_to_configured_minimum_airspeed is None
    assert "Propulsion to AIRSPEED_MIN" not in format_takeoff_performance_report(
        analysis,
        1,
    )


def test_missing_throttle_evidence_has_no_fabricated_peak_timing():
    """Battery evidence can stand alone without manufacturing throttle timing."""
    flight_log = _flight_log(
        ctun=((TARGET_US, 0.0, 0.0, 0.0, 0.0, 10.0, 1, math.nan),),
        bat=((3_500_000, 0, 25.0),),
        parameter_history=_history({"AIRSPEED_MIN": 10.0}),
    )

    analysis = _analyse(flight_log)

    assert analysis is not None
    response = analysis.propulsion_to_configured_minimum_airspeed
    assert response is not None
    assert response.maximum_throttle_command_pct is None
    assert response.time_to_maximum_throttle_s is None
    assert response.continuous_peak_throttle_duration_s is None
    report = format_takeoff_performance_report(analysis, 1)
    assert any(
        line.strip().startswith("Peak throttle") and line.endswith("Unavailable")
        for line in report.splitlines()
    )
    assert any(
        line.strip().startswith("Throttle ramp to peak")
        and line.endswith("unavailable")
        for line in report.splitlines()
    )
    assert "Peak battery current                   25.0 A" in report


def test_minimum_airspeed_observation_excludes_endpoint_and_labels_not_observed():
    """A qualifying endpoint row is unowned and statuses retain censoring."""
    history = _history({"AIRSPEED_MIN": 10.0})
    rows = (
        (2_500_000, 0.0, 0.0, 0.0, 0.0, 9.0, 1, 0.0),
        (COMPLETION_US, 0.0, 0.0, 0.0, 0.0, 11.0, 1, 0.0),
    )
    completed = _analyse(_flight_log(ctun=rows, parameter_history=history))
    censored = _analyse(
        _flight_log(
            ctun=(
                rows[0],
                (MODE_EXIT_US, 0.0, 0.0, 0.0, 0.0, 11.0, 1, 0.0),
            ),
            parameter_history=history,
        ),
        _execution(completion=False),
    )

    assert completed is not None
    assert completed.first_observed_configured_minimum_airspeed.status is (
        ConfiguredMinimumAirspeedStatus.NOT_OBSERVED_COMPLETED
    )
    assert censored is not None
    assert censored.first_observed_configured_minimum_airspeed.status is (
        ConfiguredMinimumAirspeedStatus.NOT_OBSERVED_CENSORED_MODE_EXIT
    )


def _configuration_history():
    """Return all report-context parameters with one later change."""
    values = {
        spec: float(index)
        for index, spec in enumerate(
            (
                "TKOFF_THR_MINACC",
                "TKOFF_ACCEL_CNT",
                "TKOFF_THR_DELAY",
                "TKOFF_THR_MINSPD",
                "TKOFF_ROTATE_SPD",
                "TKOFF_GND_PITCH",
                "TKOFF_LVL_PITCH",
                "TKOFF_ALT",
                "TKOFF_DIST",
                "TKOFF_LVL_ALT",
                "TKOFF_THR_MAX",
                "TKOFF_THR_MAX_T",
                "TKOFF_THR_SLEW",
                "TKOFF_OPTIONS",
                "THR_MAX",
                "PTCH_TRIM_DEG",
                "KFF_THR2PTCH",
                "PTCH_LIM_MAX_DEG",
                "LEVEL_ROLL_LIMIT",
                "ROLL_LIMIT_DEG",
                "AIRSPEED_MIN",
                "AIRSPEED_CRUISE",
                "ARSPD_USE",
                "ARSPD_PRIMARY",
            ),
            start=1,
        )
    }
    return _history(
        values,
        {"TKOFF_ALT": (ParameterChange(TRIGGER_US + 1, 999.0),)},
    )


def test_configuration_context_uses_trigger_time_and_expected_groups():
    """Later changes do not rewrite the selected launch configuration."""
    analysis = _analyse(_flight_log(parameter_history=_configuration_history()))

    assert analysis is not None
    context = analysis.configuration
    assert context.trigger_time_us == TRIGGER_US
    assert tuple(group.name for group in context.groups) == (
        "Takeoff trigger conditions",
        "Takeoff control",
        "Throttle",
        "Pitch / roll",
        "Airspeed",
    )
    values = {value.name: value for group in context.groups for value in group.values}
    assert len(values) == 24
    assert values["TKOFF_ALT"].value == 8.0
    assert values["TKOFF_ALT"].display_value == 8.0
    assert values["TKOFF_THR_DELAY"].value == 3.0
    throttle_delay = values["TKOFF_THR_DELAY"].display_value
    assert throttle_delay is not None
    assert math.isclose(throttle_delay, 0.3)


def test_configuration_context_keeps_missing_value_unavailable():
    """Missing configuration is explicit and has no snapshot fallback."""
    analysis = _analyse(_flight_log())

    assert analysis is not None
    values = [
        value for group in analysis.configuration.groups for value in group.values
    ]
    assert all(value.value is None for value in values)
    assert "unavailable" in format_takeoff_performance_report(analysis, 1)


def test_takeoff_options_preserve_and_decode_known_and_unknown_bits():
    """Plane 4.7.x bit zero is decoded while every other set bit stays visible."""
    expected = {
        0: "0 — None",
        1: "1 — Allow TECS throttle range",
        8: "8 — unknown bit 3",
        9: "9 — Allow TECS throttle range, unknown bit 3",
    }
    for mask, rendered in expected.items():
        analysis = _analyse(
            _flight_log(parameter_history=_history({"TKOFF_OPTIONS": float(mask)}))
        )
        assert analysis is not None
        report = format_takeoff_performance_report(analysis, 1)
        assert f"TKOFF_OPTIONS                {rendered}" in report


def test_phase_acceleration_gate_uses_owned_message_and_event_time_parameter():
    """Owned Armed AUTO evidence uses the gate value effective at that event."""
    history = _history(
        {"TKOFF_THR_MINACC": 6.0},
        {"TKOFF_THR_MINACC": (ParameterChange(1_900_000, 0.0),)},
    )
    analysis = _analyse(
        _flight_log(parameter_history=history),
        _execution(
            armed_detail="Armed AUTO, xaccel = 7.4 m/s/s, waiting 0.0 sec",
            trigger_detail="Triggered AUTO. GPS speed = 3.1",
        ),
    )

    assert analysis is not None
    phase = analysis.phase_evidence
    assert phase.acceleration_gate_status is AccelerationGateEvidenceStatus.OBSERVED
    assert phase.observed_xaccel_m_s2 == 7.4
    assert analysis.configuration.groups[0].values[0].value == 0.0
    report = format_takeoff_performance_report(analysis, 1)
    assert "Acceleration gate                  Observed" in report
    assert "Observed x-accel                   7.4 m/s²" in report


def test_phase_acceleration_gate_distinguishes_configuration_states():
    """Configured, disabled, and unavailable gates are not called observed."""
    configured = _analyse(
        _flight_log(parameter_history=_history({"TKOFF_THR_MINACC": 6.0}))
    )
    disabled = _analyse(
        _flight_log(parameter_history=_history({"TKOFF_THR_MINACC": 0.0})),
        _execution(armed_detail="Armed AUTO, xaccel = 9.9 m/s/s, waiting 0.0 sec"),
    )
    unavailable = _analyse(_flight_log())

    assert configured is not None
    assert configured.phase_evidence.acceleration_gate_status is (
        AccelerationGateEvidenceStatus.CONFIGURED
    )
    assert disabled is not None
    assert disabled.phase_evidence.acceleration_gate_status is (
        AccelerationGateEvidenceStatus.DISABLED
    )
    assert disabled.phase_evidence.observed_xaccel_m_s2 is None
    assert unavailable is not None
    assert unavailable.phase_evidence.acceleration_gate_status is (
        AccelerationGateEvidenceStatus.UNAVAILABLE
    )
    assert "Acceleration gate                  Configured" in (
        format_takeoff_performance_report(configured, 1)
    )
    disabled_report = format_takeoff_performance_report(disabled, 2)
    assert "Acceleration gate                  Disabled" in disabled_report
    assert "Observed x-accel" not in disabled_report
    assert "Acceleration gate                  Unavailable" in (
        format_takeoff_performance_report(unavailable, 3)
    )


def test_phase_acceleration_gate_does_not_borrow_raw_foreign_message():
    """An MSG row outside the execution event model remains configuration only."""
    analysis = _analyse(
        _flight_log(
            msg=((500_000, "Armed AUTO, xaccel = 8.8 m/s/s, waiting 0.0 sec"),),
            parameter_history=_history({"TKOFF_THR_MINACC": 6.0}),
        )
    )

    assert analysis is not None
    assert analysis.phase_evidence.acceleration_gate_status is (
        AccelerationGateEvidenceStatus.CONFIGURED
    )
    assert analysis.phase_evidence.observed_xaccel_m_s2 is None


def test_phase_trigger_uses_owned_firmware_message_not_raw_gps_or_msg():
    """Trigger GPS speed comes only from the owned Triggered AUTO event text."""
    owned = _analyse(
        _flight_log(gps=((1_900_000, 0, 3, 99.0, 1),)),
        _execution(trigger_detail="Triggered AUTO. GPS speed = 3.1"),
    )
    malformed_owned = _analyse(
        _flight_log(
            msg=((500_000, "Triggered AUTO. GPS speed = 8.8"),),
            gps=((1_900_000, 0, 3, 7.7, 1),),
        ),
        _execution(trigger_detail="Triggered AUTO"),
    )

    assert owned is not None
    assert owned.phase_evidence.trigger_gps_speed_m_s == 3.1
    owned_report = format_takeoff_performance_report(owned, 1)
    assert "Trigger                            Observed" in owned_report
    assert "GPS speed at trigger               3.1 m/s" in owned_report
    assert "99.0 m/s" not in owned_report
    assert malformed_owned is not None
    assert malformed_owned.phase_evidence.trigger_gps_speed_m_s is None
    assert "GPS speed at trigger               Unavailable" in (
        format_takeoff_performance_report(malformed_owned, 2)
    )


def test_phase_reuses_owned_throttle_airspeed_and_completion_evidence():
    """Existing event and metric outcomes drive phase status without new rules."""
    flight_log = _flight_log(
        ctun=((3_500_000, 0.0, 0.0, 0.0, 0.0, 11.0, 1, 0.0),),
        parameter_history=_history({"AIRSPEED_MIN": 11.0}),
    )
    completed = _analyse(flight_log)
    censored = _analyse(flight_log, _execution(completion=False))
    missing_release = _analyse(flight_log, _execution(unsuppressed=False))
    missing_minimum = _analyse(
        _flight_log(parameter_history=_history({"AIRSPEED_MIN": 11.0}))
    )

    assert completed is not None
    assert completed.first_observed_configured_minimum_airspeed.status is (
        ConfiguredMinimumAirspeedStatus.OBSERVED
    )
    completed_report = format_takeoff_performance_report(completed, 1)
    assert "Throttle release                   Observed" in completed_report
    assert "AIRSPEED_MIN                       Observed" in completed_report
    assert "Takeoff completion                 Completed" in completed_report
    assert censored is not None
    assert "Takeoff completion                 Mode exit before completion" in (
        format_takeoff_performance_report(censored, 2)
    )
    assert missing_release is not None
    assert "Throttle release                   Unavailable" in (
        format_takeoff_performance_report(missing_release, 3)
    )
    assert missing_minimum is not None
    assert "AIRSPEED_MIN                       Unavailable" in (
        format_takeoff_performance_report(missing_minimum, 4)
    )


def test_phase_keeps_rotation_unavailable_despite_config_and_sensor_crossing():
    """Rotation is not inferred from TKOFF_ROTATE_SPD or CTUN response."""
    analysis = _analyse(
        _flight_log(
            ctun=(
                (2_500_000, 3.0, 2.0, 0.0, 0.0, 9.0, 1, 0.0),
                (3_500_000, 15.0, 10.0, 0.0, 0.0, 13.0, 1, 0.0),
            ),
            pos=((1_900_000, 0.0), (3_500_000, 5.0)),
            parameter_history=_history(
                {"TKOFF_ROTATE_SPD": 10.0, "AIRSPEED_MIN": 11.0}
            ),
        )
    )

    assert analysis is not None
    report = format_takeoff_performance_report(analysis, 1)
    assert "Rotation complete                  Unavailable" in report
    assert "Rotation complete                  Observed" not in report


def test_phase_section_is_detailed_only_and_does_not_duplicate_configuration():
    """Phase fields stay out of summary and static parameters stay at the bottom."""
    first = _analyse(
        _flight_log(parameter_history=_configuration_history()),
        _execution(
            armed_detail="Armed AUTO, xaccel = 7.4 m/s/s, waiting 0.0 sec",
            trigger_detail="Triggered AUTO. GPS speed = 3.1",
        ),
    )
    second = _analyse(
        _flight_log(parameter_history=_configuration_history()),
        _execution(completion=False),
    )

    assert first is not None
    assert second is not None
    report = format_takeoff_performance_reports((first, second))
    summary = report.split("\n\nTAKEOFF 1", maxsplit=1)[0]
    assert "Takeoff phase evidence" not in summary
    assert "Acceleration gate" not in summary
    assert "Rotation complete" not in summary
    assert report.count("Takeoff phase evidence") == 2
    phase_block = report.split("Takeoff phase evidence", maxsplit=1)[1].split(
        "At trigger", maxsplit=1
    )[0]
    for field in (
        "Acceleration gate",
        "Observed x-accel",
        "Trigger",
        "GPS speed at trigger",
        "Throttle release",
        "AIRSPEED_MIN",
        "Rotation complete",
        "Takeoff completion",
    ):
        assert field in phase_block
    assert "TKOFF_THR_MINACC" not in phase_block
    assert report.count("TKOFF_THR_MINACC") == 1


def test_report_uses_relative_timing_and_preserves_internal_timeus():
    """Normal output is relative while evidence retains exact microseconds."""
    flight_log = _flight_log(
        ctun=(
            (1_900_000, 0.0, 0.0, 0.0, 0.0, 8.0, 1, 0.0),
            (2_500_000, 0.0, 0.0, 0.0, 0.0, 12.0, 1, 0.0),
        ),
        parameter_history=_history({"AIRSPEED_MIN": 11.0}),
    )
    analysis = _analyse(flight_log)

    assert analysis is not None
    report = format_takeoff_performance_report(analysis, 2)
    assert "Firmware trigger" in report
    assert "0.000 s" in report
    assert "Throttle unsuppressed" in report
    assert "+1.000 s" in report
    assert "Airspeed source                    Airspeed sensor" in report
    assert "Takeoff control complete" in report
    assert "TAKEOFF mode exited" in report
    assert "\n  Mode exit" not in report
    assert "Airspeed vs AIRSPEED_MIN           -3.00 m/s" in report
    assert "Delta to AIRSPEED_MIN" not in report
    assert "Trigger → AIRSPEED_MIN" in report
    assert "Airspeed at AIRSPEED_MIN" in report
    assert "First observed ≥ AIRSPEED_MIN" not in report
    assert "Trigger → AIRSPEED_MIN             0.500 s" in report
    assert str(TRIGGER_US) not in report
    assert str(UNSUPPRESSED_US) not in report
    assert analysis.phase_timings.trigger_time_us == TRIGGER_US
    assert (
        analysis.first_observed_configured_minimum_airspeed.observation_time_us
        == 2_500_000
    )


def test_report_labels_synthetic_airspeed_without_calling_it_measured():
    """AsT 2/3 evidence is explicitly presented as a synthetic estimate."""
    flight_log = _flight_log(
        ctun=(
            (1_900_000, 0.0, 0.0, 0.0, 0.0, 8.0, 2, 0.0),
            (2_500_000, 0.0, 0.0, 0.0, 0.0, 12.0, 3, 0.0),
        ),
        parameter_history=_history({"AIRSPEED_MIN": 11.0}),
    )
    analysis = _analyse(flight_log)

    assert analysis is not None
    report = format_takeoff_performance_report(analysis, 1)
    assert analysis.airspeed_estimate_types == (2, 3)
    assert "Airspeed source                    Synthetic estimate" in report
    assert "Airspeed" in report
    assert "Airspeed at AIRSPEED_MIN" in report
    assert "measured airspeed" not in report.lower()


def test_report_labels_mixed_interval_sources_conservatively():
    """A mixed interval is not presented as uniformly sensor-derived."""
    flight_log = _flight_log(
        ctun=(
            (1_900_000, 0.0, 0.0, 0.0, 0.0, 8.0, 1, 0.0),
            (2_500_000, 0.0, 0.0, 0.0, 0.0, 9.0, 2, 0.0),
        ),
        parameter_history=_history({"AIRSPEED_MIN": 11.0}),
    )
    analysis = _analyse(flight_log)

    assert analysis is not None
    assert analysis.airspeed_estimate_types == (1, 2)
    assert "Airspeed source                    Mixed sensor / synthetic estimate" in (
        format_takeoff_performance_report(analysis, 1)
    )


def test_unavailable_airspeed_omits_performance_but_keeps_configuration():
    """Missing usable AsT evidence produces no fabricated performance values."""
    history = _history(
        {
            "AIRSPEED_MIN": 11.0,
            "AIRSPEED_CRUISE": 13.0,
            "ARSPD_USE": 1.0,
            "ARSPD_PRIMARY": 0.0,
        }
    )
    flight_log = _flight_log(
        ctun=(
            (1_900_000, 0.0, 0.0, 0.0, 0.0, 0.0, 0, 0.0),
            (2_500_000, 0.0, 0.0, 0.0, 0.0, 0.0, 0, 0.0),
        ),
        parameter_history=history,
    )
    analysis = _analyse(flight_log)

    assert analysis is not None
    report = format_takeoff_performance_report(analysis, 1)
    assert analysis.airspeed_estimate_types == ()
    assert "Airspeed source                    Unavailable" in report
    assert "AIRSPEED_MIN" in report
    assert "11.0 m/s" in report
    assert "AIRSPEED_CRUISE" in report
    assert "13.0 m/s" in report
    assert "Airspeed build" not in report
    assert "Propulsion to AIRSPEED_MIN" not in report
    assert "Delta to AIRSPEED_MIN" not in report
    assert "First observed ≥ AIRSPEED_MIN" not in report
    assert "Airspeed at observation" not in report
    assert "0.00 m/s" not in report
    assert str(TRIGGER_US) not in report


def test_comparative_report_starts_with_summary_and_consolidates_configuration():
    """Overview counts and three rows precede one shared configuration block."""
    first = _analyse(_flight_log(parameter_history=_configuration_history()))
    second = _analyse(
        _flight_log(parameter_history=_configuration_history()),
        _execution(completion=False),
    )
    third = _analyse(_flight_log(parameter_history=_configuration_history()))

    assert first is not None
    assert second is not None
    assert third is not None
    report = format_takeoff_performance_reports(
        (first, second, third),
        detected_execution_count=5,
    )
    assert report.count("TAKEOFF CONFIGURATION") == 1
    assert "Applies to TAKEOFF 1–3" in report
    assert report.count("TKOFF_THR_MINACC") == 1
    assert "5 TAKEOFF-mode executions detected" in report
    assert "3 triggered takeoffs analysed" in report
    assert "2 non-trigger executions omitted" in report
    summary = report.split("\n\nTAKEOFF 1", maxsplit=1)[0]
    assert "1    Completed" in summary
    assert "2    Mode exit before completion" in summary
    assert "3    Completed" in summary
    assert "Peak current" in summary
    assert "Pitch tracking error" not in summary
    assert "pitch residual" not in report.lower()
    assert report.index("Summary") < report.index("TAKEOFF 1")
    assert report.index("TAKEOFF 1") < report.index("TAKEOFF 2")
    assert report.index("TAKEOFF 2") < report.index("TAKEOFF 3")
    assert report.index("TAKEOFF 3") < report.index("TAKEOFF CONFIGURATION")


def test_comparative_report_does_not_collapse_differing_configuration():
    """Distinct trigger-time parameter values remain execution-scoped."""
    first = _analyse(_flight_log(parameter_history=_history({"TKOFF_ROTATE_SPD": 0.0})))
    second = _analyse(
        _flight_log(parameter_history=_history({"TKOFF_ROTATE_SPD": 12.0}))
    )

    assert first is not None
    assert second is not None
    report = format_takeoff_performance_reports((first, second))
    assert "Applies to TAKEOFF" not in report
    assert report.count(" CONFIGURATION") == 2
    assert "TAKEOFF 1 CONFIGURATION" in report
    assert "TAKEOFF 2 CONFIGURATION" in report
    assert "TKOFF_ROTATE_SPD             0.0 m/s" in report
    assert "TKOFF_ROTATE_SPD             12.0 m/s" in report
    assert report.index("TAKEOFF 2\n") < report.index("TAKEOFF 1 CONFIGURATION")


def test_single_takeoff_report_omits_comparative_table_and_places_config_last():
    """One result retains the overview without pointless comparative clutter."""
    analysis = _analyse(_flight_log(parameter_history=_configuration_history()))

    assert analysis is not None
    report = format_takeoff_performance_reports((analysis,))
    assert "1 TAKEOFF-mode execution detected" in report
    assert "1 triggered takeoff analysed" in report
    assert "0 non-trigger executions omitted" in report
    assert "Summary" not in report
    assert "Trigger → AIRSPEED_MIN" not in report
    assert report.index("TAKEOFF 1\n") < report.index("TAKEOFF CONFIGURATION")
    assert "Applies to TAKEOFF" not in report


def test_summary_uses_dash_for_unavailable_airspeed_without_fabricating_zero():
    """Optional airspeed remains concise and absent in the opening comparison."""
    first = _analyse(_flight_log())
    second = _analyse(_flight_log())

    assert first is not None
    assert second is not None
    report = format_takeoff_performance_reports((first, second))
    summary = report.split("\n\nTAKEOFF 1", maxsplit=1)[0]
    assert "Trigger→Vmin" in summary
    assert "—" in summary
    assert "0.000 s" not in summary
    assert report.count("Airspeed source                    Unavailable") == 2
    assert "Airspeed build" not in report


def test_summary_uses_peak_current_and_dash_when_it_is_unavailable():
    """The comparison uses existing current evidence without fabricating zero."""
    ctun = (
        (UNSUPPRESSED_US, 0.0, 0.0, 0.0, 0.0, 9.0, 1, 20.0),
        (TARGET_US, 0.0, 0.0, 0.0, 0.0, 10.0, 1, 90.0),
    )
    history = _history({"AIRSPEED_MIN": 10.0})
    with_current = _analyse(
        _flight_log(
            ctun=ctun,
            bat=((3_500_000, 0, 25.0),),
            parameter_history=history,
        )
    )
    without_current = _analyse(_flight_log(ctun=ctun, parameter_history=history))

    assert with_current is not None
    assert without_current is not None
    report = format_takeoff_performance_reports((with_current, without_current))
    summary = report.split("\n\nTAKEOFF 1", maxsplit=1)[0]
    assert "Peak current" in summary
    assert "25.0 A" in summary
    assert "—" in summary
    assert "Pitch tracking error" not in summary


def test_report_delta_format_distinguishes_positive_negative_and_zero():
    """Signed deltas retain direction while exact zero has no positive sign."""
    positive_negative = _analyse(
        _flight_log(
            pos=(
                (1_900_000, 10.0),
                (2_500_000, 9.5),
                (COMPLETION_US, 20.0),
            )
        )
    )
    zero = _analyse(
        _flight_log(
            pos=(
                (1_900_000, 10.0),
                (2_500_000, 10.0),
                (COMPLETION_US, 10.0),
            )
        )
    )

    assert positive_negative is not None
    assert zero is not None
    directional_report = format_takeoff_performance_report(positive_negative, 1)
    zero_report = format_takeoff_performance_report(zero, 2)
    assert "Minimum altitude delta             -0.50 m" in directional_report
    assert "Altitude gain at completion        +10.00 m" in directional_report
    assert "Minimum altitude delta             0.00 m" in zero_report
    assert "Altitude gain at completion        0.00 m" in zero_report
    assert "+0.00 m" not in zero_report


def test_rotation_control_wording_is_neutral_and_parameter_based():
    """Rotation gating is described without inferring a takeoff method."""
    ungated = _analyse(
        _flight_log(parameter_history=_history({"TKOFF_ROTATE_SPD": 0.0}))
    )
    gated = _analyse(_flight_log(parameter_history=_history({"TKOFF_ROTATE_SPD": 8.0})))

    assert ungated is not None
    assert gated is not None
    ungated_report = format_takeoff_performance_report(ungated, 1)
    gated_report = format_takeoff_performance_report(gated, 2)
    assert "Rotation control             No speed-gated rotation" in ungated_report
    assert "Rotation control             Speed-gated rotation" in gated_report
    assert "hand launch" not in ungated_report.lower()
    assert "launch method" not in ungated_report.lower()


def test_report_exposes_existing_status_trigger_and_control_evidence():
    """Operational layout exposes existing evidence without new calculations."""
    flight_log = _flight_log(
        ctun=(
            (1_900_000, 6.0, 4.0, 2.0, 1.0, 8.0, 1, 10.0),
            (2_500_000, 20.0, 5.0, 0.0, -7.0, 9.0, 1, 30.0),
            (3_000_000, 15.0, 6.0, 0.0, 5.0, 11.0, 1, 40.0),
            (3_500_000, 12.0, 7.0, 0.0, 3.0, 13.0, 1, 50.0),
            (5_500_000, 10.0, 8.0, 0.0, 2.0, 15.0, 1, 60.0),
        ),
        gps=((1_900_000, 0, 3, 2.5, 1),),
        pos=(
            (1_900_000, 10.0),
            (2_500_000, 9.5),
            (COMPLETION_US, 20.0),
        ),
        tecs=((2_200_000, 0.1),),
        parameter_history=_history(
            {
                "AIRSPEED_MIN": 11.0,
                "KFF_THR2PTCH": 0.0,
                "TKOFF_TDRAG_ELEV": 0.0,
                "TKOFF_TDRAG_SPD1": 0.0,
            }
        ),
    )
    completed = _analyse(flight_log)
    censored = _analyse(flight_log, _execution(completion=False))

    assert completed is not None
    assert censored is not None
    completed_report = format_takeoff_performance_report(completed, 1)
    censored_report = format_takeoff_performance_report(censored, 2)
    assert "Status                               Completed" in completed_report
    assert "Status                               Mode exit before completion" in (
        censored_report
    )
    assert "Groundspeed                        2.50 m/s" in completed_report
    assert "Pitch demand / achieved            6.00° / 4.00°" in completed_report
    assert "Roll demand / achieved             2.00° / 1.00°" in completed_report
    assert "Throttle command                   10.00%" not in completed_report
    assert "Airspeed range                     9.00–15.00 m/s" in completed_report
    airspeed_build = completed_report.split("Airspeed build", maxsplit=1)[1].split(
        "Takeoff control", maxsplit=1
    )[0]
    assert "Airspeed range" not in airspeed_build
    assert completed_report.index("Takeoff control") < completed_report.index(
        "Airspeed range"
    )
    assert completed_report.index("Airspeed range") < completed_report.index(
        "Largest pitch tracking error"
    )
    assert "Largest pitch tracking error       +9.00°" in completed_report
    assert "pitch residual" not in completed_report.lower()
    assert "Maximum absolute roll              7.00°" in completed_report
    assert "Minimum altitude delta             -0.50 m" in completed_report
    assert "Altitude gain at completion        +10.00 m" in completed_report
    assert "Altitude delta at mode exit" in censored_report
    assert "Censored — mode exit" not in censored_report
    assert str(TRIGGER_US) not in completed_report
    assert str(COMPLETION_US) not in completed_report


def test_airspeed_source_is_execution_evidence_not_shared_configuration():
    """Shared configuration does not claim a common observational source."""
    history = _history({"AIRSPEED_MIN": 11.0})
    sensor = _analyse(
        _flight_log(
            ctun=((1_900_000, 0.0, 0.0, 0.0, 0.0, 8.0, 1, 0.0),),
            parameter_history=history,
        )
    )
    synthetic = _analyse(
        _flight_log(
            ctun=((1_900_000, 0.0, 0.0, 0.0, 0.0, 8.0, 2, 0.0),),
            parameter_history=history,
        )
    )

    assert sensor is not None
    assert synthetic is not None
    report = format_takeoff_performance_reports((sensor, synthetic))
    executions, configuration = report.split("\n\nTAKEOFF CONFIGURATION", maxsplit=1)
    assert "Airspeed source" not in configuration
    assert "Airspeed source                    Airspeed sensor" in executions
    assert "Airspeed source                    Synthetic estimate" in executions

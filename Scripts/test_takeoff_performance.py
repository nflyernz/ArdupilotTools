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
    ConfiguredMinimumAirspeedStatus,
    FixedThrottleTargetStatus,
    TakeoffControlIntervalStatus,
    TakeoffPerformanceProcessor,
    format_takeoff_performance_report,
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


def _history(initial_values=None, changes=None):
    """Build timestamped parameter state without synthetic PARM startup noise."""
    return ParameterHistory(initial_values or {}, changes or {})


def _flight_log(
    *,
    ctun=(),
    gps=(),
    pos=(),
    baro=(),
    tecs=(),
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
            "GPS": _table(gps, ("TimeUS", "I", "Status", "Spd", "U")),
            "POS": _table(pos, ("TimeUS", "RelHomeAlt")),
            "BARO": _table(baro, ("TimeUS", "Alt")),
            "TECS": _table(tecs, ("TimeUS", "ph")),
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
        "Launch detection",
        "Takeoff",
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
    assert "Firmware trigger                     0.000 s" in report
    assert "Throttle unsuppressed                +1.000 s" in report
    assert "First observed ≥ configured minimum +0.500 s" in report
    assert str(TRIGGER_US) not in report
    assert str(UNSUPPRESSED_US) not in report
    assert analysis.phase_timings.trigger_time_us == TRIGGER_US
    assert (
        analysis.first_observed_configured_minimum_airspeed.observation_time_us
        == 2_500_000
    )

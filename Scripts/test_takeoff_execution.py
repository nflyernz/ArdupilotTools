"""Focused synthetic tests for AUTO takeoff execution ownership."""

import pandas as pd
import pytest
from core.flight_data import FlightLog
from core.takeoff_execution import (
    TakeoffEntryContext,
    TakeoffExecutionEvent,
    TakeoffExecutionEventType,
    TakeoffTerminationReason,
)
from core.takeoff_execution_detector import TakeoffExecutionDetector

AUTO_MODE = 10
TAKEOFF_MODE = 13
FBWA_MODE = 5
MANUAL_MODE = 0
NAV_TAKEOFF = 22
NAV_WAYPOINT = 16

START_US = 1_000_000
LOG_END_US = 9_000_000


def _table(rows, columns):
    """Build a compact synthetic message table with stable row order."""
    return pd.DataFrame(rows, columns=columns)


def _flight_log(
    *,
    mise=((START_US, 1, NAV_TAKEOFF),),
    mode=((900_000, AUTO_MODE),),
    msg=(),
    arm=(),
    cmd=(),
    stat=(),
    log_end_us=LOG_END_US,
):
    """Build only the message evidence consumed by the detector."""
    messages = {
        "MISE": _table(mise, ("TimeUS", "CNum", "CId")),
        "MODE": _table(mode, ("TimeUS", "ModeNum")),
        "MSG": _table(msg, ("TimeUS", "Message")),
        "ARM": _table(arm, ("TimeUS", "ArmState")),
        "CMD": _table(cmd, ("TimeUS", "CNum", "CId")),
        "STAT": _table(stat, ("TimeUS", "Stage", "Sup")),
    }
    if log_end_us is not None:
        messages["GPS"] = _table(((log_end_us,),), ("TimeUS",))
    return FlightLog(messages=messages)


def _detect(**evidence):
    """Detect executions from compact synthetic evidence."""
    return TakeoffExecutionDetector().detect(_flight_log(**evidence))


def test_prior_auto_and_runtime_mise_start_execution():
    """Strictly earlier AUTO plus runtime MISE establishes ownership."""
    executions = _detect()

    assert len(executions) == 1
    execution = executions[0]
    assert execution.start_us == START_US
    assert execution.mission_item_number == 1
    assert execution.command_id == NAV_TAKEOFF


def test_mise_without_prior_auto_does_not_start_execution():
    """Runtime mission evidence alone does not establish AUTO ownership."""
    assert _detect(mode=()) == []


def test_same_time_auto_alone_does_not_establish_start_order():
    """Equal-time MODE and MISE records have no cross-stream order."""
    assert _detect(mode=((START_US, AUTO_MODE),)) == []


def test_prior_auto_survives_confirming_same_time_auto_evidence():
    """Same-time AUTO does not invalidate ownership established earlier."""
    executions = _detect(
        mode=((900_000, AUTO_MODE), (START_US, AUTO_MODE)),
    )

    assert len(executions) == 1
    assert executions[0].start_us == START_US


def test_prior_auto_with_same_time_mode_exit_has_ambiguous_ownership():
    """Contradictory same-time MODE evidence prevents a takeoff start."""
    assert (
        _detect(
            mode=((900_000, AUTO_MODE), (START_US, MANUAL_MODE)),
        )
        == []
    )


def test_prior_auto_with_unusable_same_time_mode_rejects_start():
    """The production contract treats malformed same-time MODE as ambiguous."""
    assert (
        _detect(
            mode=((900_000, AUTO_MODE), (START_US, float("nan"))),
        )
        == []
    )


def test_stored_mission_definition_does_not_replace_runtime_mise():
    """A stored CMD NAV_TAKEOFF is configuration, not execution evidence."""
    assert (
        _detect(
            mise=(),
            cmd=((500_000, 1, NAV_TAKEOFF),),
        )
        == []
    )


def test_pretrigger_retries_and_trigger_belong_to_one_execution():
    """Launch-check retries remain observations within one command execution."""
    executions = _detect(
        msg=(
            (2_000_000, "Armed AUTO, xaccel = 6.0 m/s/s, waiting 0.0 sec"),
            (3_000_000, "Timeout AUTO"),
            (4_000_000, "Bad launch AUTO"),
            (5_000_000, "Triggered AUTO. GPS speed = 2.0"),
        ),
    )

    assert len(executions) == 1
    execution = executions[0]
    assert [event.event_type for event in execution.pretrigger_events] == [
        TakeoffExecutionEventType.ARMED_AUTO,
        TakeoffExecutionEventType.PRETRIGGER_TIMEOUT,
        TakeoffExecutionEventType.BAD_LAUNCH,
    ]
    assert execution.launch_trigger is not None
    assert execution.launch_trigger.time_us == 5_000_000


def test_completion_closes_execution_and_excludes_future_evidence():
    """Evidence after firmware completion cannot enter the execution."""
    execution = _detect(
        msg=(
            (2_000_000, "Triggered AUTO. GPS speed = 2.0"),
            (6_000_000, "Takeoff complete at 20m"),
            (7_000_000, "Bad launch AUTO"),
        ),
    )[0]

    assert execution.end_us == 6_000_000
    assert execution.termination_reason is TakeoffTerminationReason.COMPLETED
    assert execution.completion is not None
    assert execution.completion.time_us == 6_000_000
    assert [event.time_us for event in execution.events] == [
        2_000_000,
        6_000_000,
    ]


def test_first_mode_exit_is_hard_boundary_and_reentry_does_not_reopen():
    """Later AUTO state cannot reopen an execution closed by mode exit."""
    execution = _detect(
        mode=(
            (900_000, AUTO_MODE),
            (5_000_000, MANUAL_MODE),
            (6_000_000, AUTO_MODE),
            (8_000_000, MANUAL_MODE),
        ),
        msg=(
            (4_000_000, "Triggered AUTO. GPS speed = 2.0"),
            (7_000_000, "Takeoff complete at 20m"),
        ),
    )[0]

    assert execution.end_us == 5_000_000
    assert execution.termination_reason is TakeoffTerminationReason.MODE_EXIT
    assert execution.launch_trigger is not None
    assert execution.completion is None
    assert [event.time_us for event in execution.events] == [4_000_000]


def test_takeoff_timeout_closes_execution_and_retains_timeout_event():
    """Post-trigger takeoff timeout is an explicit firmware termination."""
    execution = _detect(
        msg=(
            (2_000_000, "Triggered AUTO. GPS speed = 2.0"),
            (5_000_000, "Takeoff timeout. Ground speed below 4m/s"),
            (6_000_000, "Takeoff complete at 20m"),
        ),
    )[0]

    assert execution.end_us == 5_000_000
    assert execution.termination_reason is TakeoffTerminationReason.TAKEOFF_TIMEOUT
    assert [event.event_type for event in execution.events] == [
        TakeoffExecutionEventType.TRIGGERED_AUTO,
        TakeoffExecutionEventType.TAKEOFF_TIMEOUT,
    ]
    assert execution.completion is None


def test_disarm_before_completion_terminates_execution():
    """An observed disarm ends ownership when no specific cause precedes it."""
    execution = _detect(
        msg=(
            (2_000_000, "Triggered AUTO. GPS speed = 2.0"),
            (7_000_000, "Takeoff complete at 20m"),
        ),
        arm=((5_000_000, 0),),
    )[0]

    assert execution.end_us == 5_000_000
    assert execution.termination_reason is TakeoffTerminationReason.DISARM
    assert execution.completion is None


def test_next_navigation_mise_ends_takeoff_ownership():
    """Runtime execution of another NAV command advances mission ownership."""
    execution = _detect(
        mise=(
            (START_US, 1, NAV_TAKEOFF),
            (5_000_000, 2, NAV_WAYPOINT),
        ),
        msg=((4_000_000, "Triggered AUTO. GPS speed = 2.0"),),
    )[0]

    assert execution.end_us == 5_000_000
    assert execution.termination_reason is TakeoffTerminationReason.MISSION_ADVANCE
    assert execution.launch_trigger is not None


def test_repeated_nav_takeoff_creates_separate_execution_ownership():
    """A later runtime NAV_TAKEOFF starts a new, isolated execution."""
    executions = _detect(
        mise=(
            (START_US, 1, NAV_TAKEOFF),
            (5_000_000, 1, NAV_TAKEOFF),
        ),
        msg=(
            (2_000_000, "Triggered AUTO. GPS speed = 2.0"),
            (6_000_000, "Triggered AUTO. GPS speed = 2.2"),
            (8_000_000, "Takeoff complete at 20m"),
        ),
    )

    assert len(executions) == 2
    first, second = executions
    assert first.end_us == 5_000_000
    assert first.termination_reason is TakeoffTerminationReason.COMMAND_RESTART
    assert [event.time_us for event in first.events] == [2_000_000]
    assert second.start_us == 5_000_000
    assert second.end_us == 8_000_000
    assert second.termination_reason is TakeoffTerminationReason.COMPLETED
    assert [event.time_us for event in second.events] == [
        6_000_000,
        8_000_000,
    ]


def test_same_time_completion_causally_precedes_mission_advance():
    """Firmware completion explains an equal-time next NAV execution."""
    execution = _detect(
        mise=(
            (START_US, 1, NAV_TAKEOFF),
            (5_000_000, 2, NAV_WAYPOINT),
        ),
        msg=((5_000_000, "Takeoff complete at 20m"),),
    )[0]

    assert execution.end_us == 5_000_000
    assert execution.termination_reason is TakeoffTerminationReason.COMPLETED
    assert execution.completion is not None


def test_same_time_takeoff_timeout_causally_precedes_associated_disarm():
    """Firmware timeout explains its equal-time disarm observation."""
    execution = _detect(
        msg=((5_000_000, "Takeoff timeout. Ground speed below 4m/s"),),
        arm=((5_000_000, 0),),
    )[0]

    assert execution.end_us == 5_000_000
    assert execution.termination_reason is TakeoffTerminationReason.TAKEOFF_TIMEOUT
    assert execution.events[-1].event_type is (
        TakeoffExecutionEventType.TAKEOFF_TIMEOUT
    )


def test_same_time_completion_and_mode_exit_have_ambiguous_cause():
    """No cross-stream ordering is invented for completion versus mode exit."""
    execution = _detect(
        mode=((900_000, AUTO_MODE), (5_000_000, MANUAL_MODE)),
        msg=((5_000_000, "Takeoff complete at 20m"),),
    )[0]

    assert execution.end_us == 5_000_000
    assert execution.termination_reason is TakeoffTerminationReason.AMBIGUOUS
    assert execution.completion is None


def test_same_time_mode_exit_and_disarm_have_ambiguous_cause():
    """No cross-stream ordering is invented for mode exit versus disarm."""
    execution = _detect(
        mode=((900_000, AUTO_MODE), (5_000_000, MANUAL_MODE)),
        arm=((5_000_000, 0),),
    )[0]

    assert execution.end_us == 5_000_000
    assert execution.termination_reason is TakeoffTerminationReason.AMBIGUOUS


def test_log_end_is_exact_and_includes_messages_at_final_timestamp():
    """The final retained timestamp is owned without manufacturing an EOF."""
    execution = _detect(
        msg=(
            (2_000_000, "Armed AUTO, xaccel = 6.0 m/s/s, waiting 0.0 sec"),
            (5_000_000, "Triggered AUTO. GPS speed = 2.0"),
        ),
        log_end_us=None,
    )[0]

    assert execution.end_us == 5_000_000
    assert execution.termination_reason is TakeoffTerminationReason.LOG_END
    assert [event.time_us for event in execution.events] == [
        2_000_000,
        5_000_000,
    ]
    assert execution.launch_trigger is not None
    assert execution.launch_trigger.time_us == execution.end_us


def test_post_disarm_completion_cannot_rewrite_finalized_execution():
    """Future completion evidence cannot supersede an owned disarm boundary."""
    execution = _detect(
        msg=(
            (3_000_000, "Triggered AUTO. GPS speed = 2.0"),
            (8_000_000, "Takeoff complete at 20m"),
        ),
        arm=((5_000_000, 0),),
    )[0]

    assert execution.end_us == 5_000_000
    assert execution.termination_reason is TakeoffTerminationReason.DISARM
    assert execution.completion is None
    assert [event.time_us for event in execution.events] == [3_000_000]


def test_equal_time_different_events_remain_distinct_without_ordering():
    """Event identity is not reduced to TimeUS and implies no type order."""
    armed = TakeoffExecutionEvent(
        2_000_000,
        TakeoffExecutionEventType.ARMED_AUTO,
        "Armed AUTO",
    )
    triggered = TakeoffExecutionEvent(
        2_000_000,
        TakeoffExecutionEventType.TRIGGERED_AUTO,
        "Triggered AUTO",
    )

    assert armed != triggered
    assert len({armed, triggered}) == 2
    with pytest.raises(TypeError):
        _ = armed < triggered


def test_unusable_mise_fields_do_not_create_execution_starts():
    """Malformed runtime command identity or time remains unavailable."""
    assert (
        _detect(
            mise=(
                (float("nan"), 1, NAV_TAKEOFF),
                (2_000_000, 1, 22.5),
                (3_000_000, 1.5, NAV_TAKEOFF),
            ),
        )
        == []
    )


def test_takeoff_mode_outer_ownership_and_reentry():
    """Mode 13 owns one window per entry and ignores duplicate observations."""
    executions = _detect(
        mise=(),
        mode=(
            (1_000_000, TAKEOFF_MODE),
            (1_500_000, TAKEOFF_MODE),
            (4_000_000, FBWA_MODE),
            (6_000_000, TAKEOFF_MODE),
            (8_000_000, MANUAL_MODE),
        ),
    )

    assert len(executions) == 2
    first, second = executions
    assert first.entry_context is TakeoffEntryContext.TAKEOFF_MODE
    assert (first.start_us, first.end_us) == (1_000_000, 4_000_000)
    assert first.termination_reason is TakeoffTerminationReason.MODE_EXIT
    assert second.entry_context is TakeoffEntryContext.TAKEOFF_MODE
    assert (second.start_us, second.end_us) == (6_000_000, 8_000_000)
    assert second.termination_reason is TakeoffTerminationReason.MODE_EXIT


def test_takeoff_mode_log_end_censors_open_execution():
    """A Mode-13 execution still active at log end remains censored."""
    execution = _detect(
        mise=(),
        mode=((1_000_000, TAKEOFF_MODE),),
        log_end_us=5_000_000,
    )[0]

    assert execution.start_us == 1_000_000
    assert execution.end_us == 5_000_000
    assert execution.termination_reason is TakeoffTerminationReason.LOG_END


def test_takeoff_mode_exit_excludes_later_messages():
    """Messages after Mode-13 exit cannot leak into its finalized window."""
    execution = _detect(
        mise=(),
        mode=((1_000_000, TAKEOFF_MODE), (5_000_000, FBWA_MODE)),
        msg=(
            (2_000_000, "Triggered AUTO. GPS speed = 2.0"),
            (6_000_000, "Bad launch AUTO"),
            (7_000_000, "Takeoff to 40m for 200m heading 90 deg"),
        ),
    )[0]

    assert [event.time_us for event in execution.events] == [2_000_000]


def test_takeoff_mode_owns_shared_launch_messages():
    """Shared AUTO launch-check messages remain Mode-13 observations."""
    execution = _detect(
        mise=(),
        mode=((1_000_000, TAKEOFF_MODE), (8_000_000, FBWA_MODE)),
        msg=(
            (2_000_000, "Armed AUTO, xaccel = 6.0 m/s/s, waiting 0.0 sec"),
            (3_000_000, "Timeout AUTO"),
            (4_000_000, "Bad launch AUTO"),
            (5_000_000, "Triggered AUTO. GPS speed = 2.0"),
        ),
    )[0]

    assert execution.entry_context is TakeoffEntryContext.TAKEOFF_MODE
    assert [event.event_type for event in execution.pretrigger_events] == [
        TakeoffExecutionEventType.ARMED_AUTO,
        TakeoffExecutionEventType.PRETRIGGER_TIMEOUT,
        TakeoffExecutionEventType.BAD_LAUNCH,
    ]
    assert execution.launch_trigger is not None
    assert execution.launch_trigger.time_us == 5_000_000


def test_takeoff_to_is_target_course_observation_only():
    """The full firmware target detail is evidence, not a boundary or trigger."""
    detail = "Takeoff to 40m for 200m heading 90 deg"
    execution = _detect(
        mise=(),
        mode=((1_000_000, TAKEOFF_MODE), (6_000_000, FBWA_MODE)),
        msg=((3_000_000, detail),),
    )[0]

    target = execution.target_course_finalization
    assert target is not None
    assert target.event_type is TakeoffExecutionEventType.TARGET_COURSE_FINALIZED
    assert target.time_us == 3_000_000
    assert target.detail == detail
    assert execution.launch_trigger is None
    assert execution.takeoff_control_completion is None
    assert execution.end_us == 6_000_000
    assert execution.termination_reason is TakeoffTerminationReason.MODE_EXIT


def test_takeoff_control_completion_is_inner_observation():
    """Confirmed TAKEOFF-to-NORMAL does not close outer Mode-13 ownership."""
    execution = _detect(
        mise=(),
        mode=((1_000_000, TAKEOFF_MODE), (7_000_000, FBWA_MODE)),
        stat=(
            (2_000_000, 1, 0),
            (4_000_000, 3, 0),
            (4_100_000, 3, 0),
        ),
        msg=((6_000_000, "Bad launch AUTO"),),
    )[0]

    completion = execution.takeoff_control_completion
    assert completion is not None
    assert completion.time_us == 4_000_000
    assert execution.end_us == 7_000_000
    assert execution.termination_reason is TakeoffTerminationReason.MODE_EXIT
    assert any(event.time_us == 6_000_000 for event in execution.events)


def test_mode_exit_generated_normal_does_not_manufacture_completion():
    """One pre-exit NORMAL can be the new mode's synchronous stage write."""
    execution = _detect(
        mise=(),
        mode=((1_000_000, TAKEOFF_MODE), (5_000_000, FBWA_MODE)),
        stat=(
            (2_000_000, 1, 0),
            (4_900_000, 3, 0),
        ),
    )[0]

    assert execution.takeoff_control_completion is None


def test_second_pre_exit_normal_confirms_first_completion_candidate():
    """A second owned NORMAL retains the first candidate's timestamp."""
    execution = _detect(
        mise=(),
        mode=((1_000_000, TAKEOFF_MODE), (5_000_000, FBWA_MODE)),
        stat=(
            (2_000_000, 1, 0),
            (4_000_000, 3, 0),
            (4_100_000, 3, 0),
        ),
    )[0]

    completion = execution.takeoff_control_completion
    assert completion is not None
    assert completion.time_us == 4_000_000


def test_equal_time_normal_and_mode_exit_remain_unowned():
    """Equal-time STAT cannot be ordered before the Mode-13 exit boundary."""
    execution = _detect(
        mise=(),
        mode=((1_000_000, TAKEOFF_MODE), (5_000_000, FBWA_MODE)),
        stat=(
            (2_000_000, 1, 0),
            (4_900_000, 3, 0),
            (5_000_000, 3, 0),
        ),
    )[0]

    assert execution.takeoff_control_completion is None


def test_inner_completion_requires_launch_response_evidence():
    """A bare stage change without trigger or unsuppression is insufficient."""
    execution = _detect(
        mise=(),
        mode=((1_000_000, TAKEOFF_MODE), (6_000_000, FBWA_MODE)),
        stat=(
            (2_000_000, 1, 1),
            (4_000_000, 3, 1),
            (4_100_000, 3, 1),
        ),
    )[0]

    assert execution.throttle_unsuppressed is None
    assert execution.takeoff_control_completion is None


def test_trigger_qualifies_later_takeoff_control_completion():
    """An earlier launch-check trigger establishes a defensible response."""
    execution = _detect(
        mise=(),
        mode=((1_000_000, TAKEOFF_MODE), (6_000_000, FBWA_MODE)),
        msg=((1_500_000, "Triggered AUTO. GPS speed = 2.0"),),
        stat=(
            (2_000_000, 1, 1),
            (4_000_000, 3, 1),
            (4_100_000, 3, 1),
        ),
    )[0]

    assert execution.throttle_unsuppressed is None
    assert execution.takeoff_control_completion is not None
    assert execution.takeoff_control_completion.time_us == 4_000_000


def test_already_flying_mode_entry_exists_without_launch_messages():
    """Mode 13 itself establishes outer ownership without launch messages."""
    execution = _detect(
        mise=(),
        mode=((1_000_000, TAKEOFF_MODE), (6_000_000, FBWA_MODE)),
    )[0]

    assert execution.entry_context is TakeoffEntryContext.TAKEOFF_MODE
    assert execution.launch_trigger is None
    assert execution.takeoff_control_completion is None


def test_already_flying_unsuppressed_stage_transition_can_complete_control():
    """STAT.Sup=0 can qualify an observed transition without launch messages."""
    execution = _detect(
        mise=(),
        mode=((1_000_000, TAKEOFF_MODE), (6_000_000, FBWA_MODE)),
        stat=(
            (2_000_000, 1, 0),
            (4_000_000, 3, 0),
            (4_100_000, 3, 0),
        ),
    )[0]

    assert execution.launch_trigger is None
    assert execution.throttle_unsuppressed is None
    assert execution.takeoff_control_completion is not None
    assert execution.takeoff_control_completion.time_us == 4_000_000


def test_takeoff_mode_and_auto_mission_contexts_remain_distinct():
    """Adjacent execution contexts retain only their own observations."""
    executions = _detect(
        mise=((6_000_000, 1, NAV_TAKEOFF),),
        mode=(
            (1_000_000, TAKEOFF_MODE),
            (5_000_000, AUTO_MODE),
        ),
        msg=(
            (2_000_000, "Triggered AUTO. GPS speed = 2.0"),
            (3_000_000, "Takeoff to 40m for 200m heading 90 deg"),
            (7_000_000, "Triggered AUTO. GPS speed = 2.2"),
            (8_000_000, "Takeoff complete at 40m"),
        ),
    )

    assert len(executions) == 2
    mode_execution, auto_execution = executions
    assert mode_execution.entry_context is TakeoffEntryContext.TAKEOFF_MODE
    assert [event.time_us for event in mode_execution.events] == [
        2_000_000,
        3_000_000,
    ]
    assert mode_execution.target_course_finalization is not None
    assert auto_execution.entry_context is TakeoffEntryContext.AUTO_MISSION
    assert [event.time_us for event in auto_execution.events] == [
        7_000_000,
        8_000_000,
    ]
    assert auto_execution.target_course_finalization is None
    assert auto_execution.completion is not None


def test_trigger_qualifies_first_later_unsuppressed_observation():
    """Launch-check success directly qualifies the next owned Sup=0 sample."""
    execution = _detect(
        mise=(),
        mode=((1_000_000, TAKEOFF_MODE), (6_000_000, FBWA_MODE)),
        msg=((3_000_000, "Triggered AUTO. GPS speed = 2.0"),),
        stat=(
            (2_000_000, 1, 1),
            (4_000_000, 1, 0),
        ),
    )[0]

    assert execution.throttle_unsuppressed is not None
    assert execution.throttle_unsuppressed.time_us == 4_000_000


def test_lone_pre_exit_unsuppressed_candidate_is_not_owned():
    """A mode-exit-generated Sup=0 sample cannot leak into Mode 13."""
    execution = _detect(
        mise=(),
        mode=((1_000_000, TAKEOFF_MODE), (5_000_000, MANUAL_MODE)),
        stat=(
            (2_000_000, 1, 1),
            (4_999_982, 3, 0),
        ),
    )[0]

    assert execution.throttle_unsuppressed is None
    assert execution.takeoff_control_completion is None


def test_second_owned_unsuppressed_sample_confirms_first_candidate():
    """No-trigger persistence retains the first Sup=0 candidate timestamp."""
    execution = _detect(
        mise=(),
        mode=((1_000_000, TAKEOFF_MODE), (6_000_000, FBWA_MODE)),
        stat=(
            (2_000_000, 1, 1),
            (4_000_000, 1, 0),
            (4_100_000, 1, 0),
        ),
    )[0]

    assert execution.throttle_unsuppressed is not None
    assert execution.throttle_unsuppressed.time_us == 4_000_000


def test_equal_time_unsuppressed_and_mode_exit_is_not_owned():
    """Equal-time STAT cannot be ordered before the Mode-13 exit boundary."""
    execution = _detect(
        mise=(),
        mode=((1_000_000, TAKEOFF_MODE), (5_000_000, FBWA_MODE)),
        stat=(
            (2_000_000, 1, 1),
            (4_900_000, 1, 0),
            (5_000_000, 1, 0),
        ),
    )[0]

    assert execution.throttle_unsuppressed is None


def test_already_unsuppressed_entry_does_not_fabricate_transition():
    """Continuous Sup=0 across entry is state, not a Mode-13 transition."""
    execution = _detect(
        mise=(),
        mode=((1_000_000, TAKEOFF_MODE), (6_000_000, FBWA_MODE)),
        stat=(
            (900_000, 3, 0),
            (2_000_000, 3, 0),
            (2_100_000, 3, 0),
        ),
    )[0]

    assert execution.throttle_unsuppressed is None


def test_unconfirmed_unsuppressed_candidate_at_log_end_is_unavailable():
    """Inclusive log end does not confirm a lone no-trigger candidate."""
    execution = _detect(
        mise=(),
        mode=((1_000_000, TAKEOFF_MODE),),
        stat=(
            (2_000_000, 1, 1),
            (5_000_000, 1, 0),
        ),
        log_end_us=None,
    )[0]

    assert execution.end_us == 5_000_000
    assert execution.termination_reason is TakeoffTerminationReason.LOG_END
    assert execution.throttle_unsuppressed is None


def test_triggered_unsuppressed_observation_at_log_end_is_retained():
    """An earlier trigger qualifies the final inclusive Sup=0 observation."""
    execution = _detect(
        mise=(),
        mode=((1_000_000, TAKEOFF_MODE),),
        msg=((3_000_000, "Triggered AUTO. GPS speed = 2.0"),),
        stat=(
            (2_000_000, 1, 1),
            (5_000_000, 1, 0),
        ),
        log_end_us=None,
    )[0]

    assert execution.end_us == 5_000_000
    assert execution.termination_reason is TakeoffTerminationReason.LOG_END
    assert execution.throttle_unsuppressed is not None
    assert execution.throttle_unsuppressed.time_us == 5_000_000

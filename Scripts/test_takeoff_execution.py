"""Focused synthetic tests for AUTO takeoff execution ownership."""

import pandas as pd
import pytest
from core.flight_data import FlightLog
from core.takeoff_execution import (
    TakeoffExecutionEvent,
    TakeoffExecutionEventType,
    TakeoffTerminationReason,
)
from core.takeoff_execution_detector import TakeoffExecutionDetector

AUTO_MODE = 10
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
    log_end_us=LOG_END_US,
):
    """Build only the message evidence consumed by the detector."""
    messages = {
        "MISE": _table(mise, ("TimeUS", "CNum", "CId")),
        "MODE": _table(mode, ("TimeUS", "ModeNum")),
        "MSG": _table(msg, ("TimeUS", "Message")),
        "ARM": _table(arm, ("TimeUS", "ArmState")),
        "CMD": _table(cmd, ("TimeUS", "CNum", "CId")),
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

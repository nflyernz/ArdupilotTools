"""Firmware-owned ArduPlane takeoff execution models."""

from dataclasses import dataclass
from enum import Enum


class TakeoffEntryContext(Enum):
    """Firmware context that owns one takeoff execution."""

    TAKEOFF_MODE = "takeoff_mode"
    AUTO_MISSION = "auto_mission"


class TakeoffExecutionEventType(Enum):
    """Logged firmware observations owned by a takeoff execution."""

    ARMED_AUTO = "armed_auto"
    PRETRIGGER_TIMEOUT = "pretrigger_timeout"
    BAD_LAUNCH = "bad_launch"
    TRIGGERED_AUTO = "triggered_auto"
    TARGET_COURSE_FINALIZED = "target_course_finalized"
    THROTTLE_UNSUPPRESSED = "throttle_unsuppressed"
    TAKEOFF_CONTROL_COMPLETED = "takeoff_control_completed"
    TAKEOFF_TIMEOUT = "takeoff_timeout"
    TAKEOFF_COMPLETE = "takeoff_complete"


class TakeoffTerminationReason(Enum):
    """Authoritative reasons a takeoff execution ended."""

    COMPLETED = "completed"
    MODE_EXIT = "mode_exit"
    TAKEOFF_TIMEOUT = "takeoff_timeout"
    DISARM = "disarm"
    MISSION_ADVANCE = "mission_advance"
    COMMAND_RESTART = "command_restart"
    AMBIGUOUS = "ambiguous"
    LOG_END = "log_end"


@dataclass(frozen=True, slots=True)
class TakeoffExecutionEvent:
    """One logged firmware observation or observed state boundary."""

    time_us: int
    event_type: TakeoffExecutionEventType
    detail: str = ""


@dataclass(frozen=True, slots=True)
class TakeoffExecution:
    """One immutable firmware-owned Plane takeoff execution."""

    start_us: int
    end_us: int
    mission_item_number: int | None
    command_id: int | None
    termination_reason: TakeoffTerminationReason
    events: tuple[TakeoffExecutionEvent, ...] = ()
    entry_context: TakeoffEntryContext = TakeoffEntryContext.AUTO_MISSION

    @property
    def launch_trigger(self) -> TakeoffExecutionEvent | None:
        """Return the observed firmware launch trigger, when logged."""
        return self._first_event(TakeoffExecutionEventType.TRIGGERED_AUTO)

    @property
    def completion(self) -> TakeoffExecutionEvent | None:
        """Return AUTO mission completion, when directly logged."""
        if self.entry_context is not TakeoffEntryContext.AUTO_MISSION:
            return None
        return self._first_event(TakeoffExecutionEventType.TAKEOFF_COMPLETE)

    @property
    def target_course_finalization(self) -> TakeoffExecutionEvent | None:
        """Return the observed TAKEOFF-mode target/course finalization."""
        return self._first_event(TakeoffExecutionEventType.TARGET_COURSE_FINALIZED)

    @property
    def throttle_unsuppressed(self) -> TakeoffExecutionEvent | None:
        """Return the first retained STAT observation with suppression off."""
        return self._first_event(TakeoffExecutionEventType.THROTTLE_UNSUPPRESSED)

    @property
    def takeoff_control_completion(self) -> TakeoffExecutionEvent | None:
        """Return observed TAKEOFF-stage completion inside Mode 13."""
        return self._first_event(TakeoffExecutionEventType.TAKEOFF_CONTROL_COMPLETED)

    @property
    def pretrigger_events(self) -> tuple[TakeoffExecutionEvent, ...]:
        """Return observed launch-check arm/retry events."""
        event_types = {
            TakeoffExecutionEventType.ARMED_AUTO,
            TakeoffExecutionEventType.PRETRIGGER_TIMEOUT,
            TakeoffExecutionEventType.BAD_LAUNCH,
        }
        return tuple(event for event in self.events if event.event_type in event_types)

    def _first_event(
        self,
        event_type: TakeoffExecutionEventType,
    ) -> TakeoffExecutionEvent | None:
        return next(
            (event for event in self.events if event.event_type is event_type),
            None,
        )

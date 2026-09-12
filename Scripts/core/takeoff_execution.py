"""Firmware-owned AUTO takeoff execution models."""

from dataclasses import dataclass
from enum import Enum


class TakeoffExecutionEventType(Enum):
    """Directly observed events owned by an AUTO takeoff execution."""

    ARMED_AUTO = "armed_auto"
    PRETRIGGER_TIMEOUT = "pretrigger_timeout"
    BAD_LAUNCH = "bad_launch"
    TRIGGERED_AUTO = "triggered_auto"
    TAKEOFF_TIMEOUT = "takeoff_timeout"
    TAKEOFF_COMPLETE = "takeoff_complete"


class TakeoffTerminationReason(Enum):
    """Authoritative reasons an AUTO takeoff execution ended."""

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
    """One directly logged firmware observation."""

    time_us: int
    event_type: TakeoffExecutionEventType
    detail: str = ""


@dataclass(frozen=True, slots=True)
class TakeoffExecution:
    """One immutable firmware-owned AUTO ``NAV_TAKEOFF`` execution."""

    start_us: int
    end_us: int
    mission_item_number: int
    command_id: int
    termination_reason: TakeoffTerminationReason
    events: tuple[TakeoffExecutionEvent, ...] = ()

    @property
    def launch_trigger(self) -> TakeoffExecutionEvent | None:
        """Return the observed firmware launch trigger, when logged."""
        return self._first_event(TakeoffExecutionEventType.TRIGGERED_AUTO)

    @property
    def completion(self) -> TakeoffExecutionEvent | None:
        """Return the observed firmware completion, when logged."""
        return self._first_event(TakeoffExecutionEventType.TAKEOFF_COMPLETE)

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

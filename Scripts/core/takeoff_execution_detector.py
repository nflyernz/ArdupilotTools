"""Detect firmware-owned ArduPlane AUTO takeoff executions."""

import math
from dataclasses import dataclass
from numbers import Integral, Real
from typing import ClassVar

from pymavlink import mavutil

from .flight_data import FlightLog
from .takeoff_execution import (
    TakeoffExecution,
    TakeoffExecutionEvent,
    TakeoffExecutionEventType,
    TakeoffTerminationReason,
)


@dataclass(frozen=True, slots=True)
class _CommandStart:
    """Usable runtime ``MISE`` evidence for one takeoff command start."""

    time_us: int
    mission_item_number: int


@dataclass(frozen=True, slots=True)
class _Termination:
    """One candidate execution termination."""

    time_us: int
    reason: TakeoffTerminationReason
    event: TakeoffExecutionEvent | None = None


class TakeoffExecutionDetector:
    """Identify AUTO ``NAV_TAKEOFF`` ownership from logged firmware events."""

    AUTO_MODE = 10
    NAV_TAKEOFF_COMMAND = mavutil.mavlink.MAV_CMD_NAV_TAKEOFF

    _MESSAGE_EVENTS = (
        (
            "Armed AUTO",
            TakeoffExecutionEventType.ARMED_AUTO,
        ),
        (
            "Timeout AUTO",
            TakeoffExecutionEventType.PRETRIGGER_TIMEOUT,
        ),
        (
            "Bad launch AUTO",
            TakeoffExecutionEventType.BAD_LAUNCH,
        ),
        (
            "Triggered AUTO",
            TakeoffExecutionEventType.TRIGGERED_AUTO,
        ),
        (
            "Takeoff timeout",
            TakeoffExecutionEventType.TAKEOFF_TIMEOUT,
        ),
        (
            "Takeoff complete",
            TakeoffExecutionEventType.TAKEOFF_COMPLETE,
        ),
    )

    _TERMINATION_REASONS: ClassVar[
        dict[TakeoffExecutionEventType, TakeoffTerminationReason]
    ] = {
        TakeoffExecutionEventType.TAKEOFF_TIMEOUT: (
            TakeoffTerminationReason.TAKEOFF_TIMEOUT
        ),
        TakeoffExecutionEventType.TAKEOFF_COMPLETE: (
            TakeoffTerminationReason.COMPLETED
        ),
    }

    def detect(self, flight_log: FlightLog) -> list[TakeoffExecution]:
        """Return causally bounded AUTO mission takeoff executions."""
        starts = self._command_starts(flight_log)
        if not starts:
            return []

        message_events = self._message_events(flight_log)
        log_end_us = self._last_available_time_us(flight_log)
        executions = []

        for start in starts:
            termination = self._first_termination(
                flight_log,
                start,
                message_events,
                log_end_us,
            )
            end_inclusive = termination.reason is TakeoffTerminationReason.LOG_END
            events = tuple(
                event
                for event in message_events
                if start.time_us <= event.time_us
                and (
                    event.time_us < termination.time_us
                    or (end_inclusive and event.time_us == termination.time_us)
                )
            )
            if termination.event is not None:
                events += (termination.event,)

            executions.append(
                TakeoffExecution(
                    start_us=start.time_us,
                    end_us=termination.time_us,
                    mission_item_number=start.mission_item_number,
                    command_id=self.NAV_TAKEOFF_COMMAND,
                    termination_reason=termination.reason,
                    events=tuple(sorted(events, key=lambda event: event.time_us)),
                )
            )

        return executions

    def _command_starts(self, flight_log: FlightLog) -> list[_CommandStart]:
        mise = flight_log.get("MISE")
        mode = flight_log.get("MODE")
        required = {"TimeUS", "CNum", "CId"}

        if (
            mise.empty
            or mode.empty
            or not required.issubset(mise.columns)
            or "TimeUS" not in mode.columns
            or "ModeNum" not in mode.columns
        ):
            return []

        mode_rows = []
        for _, row in mode.iterrows():
            time_us = self._integer(row["TimeUS"])
            mode_number = self._integer(row["ModeNum"])
            if time_us is not None:
                mode_rows.append((time_us, mode_number))
        mode_rows.sort(key=lambda item: item[0])

        starts = []
        for _, row in mise.iterrows():
            time_us = self._integer(row["TimeUS"])
            command_id = self._integer(row["CId"])
            mission_item_number = self._integer(row["CNum"])
            if (
                time_us is None
                or command_id != self.NAV_TAKEOFF_COMMAND
                or mission_item_number is None
                or not self._auto_owned_before(mode_rows, time_us)
            ):
                continue
            starts.append(_CommandStart(time_us, mission_item_number))

        return sorted(starts, key=lambda start: start.time_us)

    def _message_events(
        self,
        flight_log: FlightLog,
    ) -> list[TakeoffExecutionEvent]:
        msg = flight_log.get("MSG")
        if msg.empty or "TimeUS" not in msg.columns or "Message" not in msg.columns:
            return []

        events = []
        for _, row in msg.iterrows():
            time_us = self._integer(row["TimeUS"])
            if time_us is None or not isinstance(row["Message"], str):
                continue
            detail = row["Message"]
            for prefix, event_type in self._MESSAGE_EVENTS:
                if detail.startswith(prefix):
                    events.append(TakeoffExecutionEvent(time_us, event_type, detail))
                    break

        # Python's sort is stable, so equal-time MSG rows retain their logged
        # same-stream order without assigning an event-type precedence.
        return sorted(events, key=lambda event: event.time_us)

    def _first_termination(
        self,
        flight_log: FlightLog,
        start: _CommandStart,
        message_events: list[TakeoffExecutionEvent],
        log_end_us: int,
    ) -> _Termination:
        candidates = self._message_terminations(message_events, start.time_us)
        candidates.extend(self._mode_exit(flight_log, start.time_us))
        candidates.extend(self._disarm(flight_log, start.time_us))
        candidates.extend(self._mission_change(flight_log, start.time_us))

        candidates.append(_Termination(log_end_us, TakeoffTerminationReason.LOG_END))

        earliest_time_us = min(candidate.time_us for candidate in candidates)
        earliest = [
            candidate
            for candidate in candidates
            if candidate.time_us == earliest_time_us
            and candidate.reason is not TakeoffTerminationReason.LOG_END
        ]
        if not earliest:
            return _Termination(
                earliest_time_us,
                TakeoffTerminationReason.LOG_END,
            )

        reasons = {candidate.reason for candidate in earliest}
        if len(reasons) == 1:
            return earliest[0]

        # These are the only same-time causal relationships established by
        # the firmware contract. All unrelated cross-stream ties retain the
        # boundary timestamp but deliberately leave its precise cause open.
        causal_pairs = {
            frozenset(
                {
                    TakeoffTerminationReason.COMPLETED,
                    TakeoffTerminationReason.MISSION_ADVANCE,
                }
            ): TakeoffTerminationReason.COMPLETED,
            frozenset(
                {
                    TakeoffTerminationReason.TAKEOFF_TIMEOUT,
                    TakeoffTerminationReason.DISARM,
                }
            ): TakeoffTerminationReason.TAKEOFF_TIMEOUT,
        }
        if reason := causal_pairs.get(frozenset(reasons)):
            return next(
                candidate for candidate in earliest if candidate.reason is reason
            )

        return _Termination(
            earliest_time_us,
            TakeoffTerminationReason.AMBIGUOUS,
        )

    def _message_terminations(
        self,
        events: list[TakeoffExecutionEvent],
        start_us: int,
    ) -> list[_Termination]:
        return [
            _Termination(event.time_us, reason, event)
            for event in events
            if event.time_us >= start_us
            and (reason := self._TERMINATION_REASONS.get(event.event_type)) is not None
        ]

    def _mode_exit(
        self,
        flight_log: FlightLog,
        start_us: int,
    ) -> list[_Termination]:
        mode = flight_log.get("MODE")
        if mode.empty or "TimeUS" not in mode.columns or "ModeNum" not in mode.columns:
            return []

        exits = []
        for _, row in mode.iterrows():
            time_us = self._integer(row["TimeUS"])
            mode_number = self._integer(row["ModeNum"])
            if (
                time_us is not None
                and time_us > start_us
                and mode_number is not None
                and mode_number != self.AUTO_MODE
            ):
                exits.append(_Termination(time_us, TakeoffTerminationReason.MODE_EXIT))
        return exits

    def _disarm(
        self,
        flight_log: FlightLog,
        start_us: int,
    ) -> list[_Termination]:
        arm = flight_log.get("ARM")
        if arm.empty or "TimeUS" not in arm.columns or "ArmState" not in arm.columns:
            return []

        disarms = []
        for _, row in arm.iterrows():
            time_us = self._integer(row["TimeUS"])
            arm_state = self._integer(row["ArmState"])
            if time_us is not None and time_us > start_us and arm_state == 0:
                disarms.append(_Termination(time_us, TakeoffTerminationReason.DISARM))
        return disarms

    def _mission_change(
        self,
        flight_log: FlightLog,
        start_us: int,
    ) -> list[_Termination]:
        mise = flight_log.get("MISE")
        if mise.empty or not {"TimeUS", "CId"}.issubset(mise.columns):
            return []

        changes = []
        for _, row in mise.iterrows():
            time_us = self._integer(row["TimeUS"])
            command_id = self._integer(row["CId"])
            if time_us is None or time_us <= start_us or command_id is None:
                continue

            if command_id == self.NAV_TAKEOFF_COMMAND:
                reason = TakeoffTerminationReason.COMMAND_RESTART
            elif self._is_navigation_command(command_id):
                reason = TakeoffTerminationReason.MISSION_ADVANCE
            else:
                continue

            changes.append(
                _Termination(
                    time_us,
                    reason,
                )
            )
        return changes

    @staticmethod
    def _is_navigation_command(command_id: int) -> bool:
        command = mavutil.mavlink.enums["MAV_CMD"].get(command_id)
        return (
            command is not None
            and command.name.startswith("MAV_CMD_NAV_")
            and command.name != "MAV_CMD_NAV_LAST"
        )

    @staticmethod
    def _auto_owned_before(
        mode_rows: list[tuple[int, int | None]],
        time_us: int,
    ) -> bool:
        """Require uncontradicted AUTO ownership established before MISE."""
        prior_mode = None
        same_time_modes = []
        for mode_time_us, mode_number in mode_rows:
            if mode_time_us > time_us:
                break
            if mode_time_us < time_us:
                prior_mode = mode_number
            else:
                same_time_modes.append(mode_number)
        return prior_mode == TakeoffExecutionDetector.AUTO_MODE and all(
            mode_number == TakeoffExecutionDetector.AUTO_MODE
            for mode_number in same_time_modes
        )

    def _last_available_time_us(self, flight_log: FlightLog) -> int:
        last_time_us = None
        for dataframe in flight_log.messages.values():
            if dataframe.empty or "TimeUS" not in dataframe.columns:
                continue
            for value in dataframe["TimeUS"]:
                time_us = self._integer(value)
                if time_us is not None and (
                    last_time_us is None or time_us > last_time_us
                ):
                    last_time_us = time_us

        if last_time_us is None:
            raise ValueError("FlightLog contains no usable TimeUS observations")
        return last_time_us

    @staticmethod
    def _integer(value) -> int | None:
        """Return an exact finite integer value without timestamp rounding."""
        if isinstance(value, bool):
            return None
        if isinstance(value, Integral):
            return int(value)
        if not isinstance(value, Real):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError):
            return None
        if not math.isfinite(number) or not number.is_integer():
            return None
        return int(number)

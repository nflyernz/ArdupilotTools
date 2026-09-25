"""Detect firmware-owned ArduPlane takeoff executions."""

import math
from dataclasses import dataclass
from numbers import Integral, Real
from typing import ClassVar

from pymavlink import mavutil

from .flight_data import FlightLog
from .takeoff_execution import (
    TakeoffEntryContext,
    TakeoffExecution,
    TakeoffExecutionEvent,
    TakeoffExecutionEventType,
    TakeoffTerminationReason,
)


@dataclass(frozen=True, slots=True)
class _ExecutionStart:
    """Direct evidence establishing one takeoff ownership context."""

    time_us: int
    entry_context: TakeoffEntryContext
    mission_item_number: int | None = None
    command_id: int | None = None
    mode_sequence: int | None = None


@dataclass(frozen=True, slots=True)
class _ModeObservation:
    """One usable MODE observation in retained same-stream order."""

    time_us: int
    mode_number: int | None
    sequence: int


@dataclass(frozen=True, slots=True)
class _Termination:
    """One candidate execution termination."""

    time_us: int
    reason: TakeoffTerminationReason
    event: TakeoffExecutionEvent | None = None


class TakeoffExecutionDetector:
    """Identify TAKEOFF-mode and AUTO-mission takeoff ownership."""

    AUTO_MODE = 10
    TAKEOFF_MODE = 13
    TAKEOFF_STAGE = 1
    NORMAL_STAGE = 3
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
            "Above TKOFF alt - loitering",
            TakeoffExecutionEventType.ALREADY_FLYING_ABOVE_TAKEOFF_ALT,
        ),
        (
            "Climbing to TKOFF alt then loitering",
            TakeoffExecutionEventType.ALREADY_FLYING_CLIMB_TO_TAKEOFF_ALT,
        ),
        (
            "Takeoff to ",
            TakeoffExecutionEventType.TARGET_COURSE_FINALIZED,
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
        """Return causally bounded Plane takeoff executions."""
        mode_observations = self._mode_observations(flight_log)
        starts = self._takeoff_mode_starts(mode_observations)
        starts.extend(self._command_starts(flight_log, mode_observations))
        starts.sort(key=lambda start: start.time_us)
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
                mode_observations,
            )
            end_inclusive = termination.reason is TakeoffTerminationReason.LOG_END
            start_inclusive = start.entry_context is TakeoffEntryContext.AUTO_MISSION
            events = tuple(
                event
                for event in message_events
                if (
                    event.time_us > start.time_us
                    or (start_inclusive and event.time_us == start.time_us)
                )
                and (
                    event.time_us < termination.time_us
                    or (end_inclusive and event.time_us == termination.time_us)
                )
                and self._event_belongs_to_context(
                    event,
                    start.entry_context,
                )
            )
            if termination.event is not None:
                events += (termination.event,)
            events += self._status_events(
                flight_log,
                start,
                termination,
                message_events,
            )

            executions.append(
                TakeoffExecution(
                    start_us=start.time_us,
                    end_us=termination.time_us,
                    mission_item_number=start.mission_item_number,
                    command_id=start.command_id,
                    termination_reason=termination.reason,
                    events=tuple(sorted(events, key=lambda event: event.time_us)),
                    entry_context=start.entry_context,
                )
            )

        return executions

    def _mode_observations(
        self,
        flight_log: FlightLog,
    ) -> list[_ModeObservation]:
        mode = flight_log.get("MODE")
        if mode.empty or "TimeUS" not in mode.columns or "ModeNum" not in mode.columns:
            return []

        rows = []
        for source_order, (_, row) in enumerate(mode.iterrows()):
            time_us = self._integer(row["TimeUS"])
            if time_us is None:
                continue
            rows.append(
                (
                    time_us,
                    source_order,
                    self._integer(row["ModeNum"]),
                )
            )
        rows.sort(key=lambda item: item[:2])
        return [
            _ModeObservation(time_us, mode_number, sequence)
            for sequence, (time_us, _, mode_number) in enumerate(rows)
        ]

    def _takeoff_mode_starts(
        self,
        mode_observations: list[_ModeObservation],
    ) -> list[_ExecutionStart]:
        starts = []
        previous_mode = None
        for observation in mode_observations:
            if observation.mode_number is None:
                continue
            if (
                observation.mode_number == self.TAKEOFF_MODE
                and previous_mode != self.TAKEOFF_MODE
            ):
                starts.append(
                    _ExecutionStart(
                        observation.time_us,
                        TakeoffEntryContext.TAKEOFF_MODE,
                        mode_sequence=observation.sequence,
                    )
                )
            previous_mode = observation.mode_number
        return starts

    def _command_starts(
        self,
        flight_log: FlightLog,
        mode_observations: list[_ModeObservation],
    ) -> list[_ExecutionStart]:
        mise = flight_log.get("MISE")
        required = {"TimeUS", "CNum", "CId"}

        if mise.empty or not required.issubset(mise.columns):
            return []

        starts = []
        for _, row in mise.iterrows():
            time_us = self._integer(row["TimeUS"])
            command_id = self._integer(row["CId"])
            mission_item_number = self._integer(row["CNum"])
            if (
                time_us is None
                or command_id != self.NAV_TAKEOFF_COMMAND
                or mission_item_number is None
                or not self._auto_owned_before(mode_observations, time_us)
            ):
                continue
            starts.append(
                _ExecutionStart(
                    time_us,
                    TakeoffEntryContext.AUTO_MISSION,
                    mission_item_number=mission_item_number,
                    command_id=self.NAV_TAKEOFF_COMMAND,
                )
            )

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

    @staticmethod
    def _event_belongs_to_context(
        event: TakeoffExecutionEvent,
        entry_context: TakeoffEntryContext,
    ) -> bool:
        if entry_context is TakeoffEntryContext.TAKEOFF_MODE:
            return event.event_type is not (TakeoffExecutionEventType.TAKEOFF_COMPLETE)
        return event.event_type not in {
            TakeoffExecutionEventType.TARGET_COURSE_FINALIZED,
            TakeoffExecutionEventType.ALREADY_FLYING_ABOVE_TAKEOFF_ALT,
            TakeoffExecutionEventType.ALREADY_FLYING_CLIMB_TO_TAKEOFF_ALT,
        }

    def _status_events(
        self,
        flight_log: FlightLog,
        start: _ExecutionStart,
        termination: _Termination,
        message_events: list[TakeoffExecutionEvent],
    ) -> tuple[TakeoffExecutionEvent, ...]:
        status = flight_log.get("STAT")
        if status.empty or "TimeUS" not in status.columns:
            return ()

        rows = []
        for source_order, (_, row) in enumerate(status.iterrows()):
            time_us = self._integer(row["TimeUS"])
            if time_us is None or not self._time_is_owned(
                start,
                termination,
                time_us,
            ):
                continue
            stage = self._integer(row["Stage"]) if "Stage" in status.columns else None
            suppressed = self._boolean(row["Sup"]) if "Sup" in status.columns else None
            rows.append((time_us, source_order, stage, suppressed))
        rows.sort(key=lambda item: item[:2])

        events = []
        unsuppressed = self._throttle_unsuppressed_event(
            rows,
            start.entry_context,
            [
                event
                for event in message_events
                if self._time_is_owned(
                    start,
                    termination,
                    event.time_us,
                )
            ],
        )
        if unsuppressed is not None:
            events.append(unsuppressed)

        if start.entry_context is TakeoffEntryContext.TAKEOFF_MODE:
            completion = self._takeoff_control_completion(
                rows,
                termination,
                [
                    event
                    for event in message_events
                    if self._time_is_owned(
                        start,
                        termination,
                        event.time_us,
                    )
                ],
            )
            if completion is not None:
                events.append(completion)
        return tuple(events)

    @staticmethod
    def _throttle_unsuppressed_event(
        status_rows: list[tuple[int, int, int | None, bool | None]],
        entry_context: TakeoffEntryContext,
        message_events: list[TakeoffExecutionEvent],
    ) -> TakeoffExecutionEvent | None:
        """Return a causally owned suppression-clear observation."""
        if entry_context is not TakeoffEntryContext.TAKEOFF_MODE:
            first_unsuppressed = next(
                (row for row in status_rows if row[3] is False),
                None,
            )
            if first_unsuppressed is None:
                return None
            return TakeoffExecutionEvent(
                first_unsuppressed[0],
                TakeoffExecutionEventType.THROTTLE_UNSUPPRESSED,
                "STAT.Sup=0",
            )

        trigger_times = [
            event.time_us
            for event in message_events
            if event.event_type is TakeoffExecutionEventType.TRIGGERED_AUTO
        ]
        saw_suppressed = False
        candidate_time_us = None

        for time_us, _, _, suppressed in status_rows:
            if suppressed is True:
                saw_suppressed = True
                candidate_time_us = None
                continue
            if suppressed is not False:
                continue

            if any(trigger_time < time_us for trigger_time in trigger_times):
                candidate_time_us = time_us
                break
            if candidate_time_us is not None:
                break
            if saw_suppressed:
                candidate_time_us = time_us

        if candidate_time_us is None:
            return None
        if not any(
            trigger_time < candidate_time_us for trigger_time in trigger_times
        ) and not any(
            time_us > candidate_time_us and suppressed is False
            for time_us, _, _, suppressed in status_rows
        ):
            return None
        return TakeoffExecutionEvent(
            candidate_time_us,
            TakeoffExecutionEventType.THROTTLE_UNSUPPRESSED,
            "STAT.Sup=0",
        )

    def _takeoff_control_completion(
        self,
        status_rows: list[tuple[int, int, int | None, bool | None]],
        termination: _Termination,
        message_events: list[TakeoffExecutionEvent],
    ) -> TakeoffExecutionEvent | None:
        """Return a causally defensible observed TAKEOFF-to-NORMAL boundary."""
        trigger_times = [
            event.time_us
            for event in message_events
            if event.event_type is TakeoffExecutionEventType.TRIGGERED_AUTO
        ]
        response_established = False
        previous_stage = None
        candidate = None

        for time_us, _, stage, suppressed in status_rows:
            if suppressed is False or any(
                trigger_time < time_us for trigger_time in trigger_times
            ):
                response_established = True
            if not response_established or stage is None:
                continue

            if stage == self.TAKEOFF_STAGE:
                previous_stage = stage
                candidate = None
                continue

            if stage == self.NORMAL_STAGE:
                if previous_stage == self.TAKEOFF_STAGE:
                    candidate = TakeoffExecutionEvent(
                        time_us,
                        TakeoffExecutionEventType.TAKEOFF_CONTROL_COMPLETED,
                        "STAT.Stage TAKEOFF(1) -> NORMAL(3)",
                    )
                    previous_stage = stage
                    if termination.reason is TakeoffTerminationReason.LOG_END:
                        return candidate
                    continue
                if candidate is not None:
                    # A second retained NORMAL observation before MODE exit
                    # proves that the first was not the Stage change performed
                    # inside new-mode entry immediately before MODE is logged.
                    return candidate
                previous_stage = stage
                continue

            previous_stage = stage
            candidate = None
        return None

    @staticmethod
    def _time_is_owned(
        start: _ExecutionStart,
        termination: _Termination,
        time_us: int,
    ) -> bool:
        start_owned = time_us > start.time_us or (
            start.entry_context is TakeoffEntryContext.AUTO_MISSION
            and time_us == start.time_us
        )
        end_owned = time_us < termination.time_us or (
            termination.reason is TakeoffTerminationReason.LOG_END
            and time_us == termination.time_us
        )
        return start_owned and end_owned

    def _first_termination(
        self,
        flight_log: FlightLog,
        start: _ExecutionStart,
        message_events: list[TakeoffExecutionEvent],
        log_end_us: int,
        mode_observations: list[_ModeObservation],
    ) -> _Termination:
        if start.entry_context is TakeoffEntryContext.TAKEOFF_MODE:
            return self._takeoff_mode_termination(
                start,
                mode_observations,
                log_end_us,
            )

        candidates = self._message_terminations(message_events, start.time_us)
        candidates.extend(self._auto_mode_exit(mode_observations, start.time_us))
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

    def _takeoff_mode_termination(
        self,
        start: _ExecutionStart,
        mode_observations: list[_ModeObservation],
        log_end_us: int,
    ) -> _Termination:
        """End Mode-13 ownership only on its next observed mode exit."""
        if start.mode_sequence is not None:
            for observation in mode_observations:
                if (
                    observation.sequence > start.mode_sequence
                    and observation.mode_number is not None
                    and observation.mode_number != self.TAKEOFF_MODE
                ):
                    return _Termination(
                        observation.time_us,
                        TakeoffTerminationReason.MODE_EXIT,
                    )
        return _Termination(log_end_us, TakeoffTerminationReason.LOG_END)

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

    def _auto_mode_exit(
        self,
        mode_observations: list[_ModeObservation],
        start_us: int,
    ) -> list[_Termination]:
        exits = []
        for observation in mode_observations:
            if (
                observation.time_us > start_us
                and observation.mode_number is not None
                and observation.mode_number != self.AUTO_MODE
            ):
                exits.append(
                    _Termination(
                        observation.time_us,
                        TakeoffTerminationReason.MODE_EXIT,
                    )
                )
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
        mode_observations: list[_ModeObservation],
        time_us: int,
    ) -> bool:
        """Require uncontradicted AUTO ownership established before MISE."""
        prior_mode = None
        same_time_modes = []
        for observation in mode_observations:
            if observation.time_us > time_us:
                break
            if observation.time_us < time_us:
                prior_mode = observation.mode_number
            else:
                same_time_modes.append(observation.mode_number)
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

    @classmethod
    def _boolean(cls, value) -> bool | None:
        """Return a logged boolean only when encoded exactly as zero or one."""
        if isinstance(value, bool):
            return value
        integer = cls._integer(value)
        if integer in (0, 1):
            return bool(integer)
        try:
            if value == 0:
                return False
            if value == 1:
                return True
        except (TypeError, ValueError):
            pass
        return None

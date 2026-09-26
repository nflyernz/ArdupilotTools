"""Log-wide AUTOTUNE lifecycle and per-axis evidence, independent of flights.

See Docs/Implementation/Autotune_firmware_semantics.md. ParameterHistory is
configuration evidence only; raw PARM supplies separate save-processing evidence.
"""

import math
import re
from bisect import bisect_left, bisect_right

from .autotune import (
    ActionTransition,
    AutotuneActivationContext,
    AutotuneAnalysisResult,
    AutotuneAxis,
    AutotuneExitOutcome,
    AutotuneFlightRelation,
    AutotuneSessionResult,
    AutotuneTerminationReason,
    AutotuneWarning,
    CompletionEvent,
    DemandPeriod,
    DemandState,
    EvidencePosition,
    GainLimitEvent,
    ParameterSaveObservation,
    RuntimeGains,
    SaveTrigger,
    SaveTriggerType,
)

# Plane-4.7.0 AP_AutoTune::save_gains and controller parameter registrations.
# SMAX is controlled at start, but is NOT a milestone/exit save_gains parameter.
_RATE_SAVES = ("FF", "P", "I", "D", "IMAX", "FLTT", "FLTE", "FLTD")
SAVE_PARAMETERS = {
    AutotuneAxis.ROLL: {f"RLL_RATE_{name}" for name in _RATE_SAVES}
    | {"RLL2SRV_TCONST", "RLL2SRV_RMAX"},
    AutotuneAxis.PITCH: {f"PTCH_RATE_{name}" for name in _RATE_SAVES}
    | {"PTCH2SRV_TCONST", "PTCH2SRV_RMAX_UP", "PTCH2SRV_RMAX_DN"},
    # Yaw's assumed TAU/RMAX are not registered parameters.
    AutotuneAxis.YAW: {f"YAW_RATE_{name}" for name in _RATE_SAVES},
}
CONTROLLED_PARAMETERS = {
    axis: names | {f"{prefix}_RATE_SMAX"}
    for (axis, names), prefix in zip(SAVE_PARAMETERS.items(), ("RLL", "PTCH", "YAW"))
}

# All observed matching save bursts in log_17/log_0 finish within 6.921 ms.
# One audited ATRP reporting interval (25 Hz) bounds the evidence neighborhood,
# including exit, where no next ATRP exists. This is a conservative attribution
# guardrail, NOT a firmware deadline; slower saves remain uncorrelated.
SAVE_CORRELATION_GUARD_US = 40_000
_LIMIT = re.compile(r"^(Roll|Pitch|Yaw)([PD]):\s*([+-]?[\d.]+(?:[eE][+-]?\d+)?)$")
_FINISHED = re.compile(r"^(Roll|Pitch|Yaw): Finished$")
_CONFIGURATION = (
    "AUTOTUNE_AXES",
    "AUTOTUNE_LEVEL",
    "AUTOTUNE_OPTIONS",
    "YAW_RATE_ENABLE",
)


def _number(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (ValueError, TypeError):
        return None


def _integer(value):
    value = _number(value)
    return int(value) if value is not None and value.is_integer() else None


def _position(row):
    time = _integer(row.get("TimeUS"))
    if time is None or time < 0:
        return None
    return EvidencePosition(time, _integer(row.get("_SourceOrder")))


def _gains(position, row):
    return RuntimeGains(
        position, *(_number(row.get(k)) for k in ("FF", "P", "I", "D", "RMAX", "TAU"))
    )


def _agree(left, right):
    # The BIN fields are float32; allow only float representation error.
    return (
        left is not None
        and right is not None
        and math.isclose(left, right, rel_tol=1e-6, abs_tol=1e-8)
    )


class AutotuneDetector:
    """Detect authoritative sessions first, then attach evidence and context."""

    def detect(self, flight_log):
        version = flight_log.firmware_version()
        result = AutotuneAnalysisResult(
            firmware=version["version"] if version else None
        )
        streams = {}
        for name in ("MSG", "ATRP", "PARM", "MODE", "MAVC", "MISE"):
            rows = []
            missing_order = False
            for row in flight_log.get(name).to_dict("records"):
                position = _position(row)
                if position is None:
                    result.warnings.append(
                        AutotuneWarning(
                            "INVALID_TIME", f"{name}: record has no usable TimeUS"
                        )
                    )
                    continue
                missing_order |= position.source_order is None
                rows.append((position, row))
            if missing_order:
                result.warnings.append(
                    AutotuneWarning(
                        "SOURCE_ORDER_UNAVAILABLE",
                        f"{name}: same-time cross-message ownership unavailable",
                    )
                )
            streams[name] = sorted(rows, key=lambda item: item[0].key)

        self._sessions(flight_log, streams["MSG"], result)
        samples = {(s.number, a): [] for s in result.sessions for a in AutotuneAxis}
        for position, row in streams["ATRP"]:
            session = self._owner(result.sessions, position)
            axis_id = _integer(row.get("Axis"))
            if axis_id not in (0, 1, 2):
                result.warnings.append(
                    AutotuneWarning(
                        "INVALID_AXIS", f"ATRP axis {row.get('Axis')!r}", position
                    )
                )
            elif session is None:
                result.warnings.append(
                    AutotuneWarning(
                        "ORPHAN_ATRP",
                        f"{AutotuneAxis(axis_id).name}: ATRP without owning Started autotune",
                        position,
                        record=row,
                    )
                )
            else:
                samples[session.number, AutotuneAxis(axis_id)].append((position, row))

        for position, row in streams["MSG"]:
            text = str(row.get("Message", "")).strip()
            limit, finished = _LIMIT.fullmatch(text), _FINISHED.fullmatch(text)
            if not (limit or finished or text.startswith("Autotuning ")):
                continue
            session = self._owner(result.sessions, position)
            if session is None:
                result.warnings.append(
                    AutotuneWarning(
                        "ORPHAN_MESSAGE",
                        text + " without owning session",
                        position,
                        record=row,
                    )
                )
                continue
            if text.startswith("Autotuning "):
                words = text[len("Autotuning ") :].split()
                selected = tuple(a for a in AutotuneAxis if a.name.lower() in words)
                if any(word not in ("roll", "pitch", "yaw") for word in words):
                    result.warnings.append(
                        AutotuneWarning(
                            "INVALID_SELECTION", text, position, session.number
                        )
                    )
                    continue
                session.selection_events.append((position, selected))
                if (
                    session.selected_axes is not None
                    and session.selected_axes != selected
                ):
                    result.warnings.append(
                        AutotuneWarning(
                            "CONFLICTING_SELECTION", text, position, session.number
                        )
                    )
                else:
                    session.selected_axes = selected
                continue
            match = limit or finished
            axis = AutotuneAxis[match[1].upper()]
            evidence = session.axes[axis]
            if limit:
                value = _number(limit[3])
                if value is not None:
                    evidence.gain_limit_events.append(
                        GainLimitEvent(position, axis, limit[2], value)
                    )
            else:
                evidence.completion_events.append(CompletionEvent(position, axis))
                evidence.persistence.save_requests.append(
                    SaveTrigger(position, axis, SaveTriggerType.FINISHED_MILESTONE)
                )

        for session in result.sessions:
            self._context(flight_log, streams, session, result)
            for axis, evidence in session.axes.items():
                self._axis(samples[session.number, axis], evidence, session, result)
                self._exit(session, evidence, result)
        self._correlate(streams, samples, result)
        for previous, current in zip(result.sessions, result.sessions[1:]):
            for axis in AutotuneAxis:
                last = previous.axes[axis].final_observed_runtime_gains
                first = current.axes[axis].entry_runtime_gains
                if (
                    last
                    and first
                    and all(_agree(a, b) for a, b in zip(last.values, first.values))
                ):
                    current.axes[
                        axis
                    ].persistence.runtime_continuity_from_session = previous.number
        result.warnings.sort(
            key=lambda w: (w.position.key if w.position else (-1, -1), w.code, w.detail)
        )
        return result

    @staticmethod
    def _sessions(flight_log, messages, result):
        opened = None
        for position, row in messages:
            text = str(row.get("Message", "")).strip()
            if text == "Started autotune":
                if opened:
                    opened.end = position
                    opened.termination_reason = AutotuneTerminationReason.RESTARTED
                opened = AutotuneSessionResult(len(result.sessions) + 1, position)
                opened.configuration = {
                    name: flight_log.parameter_history.value_at(name, position.time_us)
                    for name in _CONFIGURATION
                }
                mask = _integer(opened.configuration["AUTOTUNE_AXES"])
                if mask is not None and 0 <= mask <= 7:
                    opened.configured_axes = tuple(
                        a for a in AutotuneAxis if mask & (1 << a.value)
                    )
                result.sessions.append(opened)
            elif text == "Stopped autotune":
                if opened:
                    opened.end = position
                    opened.termination_reason = AutotuneTerminationReason.STOPPED
                    opened = None
                else:
                    result.warnings.append(
                        AutotuneWarning(
                            "ORPHAN_STOP",
                            "Stopped autotune without open session",
                            position,
                            record=row,
                        )
                    )
        if opened:
            opened.termination_reason = AutotuneTerminationReason.LOG_END
            time = _integer(flight_log.metadata.get("last_decoded_time_us"))
            order = _integer(flight_log.metadata.get("last_decoded_source_order"))
            if time is not None and order is not None and time >= opened.start.time_us:
                opened.end = EvidencePosition(time, order)
            else:
                result.warnings.append(
                    AutotuneWarning(
                        "LOG_END_UNAVAILABLE",
                        "Exact decoded log-end evidence unavailable",
                        session_number=opened.number,
                    )
                )
        for session in result.sessions:
            if session.termination_reason is not AutotuneTerminationReason.STOPPED:
                result.warnings.append(
                    AutotuneWarning(
                        "NORMAL_STOP_NOT_OBSERVED",
                        "Normal stop not observed: " + session.termination_reason.value,
                        session.end,
                        session.number,
                    )
                )

    @staticmethod
    def _owner(sessions, position):
        for session in sessions:
            if position.time_us == session.start.time_us and (
                position.source_order is None or session.start.source_order is None
            ):
                continue
            if (
                session.end
                and position.time_us == session.end.time_us
                and (position.source_order is None or session.end.source_order is None)
            ):
                continue
            if position.key <= session.start.key:
                continue
            if (
                session.end is None
                or position.key < session.end.key
                or (
                    session.termination_reason is AutotuneTerminationReason.LOG_END
                    and position.key == session.end.key
                )
            ):
                return session
        return None

    @staticmethod
    def _axis(rows, evidence, session, result):
        evidence.atrp_count = len(rows)
        if not rows:
            return
        evidence.entry_runtime_gains = _gains(*rows[0])
        evidence.final_observed_runtime_gains = _gains(*rows[-1])
        if any(
            value is None
            for row in (
                evidence.entry_runtime_gains,
                evidence.final_observed_runtime_gains,
            )
            for value in row.values
        ):
            result.warnings.append(
                AutotuneWarning(
                    "RUNTIME_GAINS_UNAVAILABLE",
                    f"{evidence.axis.name}: some boundary ATRP gains unavailable",
                    session_number=session.number,
                )
            )
        previous_action = None
        state = None
        start = None
        last_position = rows[0][0]
        for position, row in rows:
            action = _integer(row.get("Action"))
            if action not in range(10):
                result.warnings.append(
                    AutotuneWarning(
                        "INVALID_ACTION",
                        f"{evidence.axis.name}: ATRP Action unavailable",
                        position,
                        session.number,
                    )
                )
                previous_action = None
            elif previous_action is None:
                if evidence.action_baseline is None:
                    evidence.action_baseline = action
                previous_action = action
            elif action != previous_action:
                evidence.action_transitions.append(
                    ActionTransition(position, previous_action, action)
                )
                previous_action = action
            state_value = _integer(row.get("State"))
            new_state = DemandState(state_value) if state_value in (0, 1, 2) else None
            if new_state != state:
                if state in (DemandState.DEMAND_POS, DemandState.DEMAND_NEG):
                    evidence.demand_periods.append(
                        DemandPeriod(
                            state,
                            start,
                            position if new_state is not None else last_position,
                            new_state is not None,
                        )
                    )
                state, start = new_state, position
            if new_state is None:
                result.warnings.append(
                    AutotuneWarning(
                        "INVALID_STATE",
                        f"{evidence.axis.name}: ATRP state unavailable",
                        position,
                        session.number,
                    )
                )
            last_position = position
        if state in (DemandState.DEMAND_POS, DemandState.DEMAND_NEG):
            # Censor at the last axis observation; never extend to session end.
            evidence.demand_periods.append(
                DemandPeriod(state, start, last_position, False)
            )

    @staticmethod
    def _exit(session, evidence, result):
        if session.termination_reason is not AutotuneTerminationReason.STOPPED:
            return
        limits = {event.kind: event.value for event in evidence.gain_limit_events}
        persistence = evidence.persistence
        if evidence.completion_events or (
            limits.get("P", 0) > 0 and limits.get("D", 0) > 0
        ):
            persistence.exit_outcome = AutotuneExitOutcome.SAVE_REQUESTED
            persistence.exit_basis = "Normal stop with required P/D limit state evidenced by limits or completion"
            persistence.save_requests.append(
                SaveTrigger(session.end, evidence.axis, SaveTriggerType.SESSION_EXIT)
            )
        elif (
            evidence.active
            and not limits
            and evidence.demand_periods
            and any(t.current == 6 for t in evidence.action_transitions)
            and not any(t.current in (8, 9) for t in evidence.action_transitions)
            and not any(
                (
                    w.session_number == session.number
                    and w.code
                    in (
                        "INVALID_STATE",
                        "INVALID_ACTION",
                        "RUNTIME_GAINS_UNAVAILABLE",
                        "INVALID_SELECTION",
                        "CONFLICTING_SELECTION",
                        "AXIS_CONFIGURATION_MISMATCH",
                    )
                )
                or w.code in ("INVALID_TIME", "SOURCE_ORDER_UNAVAILABLE")
                for w in result.warnings
            )
        ):
            # The validated log_17 case: fresh reset, demand/RAISE_D progress,
            # no limit or Finished evidence, and an authoritative normal stop.
            persistence.exit_outcome = AutotuneExitOutcome.RESTORE_INFERRED
            persistence.exit_basis = "Fresh session; demand and RAISE_D observed; no P/D limits or completion; normal stop (assumes progress messages were not lost)"

    @staticmethod
    def _context(flight_log, streams, session, result):
        prior_modes = [
            (p, _integer(r.get("ModeNum")))
            for p, r in streams["MODE"]
            if p.key <= session.start.key
        ]
        modes = tuple(
            (p, _integer(r.get("ModeNum")))
            for p, r in streams["MODE"]
            if AutotuneDetector._owner([session], p)
        )
        commands = tuple(
            (p, name, _integer(r.get("Cmd", r.get("CId"))))
            for name in ("MAVC", "MISE")
            for p, r in streams[name]
            if AutotuneDetector._owner([session], p)
        )
        session.activation_context = AutotuneActivationContext(
            prior_modes[-1][1] if prior_modes else None,
            modes,
            tuple(sorted(commands, key=lambda item: item[0].key)),
        )
        if session.end:
            for index, flight in enumerate(flight_log.flights, 1):
                if (
                    session.start.time_us <= flight.end_us
                    and session.end.time_us >= flight.start_us
                ):
                    relation = AutotuneFlightRelation(
                        index,
                        session.start.time_us < flight.start_us,
                        session.end.time_us > flight.end_us,
                    )
                    session.flight_relations.append(relation)
                    if relation.extends_beyond_flight:
                        result.warnings.append(
                            AutotuneWarning(
                                "EXTENDS_BEYOND_FLIGHT",
                                "Session extends beyond detected flight window",
                                session.end,
                                session.number,
                            )
                        )
        if not session.flight_relations:
            result.warnings.append(
                AutotuneWarning(
                    "NO_ASSOCIATED_FLIGHT",
                    "No associated detected flight window",
                    session.start,
                    session.number,
                )
            )
        if (
            session.selected_axes is not None
            and session.configured_axes is not None
            and session.selected_axes != session.configured_axes
        ):
            result.warnings.append(
                AutotuneWarning(
                    "AXIS_CONFIGURATION_MISMATCH",
                    "Selected axes differ from configured axes at session start",
                    session.start,
                    session.number,
                )
            )

    @staticmethod
    def _correlate(streams, samples, result):
        """Require a local ordered trigger AND same-axis runtime-value agreement.

        Match only between a trigger and the next same-axis ATRP (at most 40ms).
        Allow either bracketing ATRP value: update/save/log are not atomic.
        Exit uses the last owned ATRP. New lifecycle/limit/completion events,
        any command, or an unrelated raw PARM terminate the neighborhood.
        Missing source order, unmatched values, and filters without ATRP values
        cannot yield positive attribution. Each raw record gets at most one owner.
        """
        parm_keys = [p.key for p, _ in streams["PARM"]]
        barriers = [p.key for name in ("MAVC", "MISE") for p, _ in streams[name]]
        for p, row in streams["MSG"]:
            text = str(row.get("Message", "")).strip()
            if (
                text in ("Started autotune", "Stopped autotune")
                or _LIMIT.fullmatch(text)
                or _FINISHED.fullmatch(text)
            ):
                barriers.append(p.key)
        barriers.sort()
        claimed = set()
        for session in result.sessions:
            for axis, evidence in session.axes.items():
                rows = samples[session.number, axis]
                keys = [p.key for p, _ in rows]
                for trigger in evidence.persistence.save_requests:
                    position = trigger.position
                    if position.source_order is None:
                        continue
                    # A normal stop can request saves for several axes together.
                    # Other-axis writes at a single-axis milestone are unrelated.
                    allowed_parameters = set().union(
                        *(
                            SAVE_PARAMETERS[other_axis]
                            for other_axis, other in session.axes.items()
                            if any(
                                t.position == position
                                for t in other.persistence.save_requests
                            )
                        )
                    )
                    index = bisect_left(keys, position.key)
                    before = _gains(*rows[index - 1]) if index else None
                    after = _gains(*rows[index]) if index < len(rows) else None
                    # Stale runtime observations do not corroborate a local save.
                    gains = [
                        g
                        for g in (before, after)
                        if g
                        and abs(g.position.time_us - position.time_us)
                        <= SAVE_CORRELATION_GUARD_US
                    ]
                    upper = (position.time_us + SAVE_CORRELATION_GUARD_US, math.inf)
                    if after:
                        upper = min(upper, after.position.key)
                    next_barrier = bisect_right(barriers, position.key)
                    if next_barrier < len(barriers):
                        upper = min(upper, barriers[next_barrier])
                    for p, row in streams["PARM"][
                        bisect_right(parm_keys, position.key) :
                    ]:
                        if p.key >= upper:
                            break
                        name = row.get("Name")
                        if name not in allowed_parameters:
                            break
                        if (
                            name not in SAVE_PARAMETERS[axis]
                            or p.source_order is None
                            or p.key in claimed
                        ):
                            continue
                        attribute = AutotuneDetector._runtime_attribute(name)
                        value = _number(row.get("Value"))
                        agreeing = next(
                            (
                                g
                                for g in gains
                                if attribute and _agree(value, getattr(g, attribute))
                            ),
                            None,
                        )
                        if agreeing is None:
                            if attribute and value is not None:
                                break  # A conflicting controlled value defeats this burst.
                            continue
                        evidence.persistence.parameter_save_observations.append(
                            ParameterSaveObservation(
                                p, name, value, trigger, agreeing.position
                            )
                        )
                        claimed.add(p.key)

    @staticmethod
    def _runtime_attribute(name):
        if name.endswith("_TCONST"):
            return "tau"
        if name in ("RLL2SRV_RMAX", "PTCH2SRV_RMAX_UP"):
            return "rmax"
        # ATRP does not report negative RMAX or filter/IMAX/SMAX values.
        suffix = name.rsplit("_", 1)[-1]
        return suffix.lower() if suffix in ("FF", "P", "I", "D") else None

"""Log-wide, BIN-only Plane RC-failsafe episode evidence."""

from dataclasses import dataclass, field
import math

from .modes import mode_name


@dataclass(frozen=True, order=True)
class Position:
    """A decoded BIN record's time and ordering, with its source retained."""

    time_us: int
    source_order: int
    source: str = field(compare=False)


@dataclass
class FailsafeEpisode:
    """Separate sampled-input and firmware-action evidence for one episode."""

    start: Position | None = None
    revalid: Position | None = None
    short_on: Position | None = None
    short_clear: Position | None = None
    long_on: Position | None = None
    long_clear: Position | None = None
    throttle_off: Position | None = None
    short_mode: tuple[Position, str] | None = None
    long_mode: tuple[Position, str] | None = None
    short_claim: str | None = None
    long_claim: str | None = None
    recovery_mode: tuple[Position, str] | None = None
    unassigned_modes: list[tuple[Position, str]] = field(default_factory=list)
    mode_at_start: str | None = None
    mode_at_clear: str | None = None
    armed: str = "unknown"
    throttle: str | None = None
    suppression: str | None = None
    cause: str | None = None
    left_censored: bool = False
    warnings: list[str] = field(default_factory=list)

    @property
    def first(self):
        return self.start or self.short_on or self.long_on

    @property
    def action_clear(self):
        return self.long_clear if self.long_on else self.short_clear

    @property
    def last(self):
        return max(
            (position for position in (self.action_clear, self.revalid) if position),
            default=None,
        )

    @property
    def input_duration_s(self):
        if self.start and self.revalid:
            return (self.revalid.time_us - self.start.time_us) / 1e6
        return None

    @property
    def action_duration_s(self):
        if self.short_on and self.action_clear:
            return (self.action_clear.time_us - self.short_on.time_us) / 1e6
        return None

    @property
    def long_duration_s(self):
        if self.long_on and self.long_clear:
            return (self.long_clear.time_us - self.long_on.time_us) / 1e6
        return None


@dataclass
class RadioLinkResult:
    firmware: str
    episodes: list[FailsafeEpisode] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    has_rci2: bool = False
    has_msg: bool = False
    omitted_unarmed: int = 0


def _integer(value):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(number) or not number.is_integer():
        return None
    return int(number)


def _records(log, name, warnings):
    """Retain well-formed records without inventing equal-time source order."""
    records = []
    for row in log.get(name).to_dict("records"):
        time = _integer(row.get("TimeUS"))
        order = _integer(row.get("_SourceOrder"))
        if time is None or time < 0 or order is None:
            warnings.append(f"{name}: record with invalid time/source order ignored")
            continue
        records.append((Position(time, order, name), row))
    return sorted(records, key=lambda item: item[0])


def _message_kind(message):
    """Recognize only Plane 4.7's explicit RC-failsafe message families."""
    if message == "RC Short Failsafe On" or message.startswith(
        "RC Short Failsafe: switched to "
    ):
        return "short_on"
    if message == "RC Short Failsafe Cleared":
        return "short_clear"
    if message.startswith("RC Long Failsafe On: switched to "):
        return "long_on"
    if message == "RC Long Failsafe Cleared":
        return "long_clear"
    if message == "Throttle failsafe off":
        return "throttle_off"
    return None


def _input_episodes(rci2, warnings):
    episodes = []
    active = None
    valid_seen = False
    previous_asserted = False
    for position, row in rci2:
        flags = _integer(row.get("Flags"))
        if flags is None or flags < 0:
            warnings.append("RCI2: invalid Flags record ignored")
            continue
        asserted = bool(flags & 2)
        valid = bool(flags & 1)
        if not asserted and valid:
            valid_seen = True
            if active:
                active.revalid = position
                active = None
        elif asserted and not previous_asserted and active is None and valid_seen:
            active = FailsafeEpisode(start=position)
            if valid:
                active.warnings.append("RCI2 valid-input and failsafe bits conflict")
            episodes.append(active)
        elif active and asserted and valid:
            if "RCI2 valid-input and failsafe bits conflict" not in active.warnings:
                active.warnings.append("RCI2 valid-input and failsafe bits conflict")
        elif active and not asserted and not valid:
            if "RCI2 failsafe cleared without valid input" not in active.warnings:
                active.warnings.append("RCI2 failsafe cleared without valid input")
        previous_asserted = asserted
    return episodes


def _owner(episodes, position):
    """Use the latest input assertion, including its trailing clear neighborhood."""
    owned = None
    for episode in episodes:
        if episode.start and episode.start <= position:
            owned = episode
        elif episode.start and episode.start > position:
            break
    return owned


def _attach_messages(episodes, messages, has_rci2, rci2, warnings):
    action_only = None
    for position, row in messages:
        kind = _message_kind(str(row.get("Message", "")))
        if kind is None:
            continue
        episode = _owner(episodes, position) if has_rci2 else action_only
        if episode is None and has_rci2:
            episode = action_only
        if episode is None and kind in ("short_on", "long_on"):
            # A missing RCI2 stream gives action-only episodes. With RCI2,
            # an armed action before any valid input is left-censored.
            if has_rci2 and not any(
                p <= position and ((_integer(r.get("Flags")) or 0) & 1)
                for p, r in rci2
            ):
                episode = FailsafeEpisode(left_censored=True)
            elif not has_rci2:
                episode = FailsafeEpisode()
            if episode is not None:
                episodes.append(episode)
                action_only = episode
        if episode is None:
            warnings.append(f"Unowned {kind} MSG at {position.time_us / 1e6:.3f} s")
            continue
        if not has_rci2 and action_only and action_only.action_clear and kind in (
            "short_on", "long_on"
        ):
            episode = FailsafeEpisode()
            episodes.append(episode)
            action_only = episode
        if kind in ("short_on", "long_on") and getattr(episode, kind):
            episode.warnings.append(f"Duplicate {kind} MSG")
            continue
        if kind in ("short_clear", "long_clear") and getattr(episode, kind):
            episode.warnings.append(f"Duplicate {kind} MSG")
            continue
        if kind == "long_on" and episode.short_on is None:
            episode.warnings.append("Long assertion without observed short assertion")
        if kind in ("short_on", "long_on") and episode.revalid and position > episode.revalid:
            episode.warnings.append(f"{kind} MSG after sampled input revalidation")
        if kind == "short_clear" and episode.short_on is None:
            episode.warnings.append("Short clear without observed assertion")
        if kind == "long_clear" and episode.long_on is None:
            episode.warnings.append("Long clear without observed assertion")
        if kind in ("short_on", "long_on") and "switched to " in str(row.get("Message", "")):
            claim = str(row["Message"]).rsplit("switched to ", 1)[1].strip().upper()
            setattr(episode, "short_claim" if kind == "short_on" else "long_claim", claim)
        setattr(episode, kind, position)
    # Action-only episodes can be out of order with input episodes; all later
    # presentation and association uses their first observed position.
    episodes.sort(key=lambda episode: episode.first or Position(0, 0, ""))


def _mode_at(modes, position):
    current = None
    if position is None:
        return None
    for marker, row in modes:
        if marker > position:
            break
        current = mode_name(row.get("ModeNum"))
    return current


def _associate_modes(episodes, modes):
    for index, episode in enumerate(episodes):
        first = episode.first
        if first is None:
            continue
        next_first = episodes[index + 1].first if index + 1 < len(episodes) else None
        episode.mode_at_start = _mode_at(modes, first)
        relevant = [
            (position, row)
            for position, row in modes
            if position >= first and (next_first is None or position < next_first)
        ]
        used = set()
        for stage in ("short", "long"):
            message = getattr(episode, f"{stage}_on")
            if message is None:
                continue
            candidates = [
                (position, row)
                for position, row in relevant
                if _integer(row.get("Rsn")) == 3
                and position <= message
                and position not in used
                and (
                    stage == "short"
                    or episode.short_on is None
                    or position > episode.short_on
                )
            ]
            if len(candidates) == 1:
                position, row = candidates[0]
                setattr(episode, f"{stage}_mode", (position, mode_name(row.get("ModeNum"))))
                used.add(position)
            elif len(candidates) > 1:
                episode.warnings.append(f"Ambiguous {stage} MODE association")
        clear = episode.action_clear
        if clear:
            episode.mode_at_clear = _mode_at(modes, clear)
            recovery = [
                (position, row)
                for position, row in relevant
                if position > clear and _integer(row.get("Rsn")) == 48
            ]
            if len(recovery) == 1:
                position, row = recovery[0]
                episode.recovery_mode = (position, mode_name(row.get("ModeNum")))
            elif len(recovery) > 1:
                episode.warnings.append("Ambiguous recovery MODE association")
        episode.unassigned_modes = [
            (position, mode_name(row.get("ModeNum")))
            for position, row in relevant
            if _integer(row.get("Rsn")) == 3 and position not in used
        ]
        if episode.unassigned_modes:
            episode.warnings.append("Radio-failsafe MODE change has uncertain short/long stage")


def _arm_state(episodes, arm, stat):
    for episode in episodes:
        first = episode.first
        if first is None:
            continue
        preceding = [(p, r) for p, r in arm if p <= first]
        state = _integer(preceding[-1][1].get("ArmState")) if preceding else None
        end = episode.last
        if state == 1:
            disarmed = any(
                p > first and (end is None or p <= end) and _integer(r.get("ArmState")) == 0
                for p, r in arm
            )
            episode.armed = "armed at start" if disarmed or end is None else "armed throughout"
            if disarmed:
                episode.warnings.append("Disarmed during episode")
        elif state == 0:
            episode.armed = "disarmed at start"
        else:
            samples = [
                _integer(row.get("Armed"))
                for position, row in stat
                if position <= first
            ]
            if samples and samples[-1] == 1:
                episode.armed = "armed at sampled STAT only; ARM unavailable"


def _commanded_throttle(episodes, log, rcou, stat):
    history = log.parameter_history
    for episode in episodes:
        begin = episode.start or episode.short_on
        end = episode.revalid if episode.start else episode.action_clear
        if begin is None:
            continue
        if end is None:
            episode.warnings.append("Throttle interval open; complete PWM range unavailable")
            continue
        samples = {}
        minimum_matches = True
        mapping_gap = False
        for position, row in rcou:
            if position < begin or position > end:
                continue
            mapped_here = False
            for number in range(1, 17):
                if history.value_at(f"SERVO{number}_FUNCTION", position.time_us) != 70:
                    continue
                value = _integer(row.get(f"C{number}"))
                if value is None:
                    continue
                mapped_here = True
                samples.setdefault(number, []).append(value)
                minimum = history.value_at(f"SERVO{number}_MIN", position.time_us)
                if minimum is None or value != minimum:
                    minimum_matches = False
            if not mapped_here:
                mapping_gap = True
        if mapping_gap and samples:
            episode.warnings.append(
                "Throttle output mapping changed/absent within interval; PWM summary omitted"
            )
        elif samples:
            if len(samples) == 1:
                number, values = next(iter(samples.items()))
                low, high = min(values), max(values)
                value_range = f"{low}" if low == high else f"{low}–{high}"
                bound = "sampled input-invalid span" if episode.start else "firmware action span"
                label = "; configured minimum" if minimum_matches else ""
                episode.throttle = (
                    f"RCOU.C{number} {value_range} µs ({bound})"
                    f"{label}; motor activity unknown"
                )
            else:
                episode.warnings.append(
                    "Multiple throttle output channels; PWM summary unavailable"
                )
        observed = {
            _integer(row.get("Sup"))
            for position, row in stat
            if begin <= position <= end and _integer(row.get("Sup")) in (0, 1)
        }
        if observed:
            episode.suppression = "STAT.Sup sampled " + ", ".join(
                str(value) for value in sorted(observed)
            )


def _qualify_timeout_path(episodes, log, rci2, rcin):
    """Report only a supported firmware path, never physical RF-loss cause."""
    history = log.parameter_history
    for episode in episodes:
        if episode.start is None:
            continue
        time = episode.start.time_us
        flags_row = next((row for position, row in rci2 if position == episode.start), None)
        if flags_row is None:
            continue
        flags = _integer(flags_row.get("Flags"))
        override = _integer(flags_row.get("OMask"))
        channel = _integer(history.value_at("RCMAP_THROTTLE", time))
        threshold = history.value_at("THR_FS_VALUE", time)
        input_row = next(
            (row for position, row in reversed(rcin) if position <= episode.start),
            None,
        )
        if (
            flags is None or flags & 4 or override != 0
            or history.value_at("THR_FAILSAFE", time) != 1
            or not (history.value_at("RC_FS_TIMEOUT", time) or 0) > 0
            or channel is None or threshold is None or input_row is None
        ):
            continue
        throttle = _integer(input_row.get(f"C{channel}"))
        if throttle is not None and throttle > threshold:
            episode.cause = "RC-input timeout path supported; exact last frame/RF cause unknown"


class RadioLinkDetector:
    """Detect BIN-backed Plane RC failsafe without requiring a flight window."""

    def detect(self, log):
        version = log.firmware_version()
        result = RadioLinkResult(version["version"] if version else "Firmware unavailable")
        rci2 = _records(log, "RCI2", result.warnings)
        messages = _records(log, "MSG", result.warnings)
        modes = _records(log, "MODE", result.warnings)
        arm = _records(log, "ARM", result.warnings)
        stat = _records(log, "STAT", result.warnings)
        rcou = _records(log, "RCOU", result.warnings)
        rcin = _records(log, "RCIN", result.warnings)
        result.has_rci2 = bool(rci2)
        result.has_msg = bool(messages)
        result.episodes = _input_episodes(rci2, result.warnings)
        _attach_messages(result.episodes, messages, result.has_rci2, rci2, result.warnings)
        _associate_modes(result.episodes, modes)
        _arm_state(result.episodes, arm, stat)
        _commanded_throttle(result.episodes, log, rcou, stat)
        _qualify_timeout_path(result.episodes, log, rci2, rcin)
        result.omitted_unarmed = sum(ep.armed == "disarmed at start" for ep in result.episodes)
        return result

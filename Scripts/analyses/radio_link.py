"""User-facing Plane Radio Link / RC Failsafe review with optional CSV."""

from pathlib import Path

from analyses.log_selector import select_log_input
from core.config import Config
from core.edgetx import analyse_edgetx, read_edgetx_csv
from core.log_reader import FlightReader, UnsupportedFirmwareError
from core.radio_link import RadioLinkDetector
from core.time import format_time_us


def _time(position):
    return format_time_us(position.time_us) if position else "?"


def _duration(seconds):
    return f"{seconds:.3f} s" if seconds is not None else "unavailable"


def _configured_seconds(value):
    return f"{value:g} s" if value is not None else "unavailable"


def _timing_lines(episode):
    timing = episode.timing
    if timing is None:
        return []
    lines = [
        "   Configured (PARM at episode onset): "
        f"RC_FS_TIMEOUT {_configured_seconds(timing.rc_timeout_s)}; "
        f"FS_LONG_TIMEOUT {_configured_seconds(timing.long_timeout_s)}"
    ]
    if (
        episode.long_on
        and timing.long_timeout_at_action_s != timing.long_timeout_s
    ):
        lines.append(
            "   FS_LONG_TIMEOUT at long MSG: "
            f"{_configured_seconds(timing.long_timeout_at_action_s)}"
        )
    observations = []
    if timing.previous_valid and episode.start:
        observations.append(
            f"valid→invalid RCI2 {_time(timing.previous_valid)}–{_time(episode.start)}"
        )
    if timing.invalid_to_short_s is not None:
        observations.append(f"invalid→short MSG {timing.invalid_to_short_s:.2f} s")
    if timing.short_to_long_s is not None:
        observations.append(f"short→long MSG {timing.short_to_long_s:.2f} s")
    if observations:
        lines.append("   Observed (BIN): " + "; ".join(observations))
    if timing.candidate_long_age_s:
        low, high = timing.candidate_long_age_s
        lines.append(
            "   Candidate long age from last-valid interval: "
            f"{low:.2f}–{high:.2f} s (inferred, not an exact RC-frame time)"
        )
    explanation = f"; {timing.reason}" if timing.reason else ""
    lines.append(f"   Timing assessment: {timing.assessment}{explanation}")
    if timing.short_to_long_s is not None:
        lines.append("   Long timeout starts at last acceptable RC input, not short MSG.")
    return lines


def format_radio_link_report(result, log_path):
    """Present each evidence layer without turning BIN state into RF claims."""
    armed = [episode for episode in result.episodes if episode.armed.startswith("armed")]
    uncertain = [episode for episode in result.episodes if episode.armed == "unknown"]
    lines = [
        f"Radio Link / RC Failsafe — {Path(log_path).name}",
        f"Firmware: {result.firmware}",
        f"Armed RC-failsafe episodes: {len(armed)}",
    ]
    if not armed:
        if uncertain:
            lines.append(
                "No confirmed armed episodes; failsafe evidence with unknown "
                "arm state follows."
            )
        else:
            evidence = (
                "RCI2 and MSG available"
                if result.has_rci2 and result.has_msg else "evidence incomplete"
            )
            lines.append(
                f"No armed Plane RC-failsafe evidence found ({evidence}); "
                "RF health not assessed."
            )
    for number, episode in enumerate([*armed, *uncertain], start=1):
        lines.append("")
        if episode.start:
            lines.append(
                f"{number}  Input invalid (RCI2 sampled): "
                f"{_time(episode.start)}–{_time(episode.revalid)}; "
                f"{_duration(episode.input_duration_s)}; {episode.armed}"
            )
        else:
            prefix = "left-censored" if episode.left_censored else "RCI2 unavailable"
            lines.append(f"{number}  Input-invalid boundary {prefix}; {episode.armed}")
        if episode.short_on:
            if episode.short_mode:
                response = f"→ {episode.short_mode[1]} (MODE, radio-failsafe reason)"
            elif episode.short_claim:
                response = f"MSG claims → {episode.short_claim}; MODE record unavailable"
            elif episode.mode_at_start:
                response = f"while already {episode.mode_at_start}; no MODE change observed"
            else:
                response = "MODE response unavailable"
            lines.append(f"   Short (MSG) {_time(episode.short_on)} {response}")
        else:
            lines.append("   Short assertion: MSG evidence unavailable")
        if episode.long_on:
            if episode.long_mode:
                response = f"→ {episode.long_mode[1]} (MODE, radio-failsafe reason)"
            elif episode.long_claim:
                response = f"MSG claims → {episode.long_claim}; MODE record unavailable"
            else:
                response = "MODE response unavailable"
            lines.append(f"   Long (MSG) {_time(episode.long_on)} {response}")
        for position, mode in episode.unassigned_modes:
            lines.append(
                f"   Radio-failsafe MODE: {mode} at {_time(position)}; short/long stage unknown"
            )
        if episode.revalid:
            lines.append(f"   Input revalidated (RCI2 sampled) {_time(episode.revalid)}")
        clear = episode.action_clear
        if clear:
            kind = "long" if episode.long_on else "short"
            lines.append(
                f"   {kind.title()} cleared (MSG) {_time(clear)}; "
                f"action span {_duration(episode.action_duration_s)}"
            )
        elif episode.short_on or episode.long_on:
            lines.append("   Firmware action clear unavailable; action duration unavailable")
        if episode.recovery_mode:
            lines.append(
                f"   Recovery MODE: {episode.recovery_mode[1]} "
                f"at {_time(episode.recovery_mode[0])}"
            )
        elif episode.mode_at_clear:
            lines.append(f"   Mode at clear: {episode.mode_at_clear}")
        if episode.throttle:
            lines.append(f"   Throttle command (aircraft BIN): {episode.throttle}")
        if episode.cause:
            lines.append(f"   Cause evidence (aircraft BIN): {episode.cause}")
        lines.extend(_timing_lines(episode))
        if episode.suppression:
            lines.append(f"   {episode.suppression} (aircraft BIN)")
        if episode.start and not episode.revalid:
            lines.append("   Input-invalid episode open at log boundary; no recovery inferred")
        for warning in episode.warnings:
            lines.append(f"   Evidence note: {warning}")
    if result.omitted_unarmed:
        lines.append(f"Unarmed startup/episode evidence omitted: {result.omitted_unarmed}")
    if uncertain:
        lines.append(
            f"Episodes with unknown armed state: {len(uncertain)} "
            "(not counted as armed)"
        )
    for warning in result.warnings:
        lines.append(f"Evidence note: {warning}")
    lines.append(
        "RF-loss instant, motor activity, fresh RXLQ minimum and range "
        "unavailable from BIN."
    )
    return "\n".join(lines)


def format_edgetx_overlay(overlay):
    """Append only provenance-labelled transmitter evidence to the BIN report."""
    lines = ["", f"EdgeTX CSV — {overlay.session.path.name}",
             f"Pairing: {overlay.pairing}; alignment: {overlay.alignment.status}"]
    if overlay.pairing == "unpaired":
        return "\n".join([*lines, *(f"EdgeTX note: {note}" for note in overlay.warnings)])
    alignment = overlay.alignment
    lines.append(
        "EdgeTX CSV radio-clock span: "
        f"{overlay.session.rows[0].clock.isoformat(sep=' ', timespec='milliseconds')}"
        " to "
        f"{overlay.session.rows[-1].clock.isoformat(sep=' ', timespec='milliseconds')}"
    )
    if alignment.offset_s is not None:
        lines.append(
            "EdgeTX clock: aircraft GPS time minus radio clock approximately "
            f"{alignment.offset_s:.0f} s; "
            + ("numeric bound established" if alignment.status == "bounded" else
               "coarse; exact RF timing unbounded")
        )
    if alignment.anchor_offsets_s:
        lines.append(
            "EdgeTX alignment landmarks: "
            f"{alignment.anchors} {alignment.reason}; observed offset range "
            f"{min(alignment.anchor_offsets_s):.1f}–"
            f"{max(alignment.anchor_offsets_s):.1f} s"
            + (" (diagnostic spread, not an uncertainty bound)"
               if alignment.status == "coarse" else " (bounded anchor intervals)")
        )
    for field, label, unit in (
        ("RQly(%)", "RQly", "%"), ("1RSS(dB)", "1RSS", " dBm"),
        ("2RSS(dB)", "2RSS", " dBm"), ("RSNR(dB)", "RSNR", " dB"),
    ):
        bounds = overlay.session.extrema(field)
        if bounds:
            lines.append(
                f"EdgeTX CSV session observed {label}: {bounds[0]:g}–{bounds[1]:g}{unit} "
                "(receiver-reported; values may be held between rows)"
            )
    for field, label, unit in (("RFMD", "RFMD index", ""),
                               ("TPWR(mW)", "TPWR", " mW")):
        values = sorted({value for row in overlay.session.rows
                         if (value := row.observed(field)) is not None})
        if values:
            display = ", ".join(f"{value:g}" for value in values[:8])
            qualifier = (
                " (reported mode index; packet rate unverified)" if field == "RFMD"
                else " (telemetry-reported; not measured radiated power or configuration)"
            )
            lines.append(
                f"EdgeTX CSV observed {label}: {display}{unit}{qualifier}"
                + (" (additional values omitted)" if len(values) > 8 else "")
            )
    gaps = [run for run in overlay.session.runs if run.availability == "unavailable"
            and run.count >= 2]
    if gaps:
        lines.append(f"EdgeTX CSV telemetry-unavailable runs: {len(gaps)}; "
                     "zero/blank placeholders excluded from RF measurements")
    for index, context in sorted(overlay.episode_context.items()):
        lines.append(f"Aircraft BIN episode #{index}: {context}")
    for index, fields in sorted(overlay.episode_rf.items()):
        details = "; ".join(
            f"{name} {low:g}–{high:g}" for name, (low, high) in fields.items()
        )
        lines.append(f"Aircraft BIN episode #{index}: EdgeTX CSV observed {details}; "
                     "bounded clock and sample age; BIN boundaries unchanged")
    if not overlay.episode_rf:
        lines.append("EdgeTX CSV numeric RF observations are session-level only; "
                     "episode-specific RF aggregation unavailable.")
    for warning in overlay.warnings:
        lines.append(f"EdgeTX note: {warning}")
    return "\n".join(lines)


def _optional_csv(path, result, flight_log):
    """Keep CSV selection local to Radio Link; Enter preserves BIN-only use."""
    nearby = sorted(path.parent.glob("*.csv"))
    if nearby:
        print("\nNearby EdgeTX CSV candidates:")
        for number, candidate in enumerate(nearby, start=1):
            print(f"{number}. {candidate.name}")
    try:
        choice = input("\nOptional EdgeTX CSV [Enter=skip, A=auto, number, P=path]: ").strip()
    except (EOFError, OSError):
        return None
    if not choice:
        return None
    if choice.casefold() == "a":
        candidates = []
        for candidate in nearby:
            try:
                session = read_edgetx_csv(candidate)
            except (OSError, UnicodeError, ValueError):
                continue
            overlay = analyse_edgetx(result, flight_log, session, explicit=False)
            if overlay.pairing == "accepted automatic":
                candidates.append(overlay)
        if len(candidates) == 1:
            return candidates[0]
        return ("automatic pairing ambiguous: "
                f"{len(candidates)} accepted CSV candidates; supply a path explicitly")
    if choice.casefold() == "p":
        try:
            choice = input("EdgeTX CSV path: ").strip()
        except (EOFError, OSError):
            return None
        if not choice:
            return None
    elif choice.isdigit() and 1 <= int(choice) <= len(nearby):
        choice = str(nearby[int(choice) - 1])
    try:
        session = read_edgetx_csv(choice)
        return analyse_edgetx(result, flight_log, session, explicit=True)
    except (OSError, UnicodeError, ValueError) as exc:
        return f"CSV unavailable: {exc}"


class RadioLinkAnalysisPresentation:
    """Select a BIN, then optionally append EdgeTX session evidence."""

    def __init__(self, config=None):
        self.config = config or Config("Config/radio_link.yaml")

    def run(self):
        selected = select_log_input()
        if not selected:
            return
        path = selected[0]
        try:
            flight_log = FlightReader(path, config=self.config).read()
        except (UnsupportedFirmwareError, OSError) as exc:
            print(f"\nRadio Link analysis unavailable: {exc}")
            return
        result = RadioLinkDetector().detect(flight_log)
        print("\n" + format_radio_link_report(result, path))
        overlay = _optional_csv(path, result, flight_log)
        if isinstance(overlay, str):
            print(f"EdgeTX note: {overlay}")
        elif overlay is not None:
            print(format_edgetx_overlay(overlay))

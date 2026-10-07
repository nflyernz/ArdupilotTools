"""User-facing Plane Radio Link / RC Failsafe review with optional CSV."""

from pathlib import Path
import re

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


def _common_configuration(episodes):
    """Collapse only complete, unchanged event-time values in reported episodes."""
    if not episodes or any(episode.timing is None for episode in episodes):
        return None
    timings = [episode.timing for episode in episodes]
    values = {(timing.rc_timeout_s, timing.long_timeout_s)
              for timing in timings}
    if len(values) != 1 or None in next(iter(values)):
        return None
    if any(episode.long_on and timing.long_timeout_at_action_s != timing.long_timeout_s
           for episode, timing in zip(episodes, timings)):
        return None
    return next(iter(values))


def _configuration_lines(rc_timeout, long_timeout, *, indent="  "):
    return [
        f"{indent}Short timeout (RC_FS_TIMEOUT): {_configured_seconds(rc_timeout)}",
        f"{indent}Long timeout (FS_LONG_TIMEOUT): {_configured_seconds(long_timeout)}",
    ]


def _timing_lines(episode, *, show_configuration):
    timing = episode.timing
    if timing is None:
        return []
    lines = ["", "Failsafe timing"]
    if show_configuration:
        lines.append("  Configuration at episode onset (PARM):")
        lines.extend(_configuration_lines(timing.rc_timeout_s, timing.long_timeout_s,
                                          indent="    "))
    if (
        episode.long_on
        and timing.long_timeout_at_action_s != timing.long_timeout_s
    ):
        lines.append(
            "  FS_LONG_TIMEOUT at long MSG: "
            f"{_configured_seconds(timing.long_timeout_at_action_s)}"
        )
    if timing.previous_valid and episode.start:
        lines.append(
            "  Last valid → invalid (RCI2 sampled): "
            f"{_time(timing.previous_valid)}–{_time(episode.start)}"
        )
    if timing.invalid_to_short_s is not None:
        lines.append(
            f"  Invalid RCI2 → short MSG: {timing.invalid_to_short_s:.2f} s"
        )
    if timing.short_to_long_s is not None:
        lines.append(f"  Short → long MSG: {timing.short_to_long_s:.2f} s")
    elif episode.short_on and not episode.long_on:
        lines.append("  Long failsafe: No long MSG assertion observed")
    if timing.candidate_long_age_s:
        low, high = timing.candidate_long_age_s
        lines.append(
            "  Candidate last-valid RC → long MSG: "
            f"{low:.2f}–{high:.2f} s (inferred, not an exact RC-frame time)"
        )
    explanation = f"; {timing.reason}" if timing.reason else ""
    lines.append(f"  Assessment: {timing.assessment}{explanation}")
    return lines


def _throttle_lines(throttle):
    """Keep the sampled PWM summary and its physical-motor limitation distinct."""
    match = re.fullmatch(
        r"RCOU\.C(\d+) ([\d–]+) µs \(([^)]+)\)"
        r"(; configured minimum)?; motor activity unknown", throttle,
    )
    if match:
        minimum = " (configured minimum)" if match[4] else ""
        return ([
            f"  Commanded throttle PWM ({match[3]}): {match[2]} µs{minimum}",
            "  Physical motor activity: Not measurable from BIN",
        ], f"  Throttle output channel: RCOU.C{match[1]} (aircraft BIN)")
    return ([
        f"  Throttle command (aircraft BIN): {throttle}",
        "  Physical motor activity: Not measurable from BIN",
    ], None)


def format_radio_link_report(result, log_path):
    """Present each evidence layer without turning BIN state into RF claims."""
    armed = [episode for episode in result.episodes if episode.armed.startswith("armed")]
    uncertain = [episode for episode in result.episodes if episode.armed == "unknown"]
    reported = [*armed, *uncertain]
    lines = [
        f"Radio Link / RC Failsafe — {Path(log_path).name}",
        f"Firmware: {result.firmware}",
        f"Armed RC-failsafe episodes: {len(armed)}",
    ]
    common_configuration = _common_configuration(reported)
    if common_configuration:
        lines.extend(["", "Failsafe configuration (PARM at reported episode onset)"])
        lines.extend(_configuration_lines(*common_configuration))
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
    for number, episode in enumerate(reported, start=1):
        lines.extend(["", f"Episode #{number} — RC failsafe"])
        if episode.start:
            lines.append(
                "  RC input invalid (RCI2 sampled): "
                f"{_time(episode.start)}–{_time(episode.revalid)} "
                f"({_duration(episode.input_duration_s)})"
            )
        else:
            prefix = "left-censored" if episode.left_censored else "RCI2 unavailable"
            lines.append(f"  RC input-invalid boundary: {prefix}")
        lines.append(f"  Armed state: {episode.armed}")
        lines.extend(["", "Aircraft response"])
        if episode.short_on:
            if episode.short_mode:
                response = f"→ {episode.short_mode[1]} (MODE, radio-failsafe reason)"
            elif episode.short_claim:
                response = f"MSG claims → {episode.short_claim}; MODE record unavailable"
            elif episode.mode_at_start:
                response = f"while already {episode.mode_at_start}; no MODE change observed"
            else:
                response = "MODE response unavailable"
            lines.append(f"  Short failsafe (MSG): {_time(episode.short_on)} {response}")
        else:
            lines.append("  Short assertion: MSG evidence unavailable")
        if episode.long_on:
            if episode.long_mode:
                response = f"→ {episode.long_mode[1]} (MODE, radio-failsafe reason)"
            elif episode.long_claim:
                response = f"MSG claims → {episode.long_claim}; MODE record unavailable"
            else:
                response = "MODE response unavailable"
            lines.append(f"  Long failsafe (MSG): {_time(episode.long_on)} {response}")
        for position, mode in episode.unassigned_modes:
            lines.append(
                f"  Radio-failsafe MODE: {mode} at {_time(position)}; short/long stage unknown"
            )
        if episode.revalid:
            lines.append(f"  RC input revalidated (RCI2 sampled): {_time(episode.revalid)}")
        clear = episode.action_clear
        if clear:
            kind = "long" if episode.long_on else "short"
            lines.append(
                f"  {kind.title()} failsafe cleared (MSG): {_time(clear)}; "
                f"action span {_duration(episode.action_duration_s)}"
            )
        elif episode.short_on or episode.long_on:
            lines.append("  Firmware action clear unavailable; action duration unavailable")
        if episode.recovery_mode:
            lines.append(
                f"  Recovery MODE: {episode.recovery_mode[1]} "
                f"at {_time(episode.recovery_mode[0])}"
            )
        elif episode.mode_at_clear:
            lines.append(f"  Mode at clear: {episode.mode_at_clear}")
        lines.extend(_timing_lines(episode, show_configuration=common_configuration is None))
        notes = []
        if episode.timing and episode.timing.short_to_long_s is not None:
            notes.append(
                "  Long timeout starts at last acceptable RC input, not short MSG."
            )
        if episode.throttle:
            output_lines, channel_note = _throttle_lines(episode.throttle)
            lines.extend(["", "Aircraft outputs", *output_lines])
            if channel_note:
                notes.append(channel_note)
        if episode.cause:
            lines.extend(["", "Evidence"])
            if episode.cause == (
                "RC-input timeout path supported; exact last frame/RF cause unknown"
            ):
                lines.extend([
                    "  RC-input timeout path supported (aircraft BIN)",
                    "  Exact last RC frame / physical RF-loss cause: Not measurable",
                ])
            else:
                lines.append(f"  Cause evidence (aircraft BIN): {episode.cause}")
        if episode.suppression:
            notes.append(f"  {episode.suppression} (aircraft BIN)")
        if episode.start and not episode.revalid:
            notes.append("  Input-invalid episode open at log boundary; no recovery inferred")
        for warning in episode.warnings:
            notes.append(f"  Evidence note: {warning}")
        if notes:
            lines.extend(["", "Notes", *notes])
    if result.omitted_unarmed:
        lines.append(f"Unarmed startup/episode evidence omitted: {result.omitted_unarmed}")
    if uncertain:
        lines.append(
            f"Episodes with unknown armed state: {len(uncertain)} "
            "(not counted as armed)"
        )
    for warning in result.warnings:
        lines.append(f"Evidence note: {warning}")
    lines.extend([
        "", "BIN limitations",
        "  Exact physical RF-loss instant: Not measurable",
        "  Physical motor activity: Not measurable",
        "  Fresh RXLQ minimum: Not available from BIN",
        "  Transmitter distance/range: Not available from BIN",
    ])
    return "\n".join(lines)


def _episode_context_lines(context):
    """Render the existing qualified context without deriving new event timing."""
    lead_in = []
    telemetry = []
    other = []
    for part in context.split("; "):
        if part.startswith("EdgeTX CSV pre-episode lead-in "):
            match = re.search(r": RQly (.+?)%, 1RSS (.+?) dBm$", part)
            if match:
                lead_in.extend([
                    "  RF before telemetry loss (final 30 s before disappearance):",
                    f"    RQly: {match[1]}%",
                    f"    1RSS: {match[2]} dBm",
                    "  These CSV values may have been held between updates.",
                ])
            else:
                other.append(f"  Evidence: {part}")
        elif part == "values may be held":
            continue
        elif part.startswith("EdgeTX CSV telemetry unavailable throughout "):
            telemetry.append(
                "  Telemetry: Unavailable throughout the projected aircraft "
                "failsafe episode."
            )
            sensitivity = re.search(r"±([\d.]+) s offset sensitivity", part)
            bound = re.search(r"±([\d.]+) s bounded offset", part)
            if sensitivity:
                telemetry.append(
                    "  This holds when the coarse clock estimate is shifted by "
                    f"±{sensitivity[1]} s; that test is not a proven timing bound."
                )
            elif bound:
                telemetry.append(
                    f"  Clock-offset uncertainty is bounded to ±{bound[1]} s."
                )
            else:
                telemetry.append(f"  Evidence: {part}")
            telemetry.append("  The telemetry gap is not a measured RF-loss interval.")
        elif part.startswith("EdgeTX CSV telemetry return near projected BIN recovery"):
            telemetry.append("  Telemetry returned near the projected aircraft recovery.")
        elif part == "numeric RF episode membership withheld":
            other.append("  RF values for this episode cannot be determined reliably.")
        elif part != "not a measured RF-loss interval":
            other.append(f"  Evidence: {part}")
    return [*lead_in, *telemetry, *other]


def format_edgetx_overlay(overlay):
    """Present transmitter observations beside, not as causes of, BIN events."""
    pairing = {
        "accepted explicit": "Explicit",
        "accepted automatic": "Automatic",
        "paired but unaligned": "Explicit; session evidence insufficient for alignment",
        "unpaired": "Not established",
    }.get(overlay.pairing, overlay.pairing)
    alignment = overlay.alignment
    lines = ["", f"EdgeTX — {overlay.session.path.name}",
             f"Pairing: {pairing}", f"Alignment: {alignment.status.title()}"]
    if overlay.pairing == "unpaired":
        return "\n".join([*lines, *(f"Note: {note}" for note in overlay.warnings)])
    if alignment.offset_s is not None:
        lines.append(
            f"Radio clock difference: aircraft GPS time minus radio clock "
            f"~{alignment.offset_s:.0f} s"
        )

    lines.extend(["", "Session RF observations (EdgeTX CSV)"])
    for field, label, unit in (
        ("RQly(%)", "Lowest RQly", "%"),
        ("1RSS(dB)", "Weakest 1RSS", " dBm"),
        ("2RSS(dB)", "Weakest 2RSS", " dBm"),
        ("RSNR(dB)", "Lowest RSNR", " dB"),
    ):
        bounds = overlay.session.extrema(field)
        if bounds:
            lines.append(
                f"  {label}: {bounds[0]:g}{unit} "
                f"(observed range {bounds[0]:g}–{bounds[1]:g}{unit})"
            )
    for field, label, unit in (("RFMD", "RF mode index", ""),
                               ("TPWR(mW)", "TX power reported", " mW")):
        values = sorted({value for row in overlay.session.rows
                         if (value := row.observed(field)) is not None})
        if values:
            display = ", ".join(f"{value:g}" for value in values[:8])
            lines.append(f"  {label}: {display}{unit}"
                         + (" (additional values omitted)" if len(values) > 8 else ""))
    gaps = [run for run in overlay.session.runs if run.availability == "unavailable"
            and run.count >= 2]
    if gaps:
        lines.append(f"\nTelemetry was unavailable {len(gaps)} times in this CSV session.")

    for index in sorted(overlay.episode_context.keys() | overlay.episode_rf.keys()):
        lines.extend(["", f"Episode #{index} — EdgeTX CSV"])
        if index in overlay.episode_context:
            lines.extend(_episode_context_lines(overlay.episode_context[index]))
        if index in overlay.episode_rf:
            fields = overlay.episode_rf[index]
            details = "; ".join(
                f"{name} {low:g}–{high:g}" for name, (low, high) in fields.items()
            )
            lines.append(f"  RF observed within bounded episode: {details}.")
            lines.append("  Clock and sample-age bounds established; BIN boundaries unchanged.")
        lines.append("  RF at the exact aircraft failsafe trigger: Not measurable from this CSV.")
    if not overlay.episode_rf:
        lines.append(
            "\nNo episode-specific RF minima established. RF observations around "
            "link loss are not measured failsafe thresholds."
        )

    lines.extend([
        "", "Notes:",
        "  RQly, RSSI and SNR are receiver-reported and may be held between CSV "
        "rows; zero/blank telemetry placeholders are excluded from RF measurements.",
        "  Aircraft BIN RXLQ may remain stale during complete link loss and is "
        "not used as instantaneous RF evidence.",
        "  RF mode is a reported index, not a verified packet rate; TX power is "
        "telemetry-reported, not measured radiated power or configuration.",
        "  CSV radio-clock span: "
        f"{overlay.session.rows[0].clock.isoformat(sep=' ', timespec='milliseconds')}"
        " to "
        f"{overlay.session.rows[-1].clock.isoformat(sep=' ', timespec='milliseconds')}",
    ])
    if alignment.offset_s is not None:
        lines.append(
            "  Exact RF timing remains unbounded."
            if alignment.status == "coarse" else
            "  Numeric clock-offset bound established."
        )
    if alignment.anchor_offsets_s:
        qualifier = ("diagnostic spread, not an uncertainty bound"
                     if alignment.status == "coarse" else "bounded anchor intervals")
        lines.append(
            f"  Alignment: {alignment.anchors} {alignment.reason}; observed offset "
            f"range {min(alignment.anchor_offsets_s):.1f}–"
            f"{max(alignment.anchor_offsets_s):.1f} s ({qualifier})."
        )
    lines.extend(f"  {warning}" for warning in overlay.warnings)
    return "\n".join(lines)


def _candidate_preview(candidate, result, flight_log):
    """Summarize existing evidence without accepting a candidate for the user."""
    try:
        session = read_edgetx_csv(candidate)
    except (OSError, UnicodeError, ValueError) as exc:
        return None, None, f"unusable CSV: {exc}"

    automatic = analyse_edgetx(result, flight_log, session, explicit=False)
    diagnostic = analyse_edgetx(result, flight_log, session, explicit=True)
    hints = []
    if automatic.pairing == "accepted automatic":
        hints.append("Auto-eligible candidate")
    elif diagnostic.alignment.status == "coarse":
        hints.append("GPS-coordinate candidate; explicit selection required")
    else:
        hints.append("no usable GPS-coordinate clock landmarks; explicit selection required")

    if diagnostic.alignment.status == "coarse":
        hints.append(f"{diagnostic.alignment.anchors} aircraft GPS-coordinate landmarks")
        hints.append(
            f"~{diagnostic.alignment.offset_s:.0f} s aircraft/radio clock difference "
            "(local timezone assumed)"
        )
    modes = []
    for row in session.rows:
        if row.fm and (not modes or modes[-1] != row.fm):
            modes.append(row.fm)
    if len(modes) >= 2:
        hints.append("file-wide CSV FM " + "→".join(modes[:3]))
    if (diagnostic.session.source_row_count > len(diagnostic.session.rows)
            or any("covers only part" in note for note in diagnostic.warnings)):
        hints.append("partial CSV coverage")
    return session, automatic, "; ".join(hints)


def _optional_csv(path, result, flight_log):
    """Keep CSV selection local to Radio Link; Enter preserves BIN-only use."""
    nearby = sorted(path.parent.glob("*.csv"))
    previews = [_candidate_preview(candidate, result, flight_log)
                for candidate in nearby]
    while True:
        if nearby:
            print("\nNearby EdgeTX CSV candidates:")
            for number, (candidate, (_, _, hint)) in enumerate(
                    zip(nearby, previews), start=1):
                print(f"{number}. {candidate.name}\n   {hint}")
        try:
            choice = input(
                "\nOptional EdgeTX CSV [Enter=skip, A=auto, number, P=path]: "
            ).strip()
        except (EOFError, OSError):
            return None
        if not choice:
            return None
        if choice.casefold() == "a":
            eligible = [automatic for _, automatic, _ in previews
                        if automatic is not None
                        and automatic.pairing == "accepted automatic"]
            if len(eligible) == 1:
                return eligible[0]
            if eligible:
                reason = ("Auto could not choose uniquely "
                          f"({len(eligible)} eligible candidates).")
            else:
                reason = "Auto found no eligible candidate."
            print(f"EdgeTX note: {reason} "
                  "Choose a number, P for a path, or Enter to skip.")
            continue
        if choice.casefold() == "p":
            try:
                choice = input("EdgeTX CSV path: ").strip()
            except (EOFError, OSError):
                return None
            if not choice:
                continue
        elif choice.isdigit():
            number = int(choice)
            if not 1 <= number <= len(nearby):
                print("Invalid CSV candidate number.")
                continue
            session, _, hint = previews[number - 1]
            if session is None:
                print(f"EdgeTX note: {hint}")
                continue
            return analyse_edgetx(result, flight_log, session, explicit=True)
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

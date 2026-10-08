"""User-facing Plane Radio Link / RC Failsafe review with optional CSV."""

from pathlib import Path
import math
import re
from zoneinfo import ZoneInfo

from analyses.log_selector import select_log_input
from analyses.presentation_text import wrap_report
from core.config import Config
from core.edgetx import analyse_edgetx, gps_clock_from_flight, read_edgetx_csv
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


def _suppression_line(suppression):
    """Name sampled Plane throttle-suppression states without inferring motor state."""
    if suppression == "STAT.Sup sampled 1":
        state = "Active"
    elif suppression == "STAT.Sup sampled 0":
        state = "Inactive"
    elif suppression == "STAT.Sup sampled 0, 1":
        state = "Active and inactive states observed"
    else:
        return f"  Throttle suppression: {suppression} (aircraft BIN)"
    return f"  Throttle suppression: {state} (sampled STAT.Sup; aircraft BIN)"


def _recording_lines(flight_log):
    """Use retained BIN timestamps and valid GPS time, never the filename clock."""
    first_times = []
    for frame in flight_log.messages.values():
        if "TimeUS" not in frame.columns or frame.empty:
            continue
        value = frame["TimeUS"].min()
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number) and number >= 0 and number.is_integer():
            first_times.append(int(number))
    if not first_times:
        return ["Recording date/start: Unavailable (no timestamped BIN records)",
                "Log duration: Unavailable"]
    first_us = min(first_times)
    last_us = flight_log.metadata.get("last_decoded_time_us")
    if not isinstance(last_us, (int, float)) or not math.isfinite(last_us):
        last_us = max(int(frame["TimeUS"].max()) for frame in flight_log.messages.values()
                      if "TimeUS" in frame.columns and not frame.empty)
        end_basis = "last retained"
    else:
        end_basis = "last decoded"
    duration = max(0, int(last_us) - first_us)
    lines = [f"Log duration: {format_time_us(duration)} "
             f"(first retained to {end_basis} BIN record)"]
    clock = gps_clock_from_flight(flight_log)
    if clock is None:
        return ["Recording date/start: Unavailable (no valid GPS absolute time)", *lines]
    utc = clock.utc_at(first_us / 1e6)
    local = utc.astimezone(ZoneInfo("Pacific/Auckland"))
    label = local.tzname()
    result = [
        f"Recording date: {local.day} {local:%B %Y} ({label})",
        f"Recording start: {local:%H:%M:%S} {label}; "
        f"{utc:%Y-%m-%d %H:%M:%S} UTC (GPS-derived)",
    ]
    if first_us / 1e6 < clock.first_boot_s:
        result.append(
            "Start time is extrapolated before the first valid GPS fix "
            f"at BIN {format_time_us(int(clock.first_boot_s * 1e6))}."
        )
    elif first_us / 1e6 > clock.last_boot_s:
        result.append("Start time is extrapolated beyond the valid GPS fixes.")
    else:
        result.append("Start lies within the valid GPS observation span (fitted time).")
    return [*result, *lines]


def _summary_response(episode):
    if not episode.short_on and not episode.long_on:
        return "No MSG action observed"
    if episode.short_on and episode.long_on:
        if episode.short_mode and episode.long_mode:
            return f"{episode.short_mode[1]} → {episode.long_mode[1]}"
        if episode.mode_at_start and not episode.short_mode and not episode.long_mode:
            return f"Short + long MSG; already {episode.mode_at_start} (no MODE change)"
        return "Short + long MSG; see detailed MODE evidence"
    if episode.short_mode and episode.recovery_mode:
        return f"{episode.short_mode[1]} → {episode.recovery_mode[1]}"
    if episode.mode_at_start and not episode.short_mode:
        return f"Short MSG; already {episode.mode_at_start}"
    return "Short MSG; see detailed MODE evidence"


def format_radio_link_summary(result, log_path, flight_log):
    """A one-screen overview; detail remains available on request."""
    armed = [episode for episode in result.episodes if episode.armed.startswith("armed")]
    uncertain = [episode for episode in result.episodes if episode.armed == "unknown"]
    lines = [
        "Radio Link / RC Failsafe", "=======================",
        f"Log: {Path(log_path).name}", f"Firmware: {result.firmware}",
        *_recording_lines(flight_log),
    ]
    common = _common_configuration([*armed, *uncertain])
    if common:
        lines.extend(["", "Failsafe configuration (PARM at episode onset)",
                      *_configuration_lines(*common)])
    elif armed:
        lines.append("Failsafe configuration varies or is unavailable; see detailed evidence.")
    lines.extend([
        "", f"RC-input loss episodes: {len(armed)} confirmed armed",
        f"Short failsafe actions observed (MSG): {sum(bool(e.short_on) for e in armed)}",
        f"Long failsafe actions observed (MSG): {sum(bool(e.long_on) for e in armed)}",
    ])
    if uncertain:
        lines.append(f"Additional episodes with unknown armed state: {len(uncertain)}")
    if not armed:
        lines.append("No confirmed armed RC-input loss; RF health not assessed.")
    else:
        lines.extend(["", "Aircraft episodes (RCI2 sampled)",
                      "  #  Start     Duration  Observed response"])
        for index, episode in enumerate(armed, start=1):
            start = _time(episode.start)
            duration = _duration(episode.input_duration_s)
            lines.append(f"  {index:<2} {start:<9} {duration:<9} {_summary_response(episode)}")
        if all(episode.armed == "armed throughout" for episode in armed):
            lines.append("All listed episodes: Armed throughout")
        throttle = {episode.throttle for episode in armed}
        if len(throttle) == 1 and None not in throttle:
            output, _ = _throttle_lines(next(iter(throttle)))
            lines.append(output[0].replace(
                "  Commanded throttle PWM", "Common commanded throttle PWM",
            ))
        lines.append("Physical motor activity: Not measurable from BIN")
        assessments = {}
        for index, episode in enumerate(armed, start=1):
            if episode.timing:
                assessments.setdefault(episode.timing.assessment, []).append(index)
        if assessments:
            lines.extend(["", "Timing assessment"])
            for assessment, indexes in assessments.items():
                labels = ", ".join(f"#{index}" for index in indexes)
                lines.append(f"  {labels}: {assessment}")
        for index, episode in enumerate(armed, start=1):
            if episode.short_on is None or episode.warnings:
                lines.extend(["", f"Episode #{index} — qualified RC-input loss"])
                if episode.short_on is None:
                    lines.append(
                        f"  {_duration(episode.input_duration_s)} sampled invalid; "
                        "no short-failsafe MSG assertion observed."
                    )
                if episode.revalid:
                    lines.append(f"  RC input revalidated (RCI2 sampled): {_time(episode.revalid)}")
                if episode.short_on is None and episode.suppression:
                    lines.append(_suppression_line(episode.suppression))
                lines.extend(f"  Diagnostic: {warning}" for warning in episode.warnings)
    lines.append(
        "BIN cannot measure instantaneous RF values at RC-input boundaries or "
        "failsafe actions."
    )
    return "\n".join(lines)


def format_radio_link_report(result, log_path):
    """Present each evidence layer without turning BIN state into RF claims."""
    armed = [episode for episode in result.episodes if episode.armed.startswith("armed")]
    uncertain = [episode for episode in result.episodes if episode.armed == "unknown"]
    reported = [*armed, *uncertain]
    lines = [
        f"Radio Link / RC Failsafe — {Path(log_path).name}",
        f"Firmware: {result.firmware}",
        f"RC-input loss episodes: {len(armed)} confirmed armed",
        f"Short failsafe actions observed (MSG): {sum(bool(e.short_on) for e in armed)}",
        f"Long failsafe actions observed (MSG): {sum(bool(e.long_on) for e in armed)}",
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
        lines.extend(["", f"── Episode #{number} — Aircraft BIN ──"])
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
        if episode.suppression:
            if not episode.throttle:
                lines.extend(["", "Aircraft outputs"])
            lines.append(_suppression_line(episode.suppression))
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
            telemetry.extend([
                "  Telemetry:",
                "    Unavailable throughout the projected aircraft RC-input loss episode.",
            ])
            sensitivity = re.search(r"±([\d.]+) s offset sensitivity", part)
            bound = re.search(r"±([\d.]+) s bounded offset", part)
            if sensitivity:
                telemetry.append(
                    "  Alignment: Result unchanged with "
                    f"±{sensitivity[1]} s clock-offset sensitivity; "
                    "not a proven timing bound."
                )
            elif bound:
                telemetry.append(
                    f"  Alignment: Clock-offset uncertainty bounded to ±{bound[1]} s."
                )
            else:
                telemetry.append(f"  Evidence: {part}")
            telemetry.append("  This telemetry gap is not a measured RF-loss interval.")
        elif part.startswith("EdgeTX CSV telemetry return near projected BIN recovery"):
            telemetry.append("  Telemetry: Returned near projected aircraft RC-input recovery.")
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
        lines.append(f"\nPeriods without usable telemetry: {len(gaps)}")

    for index in sorted(overlay.episode_context.keys() | overlay.episode_rf.keys()):
        lines.extend(["", f"── Episode #{index} — EdgeTX CSV ──"])
        if index in overlay.episode_context:
            lines.extend(_episode_context_lines(overlay.episode_context[index]))
        if index in overlay.episode_rf:
            fields = overlay.episode_rf[index]
            details = "; ".join(
                f"{name} {low:g}–{high:g}" for name, (low, high) in fields.items()
            )
            lines.append(f"  RF observed within bounded episode: {details}.")
            lines.append("  Clock and sample-age bounds established; BIN boundaries unchanged.")
        lines.append("  RF at the aircraft RC-input event: Not measurable from this CSV.")
    if not overlay.episode_rf:
        lines.append(
            "\nNo episode-specific RF minima established. RF observations around "
            "link loss are not measured failsafe thresholds."
        )

    lines.extend([
        "", "Notes:",
        "  RQly, RSSI and SNR are receiver-reported and may be held between CSV "
        "rows; zero/blank telemetry placeholders are excluded from RF measurements.",
        "  A period without usable telemetry is not by itself a separate measured "
        "RF-link failure.",
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
                print(f"{number}. {candidate.name}\n{wrap_report(f'   {hint}')}")
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
                print(wrap_report(f"EdgeTX note: {hint}"))
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
        print("\n" + wrap_report(format_radio_link_summary(result, path, flight_log)))
        try:
            detail = input("\nDetailed BIN evidence? [y/N]: ").strip().casefold()
        except (EOFError, OSError):
            detail = ""
        if detail in ("y", "yes"):
            print("\n" + wrap_report(format_radio_link_report(result, path)))
        overlay = _optional_csv(path, result, flight_log)
        if isinstance(overlay, str):
            print(wrap_report(f"EdgeTX note: {overlay}"))
        elif overlay is not None:
            print(wrap_report(format_edgetx_overlay(overlay)))

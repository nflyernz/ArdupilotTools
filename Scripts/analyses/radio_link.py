"""User-facing BIN-only Plane Radio Link / RC Failsafe review."""

from pathlib import Path

from analyses.log_selector import select_log_input
from core.config import Config
from core.log_reader import FlightReader, UnsupportedFirmwareError
from core.radio_link import RadioLinkDetector
from core.time import format_time_us


def _time(position):
    return format_time_us(position.time_us) if position else "?"


def _duration(seconds):
    return f"{seconds:.3f} s" if seconds is not None else "unavailable"


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


class RadioLinkAnalysisPresentation:
    """Select one log and render BIN-only RC-failsafe evidence."""

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

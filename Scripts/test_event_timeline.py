from pathlib import Path

from core.reader import (
    FlightReader,
    UnsupportedFirmwareError,
)
from core.event_extractor import EventExtractor
from core.landing_window_detector import LandingWindowDetector
from core.modes import mode_name
from core.time import format_time


def landing_end_reason(flight_log, window):
    """
    Determine why a landing window ended.

    The detector's end timestamp is matched against the source
    data so the diagnostic output explains the boundary.
    """

    end_us = int(window.end_us)

    msg = flight_log.get("MSG")
    mode = flight_log.get("MODE")
    gps = flight_log.get("GPS")

    # ------------------------------------------------------------
    # Explicit message boundaries
    # ------------------------------------------------------------

    if not msg.empty:
        rows = msg[msg["TimeUS"] == end_us]

        for row in rows.itertuples(index=False):
            text = str(row.Message)

            if "Throttle disarmed" in text:
                return "DISARM"

            if "Landing aborted" in text:
                return "ABORT"

    # ------------------------------------------------------------
    # Mode change boundary
    # ------------------------------------------------------------

    if not mode.empty:
        rows = mode[mode["TimeUS"] == end_us]

        if not rows.empty:
            value = int(rows.iloc[0]["Mode"])
            return f"MODE: {mode_name(value)}"

    # ------------------------------------------------------------
    # GPS groundspeed boundary
    # ------------------------------------------------------------

    if not gps.empty:
        rows = gps[gps["TimeUS"] == end_us]

        if not rows.empty:
            speed = float(rows.iloc[0]["Spd"])

            if speed < 3.0:
                return "GPS < 3 m/s for 2.0 s"

    # ------------------------------------------------------------
    # Flight-window boundary
    # ------------------------------------------------------------

    return "FLIGHT WINDOW END"


print()
print("Unified Event Timeline")
print("=" * 70)

log_paths = sorted(Path("Logs").glob("*.bin"))

if not log_paths:
    print("No BIN logs found in Logs/")
    raise SystemExit(1)

for log_path in log_paths:

    print()
    print("=" * 70)
    print(f"LOG : {log_path.name}")
    print("=" * 70)

    try:
        flight_log = FlightReader(
            str(log_path)
        ).read()

    except UnsupportedFirmwareError as exc:
        print("STATUS : SKIPPED")
        print(f"Reason : {exc}")
        continue

    firmware = flight_log.firmware_version()
    rngfnd_max = flight_log.param("RNGFND1_MAX")

    if firmware:
        print(
            f"Firmware : {firmware['version']}"
        )
    else:
        print(
            "Firmware : unavailable"
        )

    if rngfnd_max is not None:
        print(
            f"RNGFND1_MAX : "
            f"{float(rngfnd_max):.1f} m"
        )
    else:
        print(
            "RNGFND1_MAX : unavailable"
        )

    print(
        f"Flights : "
        f"{len(flight_log.flights)}"
    )

    for flight_number, flight_window in enumerate(
        flight_log.flights,
        start=1,
    ):

        print()
        print(
            f"Flight {flight_number}"
        )

        print(
            f"Window : "
            f"{format_time(flight_window.start_us)}"
            f" -> "
            f"{format_time(flight_window.end_us)}"
        )

        landing_windows = LandingWindowDetector().detect(
            flight_log,
            flight_window,
        )

        if landing_windows:

            for index, window in enumerate(
                landing_windows,
                start=1,
            ):

                reason = landing_end_reason(
                    flight_log,
                    window,
                )

                print(
                    f"Landing Window {index} : "
                    f"{format_time(window.start_us)}"
                    f" -> "
                    f"{format_time(window.end_us)}"
                )

                print(
                    f"Landing End : {reason}"
                )

        else:
            print(
                "Landing Windows : none"
            )

        events = EventExtractor().extract(
            flight_log,
            flight_window,
        )

        print(
            f"Events : {len(events)}"
        )

        print()

        for event in events:

            print(
                f"{format_time(event.time_us)}  "
                f"{event.event.value:<14}"
                f"{event.detail}"
            )
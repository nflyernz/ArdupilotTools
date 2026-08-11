from pathlib import Path

from core.reader import FlightReader
from core.event_extractor import EventExtractor
from core.landing_window_detector import LandingWindowDetector
from core.time import format_time
from core.modes import mode_name


extractor = EventExtractor()
detector = LandingWindowDetector()

print()
print("Unified Event Timeline")
print("=" * 70)

logs = sorted(Path("Logs").glob("*.bin"))

if not logs:
    print("No BIN logs found in Logs/")
    raise SystemExit(1)


def end_reason(flight_log, window):
    gps = flight_log.get("GPS")
    msg = flight_log.get("MSG")
    mode = flight_log.get("MODE")

    end_us = window.end_us

    #
    # GPS termination.
    #
    end_speed = float(
        detector.config.get(
            "landing_window.end_speed",
            3.0,
        )
    )

    end_seconds = float(
        detector.config.get(
            "landing_window.end_speed_seconds",
            2.0,
        )
    )

    if not gps.empty:
        samples = gps[
            (gps["TimeUS"] <= end_us)
            & (gps["TimeUS"] >= end_us - 5_000_000)
        ]

        if not samples.empty:
            below = samples[samples["Spd"] < end_speed]

            if not below.empty:
                row = below.iloc[-1]
                return (
                    f"GPS < {end_speed:.1f} m/s "
                    f"for {end_seconds:.1f} s "
                    f"(Spd={float(row['Spd']):.2f} m/s)"
                )

    #
    # Landing abort.
    #
    if not msg.empty:
        messages = msg[
            (msg["TimeUS"] >= end_us - 2_000_000)
            & (msg["TimeUS"] <= end_us + 2_000_000)
        ]

        for _, row in messages.iterrows():
            text = str(row["Message"])

            if "landing aborted" in text.lower():
                return f"ABORT: {text}"

    #
    # Mode change.
    #
    if not mode.empty:
        modes = mode[
            (mode["TimeUS"] >= end_us - 2_000_000)
            & (mode["TimeUS"] <= end_us + 2_000_000)
        ]

        for _, row in modes.iterrows():
            name = mode_name(row["ModeNum"])

            if name != "AUTO":
                return f"MODE: {name}"

    return "Unknown"


for log_path in logs:

    print()
    print("=" * 70)
    print(f"LOG : {log_path.name}")
    print("=" * 70)

    flight_log = FlightReader(str(log_path)).read()

    firmware = flight_log.firmware_version()
    rngfnd_max = flight_log.param("RNGFND1_MAX")

    if firmware:
        print(f"Firmware : {firmware['version']}")
    else:
        print("Firmware : unavailable")

    if rngfnd_max is not None:
        print(f"RNGFND1_MAX : {float(rngfnd_max):.1f} m")
    else:
        print("RNGFND1_MAX : unavailable")

    print(f"Flights : {len(flight_log.flights)}")

    for flight_number, flight_window in enumerate(
        flight_log.flights,
        start=1,
    ):

        print()
        print(f"Flight {flight_number}")
        print(
            f"Window : "
            f"{format_time(flight_window.start_us)} -> "
            f"{format_time(flight_window.end_us)}"
        )

        landing_windows = detector.detect(
            flight_log,
            flight_window,
        )

        if landing_windows:

            for number, window in enumerate(
                landing_windows,
                start=1,
            ):

                print(
                    f"Landing Window {number} : "
                    f"{format_time(window.start_us)} -> "
                    f"{format_time(window.end_us)}"
                )

                print(
                    f"Landing End : "
                    f"{end_reason(flight_log, window)}"
                )

        else:
            print("Landing Windows : none")

        events = extractor.extract(
            flight_log,
            flight_window,
        )

        print(f"Events : {len(events)}")
        print()

        for event in events:
            print(
                f"  "
                f"{format_time(event.time_us)}  "
                f"{event.event.value:<14}"
                f"{event.detail}"
            )
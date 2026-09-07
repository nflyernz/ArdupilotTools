from pathlib import Path

from core.log_reader import (
    FlightReader,
    UnsupportedFirmwareError,
)
from core.event_extractor import EventExtractor
from core.landing_window_detector import LandingWindowDetector
from core.modes import mode_name
from core.time import format_time


# Expected regression logs for the v0.4 golden test set.
EXPECTED_REGRESSION_LOGS = {
    "log_11.bin",
    "log_17.bin",
    "log_19.bin",
    "log_26.bin",
}

EXPECTED_VALIDATED_FLIGHTS = 6
EXPECTED_VALIDATED_CASES = 10


# Expected termination reasons from the validated 4.7 logs.
#
# Only representative cases are asserted here. The full
# human-readable timeline is still printed for every flight.
EXPECTED_TERMINATIONS = {
    "log_11.bin": {
        1: [
            "MODE: MANUAL",
            "MODE: AUTOTUNE",
        ],
    },
    "log_17.bin": {
        4: [
            "GPS < 3 m/s for 2.0 s",
        ],
    },
    "log_19.bin": {
        1: [
            "GPS < 3 m/s for 2.0 s",
        ],
    },
    "log_26.bin": {
        2: [
            "ABORT",
            "FLIGHT WINDOW END",
        ],
        3: [
            "ABORT",
            "FLIGHT WINDOW END",
        ],
        4: [
            "ABORT",
            "GPS < 3 m/s for 2.0 s",
        ],
    },
}


def landing_end_reason(flight_log, window):
    """
    Determine why a landing window ended.

    The detector determines the actual boundary. This function
    identifies the source event at that boundary so the diagnostic
    output explains why the window ended.
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
    #
    # Use ModeNum, matching the production detector.
    # ------------------------------------------------------------

    if not mode.empty:
        rows = mode[mode["TimeUS"] == end_us]

        if not rows.empty:
            value = int(rows.iloc[0]["ModeNum"])
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


def assert_expected_terminations(
    log_name,
    flight_number,
    actual_reasons,
):
    """
    Assert the validated termination sequence for a representative
    flight.
    """

    expected = EXPECTED_TERMINATIONS.get(
        log_name,
        {},
    ).get(flight_number)

    if expected is None:
        return

    if actual_reasons != expected:
        raise AssertionError(
            f"{log_name} Flight {flight_number}: "
            f"unexpected landing termination sequence\n"
            f"Expected: {expected}\n"
            f"Actual:   {actual_reasons}"
        )


print()
print("Unified Event Timeline")
print("=" * 70)

log_paths = sorted(Path("Logs").glob("*.bin"))

if not log_paths:
    print("No BIN logs found in Logs/")
    raise SystemExit(1)


validated_flights = 0
validated_cases = 0
skipped_logs = 0
processed_supported_logs = set()


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
        skipped_logs += 1
        continue

    # ------------------------------------------------------------
    # A supported regression log must successfully reach here.
    # ------------------------------------------------------------

    if log_path.name in EXPECTED_REGRESSION_LOGS:
        processed_supported_logs.add(log_path.name)

    firmware = flight_log.firmware_version()

    if firmware:
        print(
            f"Firmware : {firmware['version']}"
        )
    else:
        print(
            "Firmware : unavailable"
        )

    print(
        f"Flights : "
        f"{len(flight_log.flights)}"
    )

    expected_for_log = EXPECTED_TERMINATIONS.get(
        log_path.name,
        {},
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

        actual_reasons = []

        if landing_windows:

            for index, window in enumerate(
                landing_windows,
                start=1,
            ):

                reason = landing_end_reason(
                    flight_log,
                    window,
                )

                actual_reasons.append(reason)

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

        # --------------------------------------------------------
        # Assertions for validated representative flights.
        # --------------------------------------------------------

        if flight_number in expected_for_log:

            assert_expected_terminations(
                log_path.name,
                flight_number,
                actual_reasons,
            )

            validated_flights += 1
            validated_cases += len(
                expected_for_log[flight_number]
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


# ----------------------------------------------------------------
# Final regression validation
# ----------------------------------------------------------------

print()
print("=" * 70)
print("VALIDATION")
print("=" * 70)

missing_regression_logs = (
    EXPECTED_REGRESSION_LOGS
    - processed_supported_logs
)

if missing_regression_logs:
    raise AssertionError(
        "Expected regression logs were not processed: "
        + ", ".join(sorted(missing_regression_logs))
    )

if validated_flights != EXPECTED_VALIDATED_FLIGHTS:
    raise AssertionError(
        f"Unexpected validated flight count: "
        f"expected {EXPECTED_VALIDATED_FLIGHTS}, "
        f"got {validated_flights}"
    )

if validated_cases != EXPECTED_VALIDATED_CASES:
    raise AssertionError(
        f"Unexpected validated case count: "
        f"expected {EXPECTED_VALIDATED_CASES}, "
        f"got {validated_cases}"
    )

if skipped_logs != 0:
    raise AssertionError(
        f"Unexpected skipped logs: {skipped_logs}"
    )

print(
    f"Regression logs  : "
    f"{len(processed_supported_logs)} / "
    f"{len(EXPECTED_REGRESSION_LOGS)}"
)

print(
    f"Validated flights : {validated_flights}"
)

print(
    f"Validated cases   : {validated_cases}"
)

print(
    f"Skipped logs      : {skipped_logs}"
)

print()
print("STATUS : PASS")
print("=" * 70)

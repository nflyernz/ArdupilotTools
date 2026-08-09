from core.reader import FlightReader
from core.landing_window_detector import LandingWindowDetector
from core.landing_attempt_extractor import LandingAttemptExtractor
from core.event_extractor import EventExtractor
from core.time import format_time

flight_log = FlightReader(
    "Logs/log_1.bin"
).read()

#
# Barometric altitude is displayed alongside each event to provide
# context only.
#
# It is NOT currently used for landing detection or validation.
# The displayed altitude is the nearest BARO sample to the event
# timestamp and allows comparison with firmware-generated messages
# such as:
#
#   Landing approach start at ...
#   Flare ...
#   Rangefinder engaged ...
#
# Differences between BARO altitude and values embedded in firmware
# messages are expected and are currently being investigated.
#

baro = flight_log.get("BARO")


def baro_altitude(time_us):
    """
    Return the nearest BARO altitude for the supplied timestamp.

    Returns None if BARO telemetry is unavailable.
    """

    if baro is None or baro.empty:
        return None

    idx = (
        baro["TimeUS"]
        .sub(time_us)
        .abs()
        .idxmin()
    )

    return float(
        baro.loc[idx, "Alt"]
    )


print()
print("Landing Attempt Timelines")
print("-" * 70)

for flight_number, flight_window in enumerate(
    flight_log.flights,
    start=1,
):

    landing_windows = LandingWindowDetector().detect(
        flight_log,
        flight_window,
    )

    print()
    print(f"Flight {flight_number}")

    if not landing_windows:

        print("  LandingWindows : 0")
        continue

    for landing_number, landing_window in enumerate(
        landing_windows,
        start=1,
    ):

        attempts = LandingAttemptExtractor(
            flight_log
        ).extract(
            landing_window,
        )

        print()
        print(
            f"  LandingWindow {landing_number}"
        )

        print(
            f"    Attempts : {len(attempts)}"
        )

        for attempt_number, attempt in enumerate(
            attempts,
            start=1,
        ):

            print()
            print(
                f"    Attempt {attempt_number}"
            )

            print(
                "    " + "-" * 60
            )

            events = EventExtractor().extract(
                flight_log,
                attempt,
            )

            if not events:

                print(
                    "      No events"
                )
                continue

            previous_time = None

            for event in events:

                altitude = baro_altitude(
                    event.time_us
                )

                if altitude is None:

                    altitude_text = "------"

                else:

                    altitude_text = (
                        f"{altitude:5.1f}m"
                    )

                if previous_time is None:

                    delta_text = " ----- "

                else:

                    delta = (
                        event.time_us
                        - previous_time
                    ) / 1_000_000.0

                    delta_text = (
                        f"+{delta:5.2f}s"
                    )

                previous_time = event.time_us

                print(
                    f"      "
                    f"{format_time(event.time_us)}  "
                    f"{altitude_text:<7} "
                    f"{delta_text:<8} "
                    f"{event.event.value:<14}"
                    f"{event.detail}"
                )
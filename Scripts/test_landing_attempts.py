from core.reader import FlightReader
from core.landing_window_detector import LandingWindowDetector
from core.landing_attempt_extractor import LandingAttemptExtractor
from core.time import format_time

flight_log = FlightReader(
    "Logs/log_17.bin"
).read()

print()
print("Landing Attempts")
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

        print(
            f"  LandingWindow {landing_number}"
        )

        print(
            f"    Window   : "
            f"{format_time(landing_window.start_us)} -> "
            f"{format_time(landing_window.end_us)}"
        )

        attempts = LandingAttemptExtractor(
            flight_log
        ).extract(
            landing_window
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
                f"      Attempt {attempt_number}"
            )

            print(
                f"        Start : "
                f"{format_time(attempt.start_us)}"
            )

            print(
                f"        End   : "
                f"{format_time(attempt.end_us)}"
            )

            print(
                f"        Duration : "
                f"{(attempt.end_us - attempt.start_us) / 1_000_000:.2f} s"
            )

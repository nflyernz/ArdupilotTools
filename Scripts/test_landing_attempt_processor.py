from core.config import Config
from core.landing_attempt_extractor import (
    LandingAttemptExtractor,
)
from core.landing_attempt_processor import (
    LandingAttemptProcessor,
)
from core.landing_window_detector import (
    LandingWindowDetector,
)
from core.log_reader import FlightReader
from core.time import format_time


LOG_PATH = "Logs/log_26.bin"


def fmt_value(
    value,
    decimals=2,
    suffix="",
):
    if value is None:
        return "Unavailable"

    return (
        f"{value:.{decimals}f}"
        f"{suffix}"
    )


def fmt_time(
    time_us,
):
    if time_us is None:
        return "Unavailable"

    return format_time(
        time_us
    )


def end_reason_label(
    reason,
):
    labels = {
        "gps": "GPS stop",
        "abort": "Landing aborted",
        "disarm": "Throttle disarmed",
        "mode": "Mode change",
        "flight_window_end": (
            "Flight ended before landing stop detected"
        ),
    }

    if reason is None:
        return "Unavailable"

    return labels.get(
        reason,
        reason,
    )


def print_attempt(
    landing_number,
    attempt_number,
    analysis,
):
    attempt = analysis.attempt

    print()
    print(
        f"Landing {landing_number} "
        f"Attempt {attempt_number}"
    )
    print("-" * 70)

    print(
        f"Window                  "
        f"{fmt_time(attempt.start_us)}"
        f" -> "
        f"{fmt_time(attempt.end_us)}"
    )

    print(
        f"Duration                "
        f"{fmt_value(
            analysis.duration_s,
            2,
            ' s',
        )}"
    )

    print()
    print("APPROACH")
    print()

    print(
        f"Approach altitude       "
        f"{fmt_value(
            analysis.approach_start_altitude,
            1,
            ' m',
        )}"
    )

    print(
        f"Glide slope             "
        f"{fmt_value(
            analysis.glide_slope_degrees,
            1,
            ' deg',
        )}"
    )

    print()
    print("PREFLARE")
    print()

    print(
        f"Time                    "
        f"{fmt_time(
            analysis.preflare_time_us
        )}"
    )

    print(
        f"Preflare height         "
        f"{fmt_value(
            analysis.preflare_altitude,
            2,
            ' m',
        )}"
    )

    print(
        f"Airspeed                "
        f"{fmt_value(
            analysis.preflare_airspeed,
            2,
            ' m/s',
        )}"
    )

    print(
        f"GPS groundspeed         "
        f"{fmt_value(
            analysis.preflare_gps_speed,
            2,
            ' m/s',
        )}"
    )

    print(
        f"Sink rate               "
        f"{fmt_value(
            analysis.preflare_sink_rate,
            2,
            ' m/s',
        )}"
    )

    print()
    print("FLARE")
    print()

    print(
        f"Time                    "
        f"{fmt_time(
            analysis.flare_time_us
        )}"
    )

    print(
        f"Flare-timing height     "
        f"{fmt_value(
            analysis.flare_altitude,
            2,
            ' m',
        )}"
    )

    print(
        f"Sink rate               "
        f"{fmt_value(
            analysis.flare_sink_rate,
            2,
            ' m/s',
        )}"
    )

    print(
        f"Airspeed                "
        f"{fmt_value(
            analysis.flare_airspeed,
            2,
            ' m/s',
        )}"
    )

    print(
        f"GPS groundspeed         "
        f"{fmt_value(
            analysis.flare_gps_speed,
            2,
            ' m/s',
        )}"
    )

    print(
        f"Flare distance to target "
        f"{fmt_value(
            analysis.flare_distance,
            1,
            ' m',
        )}"
    )

    #
    # Optional rangefinder evidence.
    #
    has_rangefinder = any(
        value is not None
        for value in (
            analysis.rangefinder_first_nonzero_time_us,
            analysis.rangefinder_first_in_range_time_us,
            analysis.rangefinder_continuous_time_us,
        )
    )

    if has_rangefinder:

        print()
        print("RANGEFINDER")
        print()

        print(
            f"First non-zero          "
            f"{fmt_time(
                analysis.rangefinder_first_nonzero_time_us
            )}"
        )

        print(
            f"First distance          "
            f"{fmt_value(
                analysis.rangefinder_first_nonzero_distance,
                2,
                ' m',
            )}"
        )

        print(
            f"First in range          "
            f"{fmt_time(
                analysis.rangefinder_first_in_range_time_us
            )}"
        )

        print(
            f"In-range distance       "
            f"{fmt_value(
                analysis.rangefinder_first_in_range_distance,
                2,
                ' m',
            )}"
        )

        print(
            f"Continuous from         "
            f"{fmt_time(
                analysis.rangefinder_continuous_time_us
            )}"
        )

    print()
    print("LANDING / ROLLOUT COMPLETION")
    print()

    if (
        analysis.gps_stop_time_us
        is not None
    ):

        print(
            f"GPS stop                "
            f"{fmt_time(
                analysis.gps_stop_time_us
            )}"
        )

        print(
            f"Flare -> stop           "
            f"{fmt_value(
                analysis.flare_to_gps_stop_s,
                2,
                ' s',
            )}"
        )

        print(
            f"Distance from target    "
            f"{fmt_value(
                analysis.landing_end_target_distance_m,
                1,
                ' m',
            )}"
        )

    print(
        f"End reason              "
        f"{end_reason_label(
            analysis.end_reason
        )}"
    )


flight_log = FlightReader(
    LOG_PATH
).read()

config = Config(
    "Config/sensors.yaml"
)

print()
print("Landing Analysis Prototype")
print("=" * 70)

for flight_number, flight_window in enumerate(
    flight_log.flights,
    start=1,
):

    landing_windows = (
        LandingWindowDetector().detect(
            flight_log,
            flight_window,
        )
    )

    if not landing_windows:
        continue

    print()
    print("=" * 70)
    print(
        f"FLIGHT {flight_number}"
    )
    print("=" * 70)

    for landing_number, landing_window in enumerate(
        landing_windows,
        start=1,
    ):

        attempts = LandingAttemptExtractor(
            flight_log
        ).extract(
            landing_window
        )

        for attempt_number, attempt in enumerate(
            attempts,
            start=1,
        ):

            analysis = LandingAttemptProcessor(
                flight_log=flight_log,
                flight_window=flight_window,
                landing_window=landing_window,
                attempt=attempt,
                config=config,
            ).build()

            print_attempt(
                landing_number,
                attempt_number,
                analysis,
            )

print()
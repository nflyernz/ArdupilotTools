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
from core.scope import filter_telemetry
from core.time import format_time


LOGS = [
    "Logs/log_11.bin",
    "Logs/log_17.bin",
    "Logs/log_19.bin",
    "Logs/log_26.bin",
]

PRE_FLARE_US = 1_000_000
POST_GPS_STOP_US = 1_000_000


def nearest_value(
    telemetry,
    field,
    target_time_us,
):
    """
    Return the nearest telemetry value to target_time_us.

    No interpolation is performed.
    """

    if telemetry is None or telemetry.empty:
        return None

    if (
        "TimeUS" not in telemetry.columns
        or field not in telemetry.columns
    ):
        return None

    valid = telemetry[
        telemetry[field].notna()
    ]

    if valid.empty:
        return None

    offsets = (
        valid["TimeUS"]
        - target_time_us
    ).abs()

    index = offsets.idxmin()

    try:
        return float(
            valid.loc[index, field]
        )

    except (
        TypeError,
        ValueError,
    ):
        return None


def fmt(value, decimals=3):
    if value is None:
        return "-"

    return f"{value:.{decimals}f}"


config = Config(
    "Config/sensors.yaml"
)

print()
print("Touchdown Evidence")
print("=" * 78)

gps_ended = 0

for log_path in LOGS:

    flight_log = FlightReader(
        log_path
    ).read()

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

        for landing_number, landing_window in enumerate(
            landing_windows,
            start=1,
        ):

            if (
                landing_window.end_reason
                != "gps"
            ):
                continue

            attempts = (
                LandingAttemptExtractor(
                    flight_log
                ).extract(
                    landing_window
                )
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

                if analysis.flare_time_us is None:
                    continue

                gps_ended += 1

                trace_start_us = max(
                    attempt.start_us,
                    (
                        analysis.flare_time_us
                        - PRE_FLARE_US
                    ),
                )

                trace_end_us = min(
                    flight_window.end_us,
                    (
                        landing_window.end_us
                        + POST_GPS_STOP_US
                    ),
                )

                class TraceWindow:
                    start_us = trace_start_us
                    end_us = trace_end_us

                trace_window = TraceWindow()

                gps = filter_telemetry(
                    flight_log.get("GPS"),
                    trace_window,
                )

                baro = filter_telemetry(
                    flight_log.get("BARO"),
                    trace_window,
                )

                rfnd = filter_telemetry(
                    flight_log.get("RFND"),
                    trace_window,
                )

                #
                # Use GPS timestamps as the common display timeline.
                #
                # GPS is guaranteed to exist for a GPS-ended
                # LandingWindow.
                #
                if gps is None or gps.empty:
                    continue

                print()
                print(
                    f"Log      : {log_path}"
                )

                print(
                    f"Flight   : {flight_number}"
                )

                print(
                    f"Landing  : {landing_number}"
                )

                print(
                    f"Attempt  : {attempt_number}"
                )

                print(
                    f"Flare    : "
                    f"{format_time(analysis.flare_time_us)}"
                )

                print(
                    f"GPS stop : "
                    f"{format_time(landing_window.end_us)}"
                )

                print(
                    f"Trace    : "
                    f"{format_time(trace_start_us)}"
                    f" -> "
                    f"{format_time(trace_end_us)}"
                )

                print()
                print(
                    "Time        Rel(s)   "
                    "GPS Spd    BARO Alt   RFND Dist"
                )
                print(
                    "-" * 58
                )

                for row in gps.itertuples():

                    time_us = int(
                        row.TimeUS
                    )

                    rel_s = (
                        time_us
                        - analysis.flare_time_us
                    ) / 1_000_000

                    try:
                        gps_speed = float(
                            row.Spd
                        )
                    except (
                        TypeError,
                        ValueError,
                    ):
                        gps_speed = None

                    baro_alt = nearest_value(
                        baro,
                        "Alt",
                        time_us,
                    )

                    rfnd_dist = nearest_value(
                        rfnd,
                        "Dist",
                        time_us,
                    )

                    print(
                        f"{format_time(time_us):<11}"
                        f"{rel_s:>7.2f}   "
                        f"{fmt(gps_speed):>7}   "
                        f"{fmt(baro_alt):>8}   "
                        f"{fmt(rfnd_dist):>9}"
                    )

                print()
                print(
                    "Reference"
                )
                print(
                    "-" * 58
                )

                print(
                    f"Flare time       : "
                    f"{format_time(analysis.flare_time_us)}"
                )

                print(
                    f"Flare altitude   : "
                    f"{analysis.flare_altitude}"
                )

                print(
                    f"Flare sink rate  : "
                    f"{analysis.flare_sink_rate}"
                )

                print(
                    f"Flare airspeed   : "
                    f"{analysis.flare_airspeed}"
                )

                print(
                    f"Flare GPS speed  : "
                    f"{analysis.flare_gps_speed}"
                )

                print(
                    f"GPS stop time    : "
                    f"{format_time(landing_window.end_us)}"
                )

print()
print("=" * 78)

print(
    f"GPS-ended landings inspected : "
    f"{gps_ended}"
)

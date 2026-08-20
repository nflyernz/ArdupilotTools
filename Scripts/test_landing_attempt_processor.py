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


LOG_PATH = "Logs/log_17.bin"


flight_log = FlightReader(
    LOG_PATH
).read()

config = Config(
    "Config/sensors.yaml"
)

print()
print("Landing Attempt Analysis")
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
    print(
        f"Flight {flight_number}"
    )

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

            print()
            print(
                f"  Landing {landing_number} "
                f"Attempt {attempt_number}"
            )

            print(
                f"    Window     : "
                f"{format_time(attempt.start_us)}"
                f" -> "
                f"{format_time(attempt.end_us)}"
            )

            print(
                f"    Duration   : "
                f"{analysis.duration_s:.2f} s"
            )

            print()
            print("    Geometry")

            print(
                f"      Approach altitude : "
                f"{analysis.approach_start_altitude}"
            )

            print(
                f"      Glide slope       : "
                f"{analysis.glide_slope_degrees}"
            )

            print()
            print("    Preflare")

            print(
                f"      Time              : "
                f"{format_time(analysis.preflare_time_us) if analysis.preflare_time_us is not None else 'Unavailable'}"
            )

            print(
                f"      Altitude          : "
                f"{analysis.preflare_altitude}"
            )

            print(
                f"      Airspeed          : "
                f"{analysis.preflare_airspeed}"
            )

            print(
                f"      GPS speed         : "
                f"{analysis.preflare_gps_speed}"
            )
            
            print(
                f"      Sink rate         : "
                f"{analysis.preflare_sink_rate}"
            )

            print()
            print("    Flare")

            print(
                f"      Time              : "
                f"{format_time(analysis.flare_time_us) if analysis.flare_time_us is not None else 'Unavailable'}"
            )

            print(
                f"      Altitude          : "
                f"{analysis.flare_altitude}"
            )

            print(
                f"      Sink rate         : "
                f"{analysis.flare_sink_rate}"
            )

            print(
                f"      Airspeed          : "
                f"{analysis.flare_airspeed}"
            )

            print(
                f"      GPS speed         : "
                f"{analysis.flare_gps_speed}"
            )

            print(
                f"      Distance          : "
                f"{analysis.flare_distance}"
            )

            print()
            print("    Rangefinder")

            print(
                f"      First non-zero    : "
                f"{format_time(analysis.rangefinder_first_nonzero_time_us) if analysis.rangefinder_first_nonzero_time_us is not None else 'Unavailable'}"
            )

            print(
                f"      First distance    : "
                f"{analysis.rangefinder_first_nonzero_distance}"
            )

            print(
                f"      First in range    : "
                f"{format_time(analysis.rangefinder_first_in_range_time_us) if analysis.rangefinder_first_in_range_time_us is not None else 'Unavailable'}"
            )

            print(
                f"      In-range distance : "
                f"{analysis.rangefinder_first_in_range_distance}"
            )

            print(
                f"      Continuous from   : "
                f"{format_time(analysis.rangefinder_continuous_time_us) if analysis.rangefinder_continuous_time_us is not None else 'Unavailable'}"
            )

            print(
                f"      Continuous samples: "
                f"{analysis.rangefinder_continuous_samples}"
            )

            print(
                f"      Dropout events    : "
                f"{analysis.rangefinder_disengage_events}"
            )

            print(
                f"      Last dropout      : "
                f"{format_time(analysis.rangefinder_last_disengage_time_us) if analysis.rangefinder_last_disengage_time_us is not None else 'Unavailable'}"
            )

            print(
                f"      Last dropout dist : "
                f"{analysis.rangefinder_last_disengage_distance}"
            )
            
            print()
            print("    Landing / rollout completion")
            
            print(
                f"      GPS stop time     : "
                f"{format_time(analysis.gps_stop_time_us) if analysis.gps_stop_time_us is not None else 'Unavailable'}"
            )
            
            print(
                f"      Speed threshold   : "
                f"{analysis.gps_stop_speed_limit}"
            )
            
            print(
                f"      Persistence       : "
                f"{analysis.gps_stop_persistence_s}"
            )
            
            print(
                f"      Flare -> GPS stop : "
                f"{analysis.flare_to_gps_stop_s}"
            )

            print()
            print(
                f"    End reason : "
                f"{analysis.end_reason}"
            )

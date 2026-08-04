from analyses.landing import LandingAnalysis
from core.reader import FlightReader


flight_log = FlightReader(
    "Logs/log_17.bin"
).read()

analysis = LandingAnalysis()

print()
print("Direct LandingAnalysis.analyse()")
print("-" * 70)

for flight_index, flight_window in enumerate(
    flight_log.flights,
    start=1,
):

    result = analysis.analyse(
        flight_log,
        flight_window,
    )

    print()
    print(f"Flight {flight_index}")

    print(
        f"  FlightWindow       : "
        f"{result.flight_window.start_us} -> "
        f"{result.flight_window.end_us}"
    )

    if result.sensor_health_window is None:

        print(
            "  SensorHealthWindow : None"
        )

    else:

        print(
            f"  SensorHealthWindow : "
            f"{result.sensor_health_window.start_us} -> "
            f"{result.sensor_health_window.end_us}"
        )

    print(
        f"  LandingWindows     : "
        f"{len(result.landing_windows)}"
    )

    print(
        f"  Airspeed Health    : "
        f"{'None' if result.sensor_health is None else 'Present'}"
    )

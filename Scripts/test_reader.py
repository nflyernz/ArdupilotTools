from core.reader import FlightReader
from core.sensor_health_window import SensorHealthWindowDetector


flight = FlightReader("Logs/log_17.bin").read()

print(f"Messages   : {len(flight.messages)}")
print(f"Parameters : {len(flight.parameters)}")
print(f"Flights    : {len(flight.flights)}")
print(f"Segments   : {len(flight.segments)}")

print()

for i, flight_window in enumerate(flight.flights, start=1):

    sensor_window = SensorHealthWindowDetector().detect(
        flight,
        flight_window,
    )

    duration = (
        flight_window.end_us - flight_window.start_us
    ) / 1e6

    #
    # Include every segment that overlaps this flight.
    #
    segments = [
        s for s in flight.segments
        if (
            s.end_us >= flight_window.start_us
            and
            s.start_us <= flight_window.end_us
        )
    ]

    print(f"Flight {i}")
    print(f"  Duration : {duration:.1f}s")
    print(f"  Segments : {len(segments)}")
    print(f"  Flight   : {flight_window.start_us:,} -> {flight_window.end_us:,}")
    print(f"  Sensor   : {sensor_window.start_us:,} -> {sensor_window.end_us:,}")

    print("  Modes")

    for s in segments:

        rel_start = (
            s.start_us - flight_window.start_us
        ) / 1e6

        rel_end = (
            s.end_us - flight_window.start_us
        ) / 1e6

        print(
            f"    {s.mode:<10}"
            f"{rel_start:8.1f}s"
            f" -> "
            f"{rel_end:8.1f}s"
        )

    print()
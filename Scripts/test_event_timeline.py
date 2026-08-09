from core.reader import FlightReader
from core.event_extractor import EventExtractor
from core.time import format_time

flight_log = FlightReader(
    "Logs/log_26.bin"
).read()

print()
print("Unified Event Timeline")
print("-" * 70)

extractor = EventExtractor()

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

    events = extractor.extract(
        flight_log,
        flight_window,
    )

    print(
        f"Events : {len(events)}"
    )
    print()

    if not events:

        print("  No events")
        continue

    for event in events:

        print(
            f"  "
            f"{format_time(event.time_us)}  "
            f"{event.event.value:<14}"
            f"{event.detail}"
        )

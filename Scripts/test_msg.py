from core.event_extractor import EventExtractor
from core.log_reader import FlightReader


flight_log = FlightReader(
    "Logs/log_17.bin"
).read()

extractor = EventExtractor()

print()
print("Flight-scoped MSG Events")
print("-" * 70)

if not flight_log.flights:

    print("No flight windows found.")
    raise SystemExit


for i, flight_window in enumerate(flight_log.flights, start=1):

    events = extractor.extract(
        flight_log,
        flight_window,
    )

    print()
    print(f"Flight {i}")
    print(
        f"  Window : "
        f"{flight_window.start_us / 1e6:.3f} -> "
        f"{flight_window.end_us / 1e6:.3f} s"
    )
    print(f"  Events : {len(events)}")
    print()

    for event in events:

        print(
            f"    {event.time_us / 1e6:9.3f}  "
            f"{event.event.value:12}  "
            f"{event.detail}"
        )
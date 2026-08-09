from core.reader import FlightReader
from core.event_extractor import EventExtractor
from core.time import format_time

flight_log = FlightReader(
    "Logs/log_26.bin"
).read()

firmware = flight_log.firmware_version()
rngfnd_max = flight_log.param("RNGFND1_MAX")

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

    if firmware:
        print(
            f"Firmware : {firmware['version']}"
        )
    else:
        print("Firmware : unavailable")

    if rngfnd_max is not None:
        print(
            f"RNGFND1_MAX : {float(rngfnd_max):.1f} m"
        )
    else:
        print("RNGFND1_MAX : unavailable")

    print(
        f"Window : "
        f"{format_time(flight_window.start_us)} -> "
        f"{format_time(flight_window.end_us)}"
    )

    events = extractor.extract(
        flight_log,
        flight_window,
    )

    print(f"Events : {len(events)}")
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
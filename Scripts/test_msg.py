from core.event_extractor import EventExtractor
from core.reader import FlightReader

flight = FlightReader(
    "Logs/log_17_2026-6-28-10-05-44.bin"
).read()

events = EventExtractor().extract(flight)

print(f"{len(events)} events\n")

for e in events:
    print(f"{e.time_us/1e6:8.3f}  {e.event.value:12}  {e.detail}")

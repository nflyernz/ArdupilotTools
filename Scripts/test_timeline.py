from core.reader import FlightReader
from core.timeline import LandingTimeline


flight = FlightReader(
    "Logs/log_19_2026-7-5-09-43-10.bin"
).read()

timeline = LandingTimeline(flight)

events = timeline.build()

print()

print("Landing Timeline")
print("-" * 70)

t0 = events[0].time_us

for e in events:

    t = (e.time_us - t0) / 1e6

    print(f"{t:8.3f}  {e.event:15} {e.value}")

from core.reader import FlightReader
from core.landwindow import LandingWindows
from core.timeline import LandingTimeline


flight = FlightReader(
    "Logs/log_17_2026-6-28-10-05-44.bin"
).read()

windows = LandingWindows(flight).find()

if not windows:

    print("No landing windows found.")

    raise SystemExit

timeline = LandingTimeline(
    flight,
    windows[0],
).build()

print()

print("Landing Timeline")
print("-" * 70)

for event in timeline:

    print(
        f"{event.time_us / 1e6:9.3f}  "
        f"{event.event.value:<20}"
        f"{event.detail}"
    )

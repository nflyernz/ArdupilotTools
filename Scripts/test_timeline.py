from core.reader import FlightReader
from core.landing_window_detector import LandingWindowDetector
from core.timeline import LandingTimeline
from core.config import Config

config = Config("Config/landing.yaml")


flight = FlightReader(
    "Logs/log_17.bin"
).read()

if not flight.flights:

    print("No flight windows found.")

    raise SystemExit

flight_window = flight.flights[0]

detector = LandingWindowDetector()

windows = detector.detect(
    flight,
    flight_window,
)

if not windows:

    print("No landing windows found.")

    raise SystemExit

timeline = LandingTimeline(
    flight,
    windows[0],
    config,
).build()

print()

print("Landing Timeline")
print("-" * 70)

print(
    f"Landing Start : {windows[0].start_us / 1e6:.3f} s"
)

print(
    f"Landing End   : {windows[0].end_us / 1e6:.3f} s"
)

print()

for event in timeline:

    print(
        f"{event.time_us / 1e6:9.3f}  "
        f"{event.event.value:<20}"
        f"{event.detail}"
    )
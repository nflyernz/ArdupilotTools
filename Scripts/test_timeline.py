from core.log_reader import FlightReader
from core.landing_window_detector import LandingWindowDetector
from core.timeline import LandingTimeline
from core.config import Config


config = Config("Config/sensors.yaml")

flight_log = FlightReader(
    "Logs/log_17.bin"
).read()

if not flight_log.flights:

    print("No flight windows found.")
    raise SystemExit


flight_window = flight_log.flights[0]

detector = LandingWindowDetector()

windows = detector.detect(
    flight_log,
    flight_window,
)

if not windows:

    print("No landing windows found.")
    raise SystemExit


landing_window = windows[0]

timeline = LandingTimeline(
    flight_log,
    flight_window,
    landing_window,
    config,
).build()


print()
print("Landing Timeline")
print("-" * 70)

print(
    f"Flight Window : "
    f"{flight_window.start_us / 1e6:.3f} -> "
    f"{flight_window.end_us / 1e6:.3f} s"
)

print(
    f"Landing Start : {landing_window.start_us / 1e6:.3f} s"
)

print(
    f"Landing End   : {landing_window.end_us / 1e6:.3f} s"
)

print()

for event in timeline:

    print(
        f"{event.time_us / 1e6:9.3f}  "
        f"{event.event.value:<20}"
        f"{event.detail}"
    )
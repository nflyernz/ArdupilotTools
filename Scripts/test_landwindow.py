from core.reader import FlightReader
from core.landing_window_detector import LandingWindowDetector


flight = FlightReader(
    "Logs/log_17.bin"
).read()

if not flight.flights:

    print("No flight windows found.")
    raise SystemExit

flight_window = flight.flights[0]

windows = LandingWindowDetector().detect(
    flight,
    flight_window,
)

print()

print("Landing Windows")
print("-" * 70)

for i, w in enumerate(windows, start=1):

    print(f"Landing {i}")

    print(f"  Start        : {w.start_us / 1e6:.3f} s")

    print(f"  End          : {w.end_us / 1e6:.3f} s")

    duration_s = (w.end_us - w.start_us) / 1e6

    print(f"  Duration     : {duration_s:.2f} s")

    print()

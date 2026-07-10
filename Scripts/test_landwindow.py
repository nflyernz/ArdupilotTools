from core.reader import FlightReader
from core.landwindow import LandingWindows


flight = FlightReader(
    "Logs/log_17_2026-6-28-10-05-44.bin"
).read()

windows = LandingWindows(flight).find()

print()

print("Landing Windows")
print("-" * 70)

for i, w in enumerate(windows, start=1):

    print(f"Landing {i}")

    print(f"  Start        : {w.start_us / 1e6:.3f} s")

    print(f"  End          : {w.end_us / 1e6:.3f} s")

    print(f"  Duration     : {w.duration_s:.2f} s")

    print(f"  Long         : {w.is_long}")

    print(f"  Closed       : {w.closed}")

    print(f"  Close reason : {w.close_reason}")

    print()

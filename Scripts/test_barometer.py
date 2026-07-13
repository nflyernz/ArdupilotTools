from core.reader import FlightReader
from core.config import Config
from core.landwindow import LandingWindows
from core.barometer import BarometerEvents


flight = FlightReader(
    "Logs/log_19_2026-7-5-09-43-10.bin"
).read()

config = Config("Config/landing.yaml")

windows = LandingWindows(flight).find()

if not windows:

    print("No landing windows found.")
    raise SystemExit

window = windows[0]

events = BarometerEvents(
    flight,
    window,
    config
).find()

baro = flight.get("BARO")

baro = baro[
    (baro.TimeUS >= window.start_us)
    &
    (baro.TimeUS <= window.end_us)
]

rate = 0.0

if len(baro) > 1:

    dt = (
        baro.TimeUS.iloc[-1]
        - baro.TimeUS.iloc[0]
    ) / 1e6

    rate = len(baro) / dt

print()
print("Barometer Events")
print("-" * 70)

print(
    f"Landing Start : "
    f"{window.start_us/1e6:.1f} s"
)

print(
    f"Landing End   : "
    f"{window.end_us/1e6:.1f} s"
)

print()

print(
    f"BARO Rate     : "
    f"{rate:.1f} Hz"
)

print()

print("Published Events")
print("-" * 70)

for event in events:

    print(
        f"{event.time_us/1e6:10.3f}  "
        f"{event.name}"
    )

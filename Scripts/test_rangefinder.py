from core.reader import FlightReader
from core.config import Config
from core.landwindow import LandingWindows
from core.rangefinder import RangefinderEvents


flight = FlightReader(
    "Logs/log_6_2026-3-22-10-13-50.bin"
).read()

config = Config("Config/landing.yaml")

windows = LandingWindows(flight).find()

if not windows:

    print("No landing windows found.")
    raise SystemExit

window = windows[0]

events = RangefinderEvents(

    flight,

    window,

    config,

).build()

print()
print("Rangefinder Events")
print("-" * 70)

print(
    f"Landing Start : {window.start_us / 1e6:.3f} s"
)

print(
    f"Landing End   : {window.end_us / 1e6:.3f} s"
)

print()

if flight.has_param("RNGFND1_MAX"):

    print(
        f"RNGFND1_MAX   : {flight.param('RNGFND1_MAX'):.2f} m"
    )

else:

    print("RNGFND1_MAX   : Not available")

print()

rfnd = flight.get("RFND")

if len(rfnd) > 1:

    dt = rfnd["TimeUS"].diff().dropna().median()

    if dt > 0:

        rate = 1e6 / dt

        print(
            f"RFND Rate     : {rate:.1f} Hz"
        )

print()

print("Published Events")
print("-" * 70)

if not events:

    print("No events.")

else:

    for event in events:

        print(

            f"{event.time_us / 1e6:10.3f}  "

            f"{event.event.value:<24}"

            f"{event.detail}"

        )

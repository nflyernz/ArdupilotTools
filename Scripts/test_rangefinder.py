from core.log_reader import FlightReader
from core.config import Config
from core.landing_window_detector import LandingWindowDetector
from core.rangefinder import RangefinderEvents


flight_log = FlightReader(
    "Logs/log_17.bin"
).read()

config = Config("Config/sensors.yaml")

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

events = RangefinderEvents(
    flight_log,
    flight_window,
    landing_window,
    config,
).build()

print()
print("Rangefinder Events")
print("-" * 70)

print(
    f"Landing Start : {landing_window.start_us / 1e6:.3f} s"
)

print(
    f"Landing End   : {landing_window.end_us / 1e6:.3f} s"
)

print(
    f"Duration      : "
    f"{(landing_window.end_us - landing_window.start_us) / 1e6:.2f} s"
)

print()

if flight_log.has_param("RNGFND1_MAX"):

    print(
        f"RNGFND1_MAX   : "
        f"{flight_log.param('RNGFND1_MAX'):.2f} m"
    )

else:

    print("RNGFND1_MAX   : Not available")

print()

rfnd = flight_log.get("RFND")

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
from core.log_reader import FlightReader
from core.scope import filter_telemetry


flight_log = FlightReader(
    "Logs/log_17.bin"
).read()

land = flight_log.get("LAND")

print()
print("Flight-scoped LAND.stage transitions")
print("-" * 70)

if not flight_log.flights:

    print("No flight windows found.")
    raise SystemExit


for i, flight_window in enumerate(flight_log.flights, start=1):

    flight_land = filter_telemetry(
        land,
        flight_window,
    )

    print()
    print(f"Flight {i}")
    print(
        f"  Window : "
        f"{flight_window.start_us / 1e6:.3f} -> "
        f"{flight_window.end_us / 1e6:.3f} s"
    )
    print(f"  LAND records : {len(flight_land)}")
    print()

    if flight_land.empty:

        print("    No LAND records.")
        continue

    previous = None

    for _, row in flight_land.iterrows():

        stage = int(row["stage"])

        if stage != previous:

            print(
                f"    {row['TimeUS'] / 1e6:9.3f} s   "
                f"{previous} -> {stage}"
            )

            previous = stage
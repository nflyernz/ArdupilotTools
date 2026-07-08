from core.reader import FlightReader

flight = FlightReader(
    "Logs/log_17_2026-6-28-10-05-44.bin"
).read()

land = flight.get("LAND")

print()
print("LAND.stage transitions")
print("-" * 70)

previous = None

for _, row in land.iterrows():

    stage = int(row.stage)

    if stage != previous:

        print(
            f"{row.TimeUS/1e6:10.3f} s   "
            f"{previous} -> {stage}"
        )

        previous = stage

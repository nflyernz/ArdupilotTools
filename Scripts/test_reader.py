from core.reader import FlightReader


reader = FlightReader(
    "Logs/log_19_2026-7-5-09-43-10.bin"
)

flight = reader.read()


print("\nAvailable Messages")
print("-" * 60)

for name in flight.message_types():
    df = flight.get(name)
    print(f"{name:6} {len(df):8} records")


print("\nParameters")
print("-" * 60)

if flight.parameters:

    for name in sorted(flight.parameters):
        print(f"{name:20} {flight.parameters[name]}")

else:
    print("No parameter file loaded.")


print()

print("RFND Columns")
print("-" * 60)

rfnd = flight.get("RFND")

print(rfnd.columns)

print()

print(rfnd.head())

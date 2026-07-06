from core.reader import FlightReader

reader = FlightReader(
    "Logs/log_19_2026-7-5-09-43-10.bin"
)

log = reader.read()

print("Message types:")
print(log.message_types())

print()

print("Has TECS?")
print(log.has("TECS"))

print()

print("TECS:")
print(log.get("TECS").head())

print()

print("Time (seconds):")
print(log.seconds("TECS").head())

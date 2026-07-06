from core.reader import FlightReader

log = FlightReader(
    "Logs/log_19_2026-7-5-09-43-10.bin"
).read()

print(log.get("MODE"))

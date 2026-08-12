from core.log_reader import FlightReader
from core.gps import GPSProcessor
from core.time import format_time_us


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

LOG = "Logs/log_17.bin"

FLIGHT_INDEX = 0

SAMPLE_PERIOD = 1.0


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

flight_log = FlightReader(LOG).read()

if not flight_log.flights:

    print("No FlightWindows detected.")
    raise SystemExit

if FLIGHT_INDEX >= len(flight_log.flights):

    print(
        f"Flight index {FLIGHT_INDEX} does not exist. "
        f"Detected {len(flight_log.flights)} flight(s)."
    )
    raise SystemExit


flight_window = flight_log.flights[
    FLIGHT_INDEX
]

gps = flight_log.get("GPS")


print()
print("GPS Diagnostics")
print("-" * 70)

if gps is None or gps.empty:

    print("GPS message not found.")
    raise SystemExit


print(f"Samples      : {len(gps)}")
print(f"Columns      : {list(gps.columns)}")
print(
    f"Time Start   : "
    f"{format_time_us(gps.TimeUS.min())}"
)
print(
    f"Time End     : "
    f"{format_time_us(gps.TimeUS.max())}"
)

print()
print(
    f"Flight       : "
    f"{FLIGHT_INDEX + 1}"
)
print(
    f"Window Start : "
    f"{format_time_us(flight_window.start_us)}"
)
print(
    f"Window End   : "
    f"{format_time_us(flight_window.end_us)}"
)


analysis = GPSProcessor(
    flight_log,
    flight_window,
    sample_period=SAMPLE_PERIOD,
).analyse()


if analysis is None:

    print()
    print("GPSProcessor returned None.")
    print("Either:")
    print("  - no GPS data in selected FlightWindow")
    print("  - fewer than two samples")
    raise SystemExit


print()
print("GPS Analysis")
print("-" * 70)

print(
    f"Window Start        : "
    f"{format_time_us(analysis.start_us)}"
)
print(
    f"Window End          : "
    f"{format_time_us(analysis.end_us)}"
)

print()

print(
    f"Native Rate         : "
    f"{analysis.native_rate:.1f} Hz"
)
print(
    f"Sample Period       : "
    f"{SAMPLE_PERIOD:.1f} s"
)

print()

print(
    f"Horizontal Distance : "
    f"{analysis.horizontal_distance:.1f} m"
)
print(
    f"Vertical Change     : "
    f"{analysis.vertical_change:.2f} m"
)
print(
    f"Mean Speed          : "
    f"{analysis.mean_speed:.2f} m/s"
)

print()

print(
    f"Mean HDOP           : "
    f"{analysis.mean_hdop:.2f}"
)
print(
    f"Minimum Satellites  : "
    f"{analysis.minimum_satellites}"
)

print()

print("GPS Profile")
print("-" * 90)

print(
    f"{'Time':12}"
    f"{'Alt':>8}"
    f"{'Spd':>8}"
    f"{'VZ':>8}"
    f"{'HDOP':>8}"
    f"{'NSats':>8}"
)

print("-" * 90)

for row in analysis.profile.itertuples():

    print(
        f"{format_time_us(row.TimeUS):12}"
        f"{row.Alt:8.2f}"
        f"{row.Spd:8.2f}"
        f"{row.VZ:8.2f}"
        f"{row.HDop:8.2f}"
        f"{int(row.NSats):8d}"
    )
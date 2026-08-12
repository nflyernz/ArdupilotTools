from core.log_reader import FlightReader
from core.barometer import BarometerProcessor
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

baro = flight_log.get("BARO")


print()
print("Barometer Diagnostics")
print("-" * 70)

if baro is None or baro.empty:

    print("BARO message not found.")
    raise SystemExit


print(f"Samples      : {len(baro)}")
print(f"Columns      : {list(baro.columns)}")
print(
    f"Time Start   : "
    f"{format_time_us(baro.TimeUS.min())}"
)
print(
    f"Time End     : "
    f"{format_time_us(baro.TimeUS.max())}"
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


analysis = BarometerProcessor(
    flight_log,
    flight_window,
    sample_period=SAMPLE_PERIOD,
).analyse()


if analysis is None:

    print()
    print("BarometerProcessor returned None.")
    print("Either:")
    print("  - no BARO data in selected FlightWindow")
    print("  - fewer than two samples")
    raise SystemExit


print()
print("Barometer Analysis")
print("-" * 70)

print(
    f"Window Start     : "
    f"{format_time_us(analysis.start_us)}"
)

print(
    f"Window End       : "
    f"{format_time_us(analysis.end_us)}"
)

print()

print(
    f"Native Rate      : "
    f"{analysis.native_rate:.1f} Hz"
)

print(
    f"Requested Rate   : "
    f"{analysis.requested_rate:.1f} Hz"
)

print()

print(
    f"Start Altitude   : "
    f"{analysis.start_alt:.2f} m"
)

print(
    f"End Altitude     : "
    f"{analysis.end_alt:.2f} m"
)

print(
    f"Altitude Change  : "
    f"{analysis.altitude_change:.2f} m"
)

print(
    f"Mean Rate        : "
    f"{analysis.mean_rate:.2f} m/s"
)

print()

print("Altitude Profile")
print("-" * 70)

print(
    f"{'Time':12}"
    f"{'Altitude':>12}"
)

print(
    "-" * 24
)

for row in analysis.profile.itertuples():

    print(
        f"{format_time_us(row.TimeUS):12}"
        f"{row.Alt:10.2f} m"
    )
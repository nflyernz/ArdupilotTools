from core.log_reader import FlightReader
from core.airspeed import AirspeedProcessor
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

arsp = flight_log.get("ARSP")


print()
print("Airspeed Diagnostics")
print("-" * 70)

if arsp is None or arsp.empty:

    print("ARSP message not found.")
    raise SystemExit


print(f"Samples      : {len(arsp)}")
print(f"Columns      : {list(arsp.columns)}")
print(
    f"Time Start   : "
    f"{format_time_us(arsp.TimeUS.min())}"
)
print(
    f"Time End     : "
    f"{format_time_us(arsp.TimeUS.max())}"
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


analysis = AirspeedProcessor(
    flight_log,
    flight_window,
    sample_period=SAMPLE_PERIOD,
).analyse()


if analysis is None:

    print()
    print("AirspeedProcessor returned None.")
    print("Either:")
    print("  - no ARSP data in selected FlightWindow")
    print("  - no usable samples")
    raise SystemExit


print()
print("Airspeed Analysis")
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
    f"Profile Rate        : "
    f"{analysis.requested_rate:.1f} Hz"
)

print()

print("Summary")
print("-" * 70)

print(
    f"Start Speed         : "
    f"{analysis.summary.start_speed:.2f} m/s"
)
print(
    f"End Speed           : "
    f"{analysis.summary.end_speed:.2f} m/s"
)
print(
    f"Minimum Speed       : "
    f"{analysis.summary.minimum_speed:.2f} m/s"
)
print(
    f"Maximum Speed       : "
    f"{analysis.summary.maximum_speed:.2f} m/s"
)
print(
    f"Mean Speed          : "
    f"{analysis.summary.mean_speed:.2f} m/s"
)

print()

print("Validation")
print("-" * 70)

print(
    f"Valid               : "
    f"{analysis.validation.valid}"
)
print(
    f"Rules Evaluated     : "
    f"{analysis.validation.rules_evaluated}"
)
print(
    f"Failures            : "
    f"{len(analysis.validation.failures)}"
)

if analysis.validation.failures:

    for failure in analysis.validation.failures:

        print()
        print("-" * 70)
        print(failure)

else:

    print()
    print("No validation failures.")


print()
print("Airspeed Profile")
print("-" * 70)

print(
    f"{'Time':12}"
    f"{'Airspeed':>12}"
)

print("-" * 70)

for row in analysis.profile.itertuples():

    print(
        f"{format_time_us(row.TimeUS):12}"
        f"{row.Airspeed:12.2f}"
    )
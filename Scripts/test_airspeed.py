from core.reader import FlightReader
from core.airspeed import AirspeedProcessor


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

LOG = "Logs/log_9_2026-5-3-10-43-02.bin"

START = "11:57.000"
DURATION = "05:00.000"

SAMPLE_PERIOD = 1.0


# ---------------------------------------------------------------------
# Window
# ---------------------------------------------------------------------

class Window:

    def __init__(self, start_us, end_us):

        self.start_us = start_us
        self.end_us = end_us


# ---------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------

def parse_time(text):

    minutes, seconds = text.split(":")

    return int(
        (
            int(minutes) * 60
            + float(seconds)
        )
        * 1_000_000
    )


def format_time(time_us):

    seconds = time_us / 1_000_000

    minutes = int(seconds // 60)

    seconds -= minutes * 60

    return f"{minutes:02}:{seconds:06.3f}"


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

start_us = parse_time(START)
end_us = start_us + parse_time(DURATION)

window = Window(start_us, end_us)

flight = FlightReader(LOG).read()

arsp = flight.get("ARSP")

print()
print("Airspeed Diagnostics")
print("-" * 70)

if arsp is None:

    print("ARSP message not found.")
    raise SystemExit

print(f"Samples      : {len(arsp)}")
print(f"Columns      : {list(arsp.columns)}")
print(f"Time Start   : {format_time(arsp.TimeUS.min())}")
print(f"Time End     : {format_time(arsp.TimeUS.max())}")

print()
print(f"Window Start : {format_time(start_us)}")
print(f"Window End   : {format_time(end_us)}")

analysis = AirspeedProcessor(
    flight,
    window,
    sample_period=SAMPLE_PERIOD,
).run()

if analysis is None:

    print()
    print("AirspeedProcessor returned None.")
    print("Either:")
    print("  - no ARSP data in requested window")
    print("  - fewer than two samples")
    raise SystemExit

print()
print("Airspeed Analysis")
print("-" * 70)

print(f"Window Start        : {format_time(analysis.start_us)}")
print(f"Window End          : {format_time(analysis.end_us)}")

print()

print(f"Native Rate         : {analysis.native_rate:.1f} Hz")
print(f"Profile Rate        : {analysis.requested_rate:.1f} Hz")

print()

print("Summary")
print("-" * 70)

print(f"Start Speed         : {analysis.summary.start_speed:.2f} m/s")
print(f"End Speed           : {analysis.summary.end_speed:.2f} m/s")
print(f"Minimum Speed       : {analysis.summary.minimum_speed:.2f} m/s")
print(f"Maximum Speed       : {analysis.summary.maximum_speed:.2f} m/s")
print(f"Mean Speed          : {analysis.summary.mean_speed:.2f} m/s")

print()

print("Validation")
print("-" * 70)

print(f"Valid               : {analysis.validation.valid}")
print(f"Rules Evaluated     : {analysis.validation.rules_evaluated}")
print(f"Failures            : {len(analysis.validation.failures)}")

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
        f"{format_time(row.TimeUS):12}"
        f"{row.Airspeed:12.2f}"
    )

from core.reader import FlightReader
from core.gps import GPSProcessor


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

gps = flight.get("GPS")

print()
print("GPS Diagnostics")
print("-" * 70)

if gps is None:

    print("GPS message not found.")
    raise SystemExit

print(f"Samples      : {len(gps)}")
print(f"Columns      : {list(gps.columns)}")
print(f"Time Start   : {format_time(gps.TimeUS.min())}")
print(f"Time End     : {format_time(gps.TimeUS.max())}")

print()
print(f"Window Start : {format_time(start_us)}")
print(f"Window End   : {format_time(end_us)}")

analysis = GPSProcessor(
    flight,
    window,
    sample_period=SAMPLE_PERIOD,
).run()

if analysis is None:

    print()
    print("GPSProcessor returned None.")
    print("Either:")
    print("  - no GPS data in requested window")
    print("  - fewer than two samples")
    raise SystemExit

print()
print("GPS Analysis")
print("-" * 70)

print(f"Window Start        : {format_time(analysis.start_us)}")
print(f"Window End          : {format_time(analysis.end_us)}")

print()

print(f"Native Rate         : {analysis.native_rate:.1f} Hz")
print(f"Sample Period       : {SAMPLE_PERIOD:.1f} s")

print()

print(f"Horizontal Distance : {analysis.horizontal_distance:.1f} m")
print(f"Vertical Change     : {analysis.vertical_change:.2f} m")
print(f"Mean Speed          : {analysis.mean_speed:.2f} m/s")

print()

print(f"Mean HDOP           : {analysis.mean_hdop:.2f}")
print(f"Minimum Satellites  : {analysis.minimum_satellites}")

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
        f"{format_time(row.TimeUS):12}"
        f"{row.Alt:8.2f}"
        f"{row.Spd:8.2f}"
        f"{row.VZ:8.2f}"
        f"{row.HDop:8.2f}"
        f"{int(row.NSats):8d}"
    )

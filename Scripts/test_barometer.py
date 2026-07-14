from core.reader import FlightReader
from core.barometer import BarometerProcessor


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

window = Window(
    start_us,
    end_us,
)

flight = FlightReader(LOG).read()

analysis = BarometerProcessor(
    flight,
    window,
    sample_period=SAMPLE_PERIOD,
).run()

print()

print("Barometer Analysis")
print("-" * 70)

print(
    f"Window Start     : {format_time(analysis.start_us)}"
)

print(
    f"Window End       : {format_time(analysis.end_us)}"
)

print()

print(
    f"Native Rate      : {analysis.native_rate:.1f} Hz"
)

print(
    f"Requested Rate   : {analysis.requested_rate:.1f} Hz"
)

print()

print(
    f"Start Altitude   : {analysis.start_alt:.2f} m"
)

print(
    f"End Altitude     : {analysis.end_alt:.2f} m"
)

print(
    f"Altitude Change  : {analysis.altitude_change:.2f} m"
)

print(
    f"Mean Rate        : {analysis.mean_rate:.2f} m/s"
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
        f"{format_time(row.TimeUS):12}"
        f"{row.Alt:10.2f} m"
    )

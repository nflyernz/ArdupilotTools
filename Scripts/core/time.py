"""
Shared TimeUS conversion, formatting, and sampling utilities.
"""


def parse_time(text):
    """
    Convert a UAV Log Viewer time string (MM:SS.sss)
    into TimeUS.
    """

    minutes, seconds = text.split(":")

    return int(
        (
            int(minutes) * 60
            + float(seconds)
        )
        * 1_000_000
    )


def format_time_us(time_us):
    """
    Convert TimeUS into UAV Log Viewer format (MM:SS.sss).
    """

    seconds = time_us / 1_000_000

    minutes = int(seconds // 60)

    seconds -= minutes * 60

    return f"{minutes:02}:{seconds:06.3f}"


def format_time(time_us):
    """
    Compatibility alias for format_time_us().

    New code should use format_time_us().
    """

    return format_time_us(time_us)


def duration_us(seconds):
    """
    Convert seconds into TimeUS.
    """

    return int(seconds * 1_000_000)


def native_rate(time_us_series):
    """
    Estimate the native sample rate of a message.
    """

    if len(time_us_series) < 2:
        return 0.0

    duration = (
        time_us_series.iloc[-1]
        - time_us_series.iloc[0]
    ) / 1_000_000

    if duration <= 0:
        return 0.0

    return len(time_us_series) / duration
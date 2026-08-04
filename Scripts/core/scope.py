"""
Shared scope validation and filtering utilities.

FlightLog owns telemetry and derived log-level data.

FlightWindow and analysis-specific child windows define time scope
only. These helpers provide consistent validation and filtering
without transferring data ownership into windows.
"""


def validate_flight_window(flight_log, flight_window):
    """
    Validate that a FlightWindow belongs to the supplied FlightLog.

    Raises ValueError if the window is invalid or is not one of the
    FlightWindows registered on the log.
    """

    if flight_window is None:
        raise ValueError("flight_window is required")

    if flight_window.start_us > flight_window.end_us:
        raise ValueError(
            "flight_window start_us must not be after end_us"
        )

    if not any(
        window is flight_window
        for window in flight_log.flights
    ):
        raise ValueError(
            "flight_window does not belong to the supplied FlightLog"
        )


def validate_child_window(flight_window, child_window):
    """
    Validate that a child analysis window is contained within its
    parent FlightWindow.

    Raises ValueError if the child window is invalid or extends
    outside the parent flight.
    """

    if child_window is None:
        raise ValueError("child_window is required")

    if child_window.start_us > child_window.end_us:
        raise ValueError(
            "child_window start_us must not be after end_us"
        )

    if (
        child_window.start_us < flight_window.start_us
        or child_window.end_us > flight_window.end_us
    ):
        raise ValueError(
            "child_window must be contained within flight_window"
        )


def filter_telemetry(dataframe, window):
    """
    Return telemetry rows whose TimeUS lies within the supplied window.

    The returned DataFrame retains the original index.
    """

    if dataframe is None or dataframe.empty:
        return dataframe

    if "TimeUS" not in dataframe.columns:
        raise ValueError(
            "telemetry dataframe does not contain TimeUS"
        )

    return dataframe[
        (dataframe["TimeUS"] >= window.start_us)
        & (dataframe["TimeUS"] <= window.end_us)
    ]


def filter_segments(segments, flight_window):
    """
    Return mode segments that overlap the supplied FlightWindow.

    Segments that begin before or end after the FlightWindow are still
    returned when any part of the segment overlaps the flight.
    """

    if not segments:
        return []

    return [
        segment
        for segment in segments
        if (
            segment.end_us >= flight_window.start_us
            and segment.start_us <= flight_window.end_us
        )
    ]

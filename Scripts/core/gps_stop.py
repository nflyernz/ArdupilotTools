from core.events import EventType, TimelineEvent
from core.scope import filter_telemetry


class GPSStopDetector:
    """
    Detect sustained low GPS groundspeed within a bounded window.

    The event time is the beginning of the sustained low-speed run,
    not the later sample that confirms the persistence duration.

    No landing interpretation is performed here.
    """

    def __init__(
        self,
        speed_limit=3.0,
        persistence_seconds=2.0,
    ):

        self.speed_limit = float(
            speed_limit
        )

        self.persistence_seconds = float(
            persistence_seconds
        )

        self.persistence_us = int(
            self.persistence_seconds
            * 1_000_000
        )

    def detect(
        self,
        flight_log,
        window,
        start_us=None,
    ) -> TimelineEvent | None:
        """
        Return the first sustained low-groundspeed event.

        window must expose start_us and end_us.

        start_us may be supplied to begin searching later than the
        window start while retaining the same end boundary.
        """

        if window is None:
            raise ValueError(
                "window is required"
            )

        if (
            window.start_us
            > window.end_us
        ):
            raise ValueError(
                "window start_us must not be after end_us"
            )

        search_start = (
            window.start_us
            if start_us is None
            else int(start_us)
        )

        if (
            search_start
            < window.start_us
            or search_start
            > window.end_us
        ):
            raise ValueError(
                "start_us must lie within window"
            )

        gps = filter_telemetry(
            flight_log.get("GPS"),
            window,
        )

        if gps is None or gps.empty:
            return None

        if (
            "TimeUS" not in gps.columns
            or "Spd" not in gps.columns
        ):
            return None

        gps = gps[
            gps["TimeUS"] >= search_start
        ]

        if gps.empty:
            return None

        below_since = None

        for row in gps.itertuples():

            time_us = int(
                row.TimeUS
            )

            try:

                speed = float(
                    row.Spd
                )

            except (
                TypeError,
                ValueError,
            ):

                below_since = None
                continue

            if speed < self.speed_limit:

                if below_since is None:

                    below_since = time_us

                elif (
                    time_us - below_since
                    >= self.persistence_us
                ):

                    return TimelineEvent(
                        time_us=int(
                            below_since
                        ),
                        event=EventType.GPS_STOPPED,
                        detail=(
                            f"< {self.speed_limit:.1f} m/s "
                            f"for {self.persistence_seconds:.1f} s"
                        ),
                    )

            else:

                below_since = None

        return None

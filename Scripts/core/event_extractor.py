from core.events import TimelineEvent, EventType
from core.model import FlightLog
from core.scope import filter_telemetry


class EventExtractor:
    """
    Extract firmware MSG events contained within a supplied time window.

    The window may be a FlightWindow or any child analysis window
    exposing start_us and end_us.
    """

    def extract(
        self,
        flight_log: FlightLog,
        window,
    ) -> list[TimelineEvent]:

        if window is None:
            raise ValueError("window is required")

        if window.start_us > window.end_us:
            raise ValueError(
                "window start_us must not be after end_us"
            )

        msg = filter_telemetry(
            flight_log.get("MSG"),
            window,
        )

        if msg is None or msg.empty:
            return []

        return [
            TimelineEvent(
                time_us=int(row["TimeUS"]),
                event=EventType.MSG,
                detail=row["Message"],
            )
            for _, row in msg.iterrows()
        ]
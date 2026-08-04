from core.events import TimelineEvent, EventType
from core.model import FlightLog
from core.flight_window import FlightWindow
from core.scope import (
    filter_telemetry,
    validate_flight_window,
)


class EventExtractor:
    """
    Extract firmware MSG events for a selected FlightWindow.
    """

    def extract(
        self,
        flight_log: FlightLog,
        flight_window: FlightWindow,
    ) -> list[TimelineEvent]:

        validate_flight_window(
            flight_log,
            flight_window,
        )

        msg = filter_telemetry(
            flight_log.get("MSG"),
            flight_window,
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
from core.events import TimelineEvent, EventType
from core.model import FlightLog
from core.flight_window import FlightWindow


class EventExtractor:
    """
    Extract firmware MSG events for a selected FlightWindow.
    """

    def extract(
        self,
        flight_log: FlightLog,
        flight_window: FlightWindow,
    ) -> list[TimelineEvent]:

        msg = flight_log.get("MSG")

        if msg.empty:
            return []

        msg = msg[
            (msg["TimeUS"] >= flight_window.start_us)
            & (msg["TimeUS"] <= flight_window.end_us)
        ]

        return [
            TimelineEvent(
                time_us=int(row["TimeUS"]),
                event=EventType.MSG,
                detail=row["Message"],
            )
            for _, row in msg.iterrows()
        ]
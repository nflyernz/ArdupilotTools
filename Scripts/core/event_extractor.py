from core.events import TimelineEvent, EventType


class EventExtractor:

    def extract(self, flight):

        msg = flight.get("MSG")

        if msg.empty:
            return []

        return [
            TimelineEvent(
                time_us=int(row["TimeUS"]),
                event=EventType.MSG,
                detail=row["Message"],
            )
            for _, row in msg.iterrows()
        ]

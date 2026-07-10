from core.timeline import TimelineEvent, EventType


class RangefinderEvents:
    """
    Generate rangefinder timeline events.
    """

    def __init__(self, flight, window):

        self.flight = flight
        self.window = window

    def build(self):

        events = []

        if not self.flight.has("RFND"):
            return events

        rfnd = self.flight.get("RFND")

        rfnd = rfnd[
            (rfnd.TimeUS >= self.window.start_us)
            &
            (rfnd.TimeUS <= self.window.end_us)
        ]

        if rfnd.empty:
            return events

        #
        # Parameter
        #
        max_range = self.flight.params.get("RNGFND1_MAX")

        #
        # First RFND message
        #
        first = rfnd.iloc[0]

        events.append(

            TimelineEvent(

                int(first.TimeUS),

                EventType.RANGEFINDER_FIRST_DATA,

                f"{first.Dist:.2f} m",
            )
        )

        #
        # First sample inside configured range
        #
        if max_range is not None:

            inside = rfnd[rfnd.Dist < max_range]

            if not inside.empty:

                row = inside.iloc[0]

                events.append(

                    TimelineEvent(

                        int(row.TimeUS),

                        EventType.RANGEFINDER_IN_RANGE,

                        f"{row.Dist:.2f} m",
                    )
                )

        return events

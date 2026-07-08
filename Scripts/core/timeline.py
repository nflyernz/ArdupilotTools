from dataclasses import dataclass


@dataclass
class TimelineEvent:

    time_us: int
    event: str
    value: object = None


class LandingTimeline:

    def __init__(self, flight):

        self.flight = flight

    def build(self):

        events = []

        events.extend(self._mode_events())

        events.extend(self._land_stage_events())

        events.extend(self._rangefinder_events())

        events.sort(key=lambda e: e.time_us)

        return events

    def _mode_events(self):

        events = []

        mode = self.flight.get("MODE")

        if mode.empty:
            return events

        for _, row in mode.iterrows():

            events.append(
                TimelineEvent(
                    int(row.TimeUS),
                    "MODE",
                    row.Mode
                )
            )

        return events

    def _land_stage_events(self):

        events = []

        land = self.flight.get("LAND")

        if land.empty:
            return events

        previous = None

        for _, row in land.iterrows():

            stage = int(row.stage)

            if stage != previous:

                events.append(
                    TimelineEvent(
                        int(row.TimeUS),
                        "LAND_STAGE",
                        stage
                    )
                )

                previous = stage

        return events

    def _rangefinder_events(self):

        events = []

        rfnd = self.flight.get("RFND")

        if rfnd.empty:
            return events

        valid = False

        max_range = self.flight.param("RNGFND1_MAX")

        if max_range is None:
            return events

        for _, row in rfnd.iterrows():

            if not valid and row.Dist <= max_range:

                events.append(
                    TimelineEvent(
                        int(row.TimeUS),
                        "RFND_VALID",
                        row.Dist
                    )
                )

                valid = True

        return events

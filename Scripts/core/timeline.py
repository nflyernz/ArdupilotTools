from core.events import TimelineEvent, EventType
from core.rangefinder import RangefinderEvents


class LandingTimeline:
    """
    Build a chronological timeline for one landing window.
    """

    def __init__(self, flight, window, config):

        self.flight = flight
        self.window = window
        self.config = config

    def build(self):

        events = []

        #
        # LAND.stage transitions
        #
        land = self.flight.get("LAND")

        if not land.empty:

            land = land[
                (land.TimeUS >= self.window.start_us)
                &
                (land.TimeUS <= self.window.end_us)
            ]

            previous = None

            for _, row in land.iterrows():

                stage = int(row.stage)

                if stage != previous:

                    events.append(

                        TimelineEvent(

                            int(row.TimeUS),

                            EventType.LAND_STAGE,

                            str(stage),

                        )

                    )

                    previous = stage

        #
        # MODE transitions
        #
        mode = self.flight.get("MODE")

        if not mode.empty:

            mode = mode[
                (mode.TimeUS >= self.window.start_us)
                &
                (mode.TimeUS <= self.window.end_us)
            ]

            for _, row in mode.iterrows():

                events.append(

                    TimelineEvent(

                        int(row.TimeUS),

                        EventType.MODE,

                        str(row.Mode),

                    )

                )

        #
        # ARM transitions
        #
        arm = self.flight.get("ARM")

        if not arm.empty:

            arm = arm[
                (arm.TimeUS >= self.window.start_us)
                &
                (arm.TimeUS <= self.window.end_us)
            ]

            for _, row in arm.iterrows():

                events.append(

                    TimelineEvent(

                        int(row.TimeUS),

                        EventType.ARM,

                        "ARMED" if row.ArmState else "DISARMED",

                    )

                )

        #
        # Rangefinder events
        #
        events.extend(

            RangefinderEvents(

                self.flight,
                self.window,
                self.config,

            ).build()

        )

        #
        # Sort chronologically
        #
        events.sort()

        return events
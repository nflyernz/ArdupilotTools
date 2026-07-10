from dataclasses import dataclass
from enum import Enum

#from core.rangefinder import RangefinderEvents


class EventType(Enum):

    LAND_STAGE = "LAND_STAGE"

    MODE = "MODE"

    ARM = "ARM"

    RANGEFINDER_FIRST_DATA = "RFND_FIRST_DATA"

    RANGEFINDER_IN_RANGE = "RFND_IN_RANGE"

    TOUCHDOWN = "TOUCHDOWN"

    GPS_STOPPED = "GPS_STOPPED"


@dataclass(order=True)
class TimelineEvent:

    time_us: int

    event: EventType

    detail: str = ""


class LandingTimeline:
    """
    Build a chronological timeline for one landing window.
    """

    def __init__(self, flight, window):

        self.flight = flight
        self.window = window

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

                state = "ARMED" if row.ArmState else "DISARMED"

                events.append(

                    TimelineEvent(

                        int(row.TimeUS),

                        EventType.ARM,

                        state,
                    )
                )

        #
        # Rangefinder-derived events
        #
 #       events.extend(
#
 #           RangefinderEvents(
#
 #               self.flight,
#
 #               self.window,
#
 #           ).build()
#
 #       )

        #
        # Chronological order
        #
        events.sort()

        return events

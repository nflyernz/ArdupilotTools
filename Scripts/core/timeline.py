from core.events import TimelineEvent, EventType
from core.model import FlightLog
from core.flight_window import FlightWindow
from core.landing_window import LandingWindow
from core.rangefinder import RangefinderEvents
from core.scope import (
    filter_telemetry,
    validate_child_window,
    validate_flight_window,
)


class LandingTimeline:
    """
    Build a chronological timeline for one landing window
    within a selected FlightWindow.
    """

    def __init__(
        self,
        flight_log: FlightLog,
        flight_window: FlightWindow,
        landing_window: LandingWindow,
        config,
    ):

        self.flight_log = flight_log
        self.flight_window = flight_window
        self.landing_window = landing_window
        self.config = config

        validate_flight_window(
            flight_log,
            flight_window,
        )

        validate_child_window(
            flight_window,
            landing_window,
        )

    def build(self):

        events = []

        #
        # LAND.stage transitions
        #
        land = filter_telemetry(
            self.flight_log.get("LAND"),
            self.landing_window,
        )

        if not land.empty:

            previous = None

            for _, row in land.iterrows():

                stage = int(row["stage"])

                if stage != previous:

                    events.append(
                        TimelineEvent(
                            int(row["TimeUS"]),
                            EventType.LAND_STAGE,
                            str(stage),
                        )
                    )

                    previous = stage

        #
        # MODE transitions
        #
        mode = filter_telemetry(
            self.flight_log.get("MODE"),
            self.landing_window,
        )

        if not mode.empty:

            for _, row in mode.iterrows():

                events.append(
                    TimelineEvent(
                        int(row["TimeUS"]),
                        EventType.MODE,
                        str(row["Mode"]),
                    )
                )

        #
        # ARM transitions
        #
        arm = filter_telemetry(
            self.flight_log.get("ARM"),
            self.landing_window,
        )

        if not arm.empty:

            for _, row in arm.iterrows():

                events.append(
                    TimelineEvent(
                        int(row["TimeUS"]),
                        EventType.ARM,
                        "ARMED"
                        if row["ArmState"]
                        else "DISARMED",
                    )
                )

        #
        # Rangefinder events
        #
        events.extend(
            RangefinderEvents(
                self.flight_log,
                self.landing_window,
                self.config,
            ).build()
        )

        #
        # Sort chronologically
        #
        events.sort()

        return events
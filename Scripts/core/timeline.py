from core.events import TimelineEvent, EventType
from core.model import FlightLog
from core.flight_window import FlightWindow
from core.landing_window import LandingWindow
from core.rangefinder import RangefinderEvents


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

        if flight_window not in flight_log.flights:
            raise ValueError(
                "FlightWindow does not belong to FlightLog"
            )

        if (
            landing_window.start_us < flight_window.start_us
            or landing_window.end_us > flight_window.end_us
        ):
            raise ValueError(
                "LandingWindow is outside parent FlightWindow"
            )

    def build(self):

        events = []

        #
        # LAND.stage transitions
        #
        land = self.flight_log.get("LAND")

        if not land.empty:

            land = land[
                (land["TimeUS"] >= self.landing_window.start_us)
                & (land["TimeUS"] <= self.landing_window.end_us)
            ]

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
        mode = self.flight_log.get("MODE")

        if not mode.empty:

            mode = mode[
                (mode["TimeUS"] >= self.landing_window.start_us)
                & (mode["TimeUS"] <= self.landing_window.end_us)
            ]

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
        arm = self.flight_log.get("ARM")

        if not arm.empty:

            arm = arm[
                (arm["TimeUS"] >= self.landing_window.start_us)
                & (arm["TimeUS"] <= self.landing_window.end_us)
            ]

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
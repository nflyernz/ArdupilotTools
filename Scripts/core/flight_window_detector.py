"""
Detect individual flights within a log.

A FlightWindow represents one continuous flight bounded by
extended periods on the ground.

Detection is based solely on GPS ground speed and is independent
of flight mode, mission state or analysis type.
"""

from .model import FlightLog
from .flight_window import FlightWindow


class FlightWindowDetector:

    DEFAULT_THRESHOLD = 5.0

    FLIGHT_TIME_US = 2_000_000       # 2 seconds
    GROUND_TIME_US = 30_000_000      # 30 seconds

    def __init__(
        self,
        speed_threshold=DEFAULT_THRESHOLD,
    ):

        if speed_threshold <= 0:
            raise ValueError(
                "Flight speed threshold must be greater than zero."
            )

        self.speed_threshold = float(
            speed_threshold
        )

    def detect(
        self,
        flight_log: FlightLog,
    ) -> list[FlightWindow]:

        gps = flight_log.get("GPS")

        if gps.empty:
            return []

        #
        # AIRSPEED_STALL may raise the effective threshold,
        # but never lower the configured minimum threshold.
        #
        threshold = max(
            self.speed_threshold,
            0.5 * flight_log.param(
                "AIRSPEED_STALL",
                self.speed_threshold * 2,
            ),
        )

        windows = []

        start = None

        flight_candidate_start = None
        ground_start = None

        for index, row in gps.iterrows():

            time_us = int(row["TimeUS"])
            speed = float(row["Spd"])

            above_threshold = (
                speed > threshold
            )

            #
            # Looking for the start of a flight.
            #
            if start is None:

                if above_threshold:

                    if flight_candidate_start is None:

                        flight_candidate_start = index

                    candidate_time_us = int(
                        gps.loc[
                            flight_candidate_start,
                            "TimeUS",
                        ]
                    )

                    duration = (
                        time_us
                        - candidate_time_us
                    )

                    if duration >= self.FLIGHT_TIME_US:

                        #
                        # Flight starts at the first sample
                        # of the persistent above-threshold
                        # sequence.
                        #
                        start = flight_candidate_start

                        flight_candidate_start = None
                        ground_start = None

                else:

                    #
                    # Threshold persistence was broken.
                    #
                    flight_candidate_start = None

                continue

            #
            # Already in flight.
            #
            if above_threshold:

                ground_start = None

            else:

                if ground_start is None:

                    ground_start = index

                ground_time_us = int(
                    gps.loc[
                        ground_start,
                        "TimeUS",
                    ]
                )

                duration = (
                    time_us
                    - ground_time_us
                )

                if duration >= self.GROUND_TIME_US:

                    #
                    # Flight ends at the last sample before
                    # the extended ground period began.
                    #
                    end_index = ground_start - 1

                    windows.append(
                        FlightWindow(
                            start_us=int(
                                gps.loc[
                                    start,
                                    "TimeUS",
                                ]
                            ),
                            end_us=int(
                                gps.loc[
                                    end_index,
                                    "TimeUS",
                                ]
                            ),
                        )
                    )

                    start = None
                    flight_candidate_start = None
                    ground_start = None

        #
        # Flight continues to the end of available GPS data.
        #
        if start is not None:

            windows.append(
                FlightWindow(
                    start_us=int(
                        gps.loc[
                            start,
                            "TimeUS",
                        ]
                    ),
                    end_us=int(
                        gps["TimeUS"].iloc[-1]
                    ),
                )
            )

        return windows
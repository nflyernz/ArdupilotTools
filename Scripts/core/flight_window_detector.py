"""
Detect individual flights within a log.

A FlightWindow represents one continuous flight bounded by
extended periods on the ground.

Detection is based solely on GPS ground speed and is independent
of flight mode, mission state or analysis type.
"""

from .flight_window import FlightWindow


class FlightWindowDetector:

    DEFAULT_THRESHOLD = 5.0
    MIN_SAMPLES = 5
    GROUND_TIME_US = 30_000_000      # 30 seconds

    def detect(self, flight):

        gps = flight.get("GPS")

        if gps.empty:
            return []

        threshold = max(
            self.DEFAULT_THRESHOLD,
            0.5 * flight.param(
                "AIRSPEED_STALL",
                self.DEFAULT_THRESHOLD * 2,
            ),
        )

        flying = gps.Spd > threshold

        windows = []

        start = None
        flying_count = 0
        ground_start = None

        for index, state in enumerate(flying):

            #
            # Looking for start of flight
            #
            if start is None:

                if state:

                    flying_count += 1

                    if flying_count >= self.MIN_SAMPLES:

                        start = index - self.MIN_SAMPLES + 1
                        ground_start = None

                else:

                    flying_count = 0

                continue

            #
            # Already in flight
            #
            if state:

                ground_start = None

            else:

                if ground_start is None:

                    ground_start = index

                duration = (
                    gps.TimeUS.iloc[index]
                    - gps.TimeUS.iloc[ground_start]
                )

                if duration >= self.GROUND_TIME_US:

                    windows.append(

                        FlightWindow(

                            start_us=int(
                                gps.TimeUS.iloc[start]
                            ),

                            end_us=int(
                                gps.TimeUS.iloc[
                                    ground_start - 1
                                ]
                            ),

                        )

                    )

                    start = None
                    flying_count = 0
                    ground_start = None

        #
        # Flight continues to end of log
        #
        if start is not None:

            windows.append(

                FlightWindow(

                    start_us=int(
                        gps.TimeUS.iloc[start]
                    ),

                    end_us=int(
                        gps.TimeUS.iloc[-1]
                    ),

                )

            )

        return windows

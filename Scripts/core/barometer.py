from dataclasses import dataclass

import pandas as pd


@dataclass
class BarometerEvent:

    time_us: int
    name: str


class BarometerEvents:

    LEVEL = 0
    DESCENDING = 1
    CLIMBING = 2

    def __init__(self, flight, window, config):

        self.flight = flight
        self.window = window
        self.config = config

        self.events = []

    def find(self):

        baro = self.flight.get("BARO")

        if baro is None or baro.empty:
            return []

        #
        # Restrict to landing window
        #

        baro = baro[
            (baro.TimeUS >= self.window.start_us)
            &
            (baro.TimeUS <= self.window.end_us)
        ].copy()

        if len(baro) < 2:
            return []

        #
        # Configuration
        #

        samples = int(
            self.config.get(
                "barometer.smoothing_samples"
            )
        )

        derivative = int(
            self.config.get(
                "barometer.derivative_samples"
            )
        )

        descent = float(
            self.config.get(
                "barometer.descent_threshold"
            )
        )

        climb = float(
            self.config.get(
                "barometer.climb_threshold"
            )
        )

        level = float(
            self.config.get(
                "barometer.level_threshold"
            )
        )

        #
        # Smooth altitude
        #

        baro["AltSmooth"] = (
            baro["Alt"]
            .rolling(
                window=samples,
                center=True,
                min_periods=1,
            )
            .mean()
        )

        #
        # Vertical rate (m/s)
        #

        dt = (
            baro["TimeUS"].diff(derivative)
            / 1e6
        )

        dz = (
            baro["AltSmooth"].diff(derivative)
        )

        baro["Rate"] = dz / dt

        #
        # State machine
        #

        state = self.LEVEL

        for row in baro.itertuples():

            if pd.isna(row.Rate):
                continue

            #
            # LEVEL
            #

            if state == self.LEVEL:

                if row.Rate < descent:

                    self.events.append(
                        BarometerEvent(
                            row.TimeUS,
                            "BARO_DESCENT_START",
                        )
                    )

                    state = self.DESCENDING

                    continue

                if row.Rate > climb:

                    self.events.append(
                        BarometerEvent(
                            row.TimeUS,
                            "BARO_CLIMB_START",
                        )
                    )

                    state = self.CLIMBING

                    continue

            #
            # DESCENDING
            #

            elif state == self.DESCENDING:

                if abs(row.Rate) < level:

                    self.events.append(
                        BarometerEvent(
                            row.TimeUS,
                            "BARO_LEVEL",
                        )
                    )

                    state = self.LEVEL

                    continue

            #
            # CLIMBING
            #

            elif state == self.CLIMBING:

                if abs(row.Rate) < level:

                    self.events.append(
                        BarometerEvent(
                            row.TimeUS,
                            "BARO_LEVEL",
                        )
                    )

                    state = self.LEVEL

                    continue

        return self.events

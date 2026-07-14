from dataclasses import dataclass

import pandas as pd

from .time import native_rate


@dataclass
class BarometerAnalysis:

    start_us: int
    end_us: int

    native_rate: float
    requested_rate: float

    start_alt: float
    end_alt: float

    altitude_change: float
    mean_rate: float

    profile: pd.DataFrame


class BarometerProcessor:

    def __init__(
        self,
        flight,
        window,
        sample_period=1.0,
    ):

        self.flight = flight
        self.window = window
        self.sample_period = sample_period

    def run(self):

        baro = self.flight.get("BARO")

        if baro is None or baro.empty:
            return None

        #
        # Restrict to requested window.
        #

        baro = baro[
            (baro.TimeUS >= self.window.start_us)
            &
            (baro.TimeUS <= self.window.end_us)
        ].copy()

        if len(baro) < 2:
            return None

        #
        # Native sample rate.
        #

        rate = native_rate(
            baro.TimeUS
        )

        #
        # Down sample.
        #

        bucket_us = int(
            self.sample_period * 1_000_000
        )

        profile = (
            baro
            .assign(
                Bucket=lambda df:
                (
                    (df.TimeUS - df.TimeUS.iloc[0])
                    // bucket_us
                )
            )
            .groupby("Bucket")
            .agg(
                TimeUS=("TimeUS", "first"),
                Alt=("Alt", "mean"),
            )
            .reset_index(drop=True)
        )

        #
        # Summary based on the displayed profile.
        #

        start_alt = float(
            profile.Alt.iloc[0]
        )

        end_alt = float(
            profile.Alt.iloc[-1]
        )

        altitude_change = (
            end_alt - start_alt
        )

        duration = (
            profile.TimeUS.iloc[-1]
            - profile.TimeUS.iloc[0]
        ) / 1_000_000

        if duration > 0:

            mean_rate = (
                altitude_change / duration
            )

        else:

            mean_rate = 0.0

        return BarometerAnalysis(

            start_us=self.window.start_us,

            end_us=self.window.end_us,

            native_rate=rate,

            requested_rate=1.0 / self.sample_period,

            start_alt=start_alt,

            end_alt=end_alt,

            altitude_change=altitude_change,

            mean_rate=mean_rate,

            profile=profile,
        )

from dataclasses import dataclass

import pandas as pd

from .flight_window import FlightWindow
from .flight_data import FlightLog
from .scope import (
    filter_telemetry,
    validate_child_window,
    validate_flight_window,
)
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
        flight_log: FlightLog,
        flight_window: FlightWindow,
        sample_period=1.0,
    ):

        validate_flight_window(
            flight_log,
            flight_window,
        )

        self.flight_log = flight_log
        self.flight_window = flight_window
        self.sample_period = sample_period

    def analyse(
        self,
        analysis_window=None,
    ):

        if analysis_window is None:
            analysis_window = self.flight_window

        validate_child_window(
            self.flight_window,
            analysis_window,
        )

        baro = filter_telemetry(
            self.flight_log.get("BARO"),
            analysis_window,
        )

        if baro is None or len(baro) < 2:
            return None

        baro = baro.copy()

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
                    (
                        df.TimeUS
                        - df.TimeUS.iloc[0]
                    )
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
            start_us=analysis_window.start_us,
            end_us=analysis_window.end_us,
            native_rate=rate,
            requested_rate=1.0 / self.sample_period,
            start_alt=start_alt,
            end_alt=end_alt,
            altitude_change=altitude_change,
            mean_rate=mean_rate,
            profile=profile,
        )
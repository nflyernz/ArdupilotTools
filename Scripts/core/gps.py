from dataclasses import dataclass
import math

import pandas as pd

from .time import native_rate


@dataclass
class GPSAnalysis:

    start_us: int
    end_us: int

    native_rate: float
    requested_rate: float

    start_lat: float
    start_lng: float
    start_alt: float

    end_lat: float
    end_lng: float
    end_alt: float

    horizontal_distance: float
    vertical_change: float

    mean_speed: float

    mean_hdop: float
    minimum_satellites: int

    profile: pd.DataFrame


class GPSProcessor:

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

        gps = self.flight.get("GPS")

        if gps is None or gps.empty:
            return None

        #
        # Restrict to requested window.
        #

        gps = gps[
            (gps.TimeUS >= self.window.start_us)
            &
            (gps.TimeUS <= self.window.end_us)
        ].copy()

        if len(gps) < 2:
            return None

        #
        # Native sample rate.
        #

        rate = native_rate(
            gps.TimeUS
        )

        #
        # Down sample.
        #

        bucket_us = int(
            self.sample_period * 1_000_000
        )

        profile = (
            gps
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
                Lat=("Lat", "mean"),
                Lng=("Lng", "mean"),
                Alt=("Alt", "mean"),
                Spd=("Spd", "mean"),
                VZ=("VZ", "mean"),
                HDop=("HDop", "mean"),
                NSats=("NSats", "min"),
            )
            .reset_index(drop=True)
        )

        #
        # Summary based on displayed profile.
        #

        start_lat = float(
            profile.Lat.iloc[0]
        )

        start_lng = float(
            profile.Lng.iloc[0]
        )

        start_alt = float(
            profile.Alt.iloc[0]
        )

        end_lat = float(
            profile.Lat.iloc[-1]
        )

        end_lng = float(
            profile.Lng.iloc[-1]
        )

        end_alt = float(
            profile.Alt.iloc[-1]
        )

        vertical_change = (
            end_alt - start_alt
        )

        mean_speed = float(
            profile.Spd.mean()
        )

        mean_hdop = float(
            profile.HDop.mean()
        )

        minimum_satellites = int(
            profile.NSats.min()
        )

        #
        # Horizontal distance.
        #

        lat_scale = 111320.0

        mean_lat = (
            start_lat + end_lat
        ) / 2.0

        lng_scale = (
            111320.0
            * math.cos(
                math.radians(mean_lat)
            )
        )

        dx = (
            end_lng - start_lng
        ) * lng_scale

        dy = (
            end_lat - start_lat
        ) * lat_scale

        horizontal_distance = math.sqrt(
            dx * dx + dy * dy
        )

        return GPSAnalysis(

            start_us=self.window.start_us,

            end_us=self.window.end_us,

            native_rate=rate,

            requested_rate=1.0 / self.sample_period,

            start_lat=start_lat,

            start_lng=start_lng,

            start_alt=start_alt,

            end_lat=end_lat,

            end_lng=end_lng,

            end_alt=end_alt,

            horizontal_distance=horizontal_distance,

            vertical_change=vertical_change,

            mean_speed=mean_speed,

            mean_hdop=mean_hdop,

            minimum_satellites=minimum_satellites,

            profile=profile,
        )

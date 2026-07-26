"""
Determine the sensor health evaluation window.
"""

from dataclasses import dataclass


@dataclass(slots=True)
class SensorHealthWindow:
    start_us: int
    end_us: int


class SensorHealthWindowDetector:

    DEFAULT_THRESHOLD = 5.0
    MIN_SAMPLES = 5
    TRIM_US = 2_000_000      # 2 seconds

    def detect(self, flight):

        gps = flight.get("GPS")

        if gps.empty:
            raise ValueError("No GPS data available.")

        threshold = max(
            self.DEFAULT_THRESHOLD,
            0.5 * flight.param(
                "AIRSPEED_STALL",
                self.DEFAULT_THRESHOLD * 2,
            ),
        )

        flying = gps["Spd"] > threshold

        start = self._find_start(flying)

        if start is None:
            raise ValueError(
                "Unable to determine sensor health window."
            )

        end = self._find_end(flying)

        start_us = int(gps.iloc[start]["TimeUS"]) + self.TRIM_US
        end_us = int(gps.iloc[end]["TimeUS"]) - self.TRIM_US

        if start_us >= end_us:
            raise ValueError(
                "Sensor health window is too short."
            )

        return SensorHealthWindow(
            start_us=start_us,
            end_us=end_us,
        )

    def _find_start(self, flying):

        count = 0

        for index, state in enumerate(flying):

            if state:
                count += 1

                if count >= self.MIN_SAMPLES:
                    return index - self.MIN_SAMPLES + 1
            else:
                count = 0

        return None

    def _find_end(self, flying):

        count = 0

        for index in range(len(flying) - 1, -1, -1):

            if flying.iloc[index]:
                count += 1

                if count >= self.MIN_SAMPLES:
                    return index + self.MIN_SAMPLES - 1
            else:
                count = 0

        return Nonea
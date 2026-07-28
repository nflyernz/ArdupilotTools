"""
Determine the sensor health evaluation window.

A SensorHealthWindow defines the period during which sensor
validation should be performed within a FlightWindow.

The detector assumes the supplied FlightWindow already bounds
a single flight and simply trims transient behaviour from the
start and end.
"""

from dataclasses import dataclass


@dataclass(slots=True)
class SensorHealthWindow:
    """
    Time interval over which sensor validation should be performed.
    """

    start_us: int
    end_us: int


class SensorHealthWindowDetector:
    """
    Create a sensor health window from a FlightWindow.

    A small amount of time is trimmed from the start and end of
    the flight to remove transient behaviour during takeoff and
    landing.
    """

    TRIM_US = 2_000_000      # 2 seconds

    def detect(self, flight_window):

        start_us = flight_window.start_us + self.TRIM_US
        end_us = flight_window.end_us - self.TRIM_US

        if start_us >= end_us:
            raise ValueError(
                "Sensor health window is too short."
            )

        return SensorHealthWindow(
            start_us=start_us,
            end_us=end_us,
        )
"""
Flight window model.

A FlightWindow represents a single continuous flight within a log.

Logs may contain multiple flights separated by extended periods on
the ground. Each FlightWindow becomes the parent container for
analysis-specific windows such as sensor health, landing, cruise,
autotune and RTL.
"""

from dataclasses import dataclass


@dataclass(slots=True)
class FlightWindow:
    """
    Time bounds for a single flight.
    """

    start_us: int
    end_us: int

"""
Landing analysis window.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class LandingWindow:
    """
    Landing analysis time window.
    """

    start_us: int
    end_us: int

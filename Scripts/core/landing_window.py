"""
Landing analysis window.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class LandingWindow:
    """
    One detected and bounded AUTO landing attempt.
    """

    start_us: int
    end_us: int
    end_reason: str
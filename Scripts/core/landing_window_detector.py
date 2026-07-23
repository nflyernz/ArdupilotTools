"""
Landing window detector.
"""

from core.landing_window import LandingWindow


class LandingWindowDetector:
    """
    Detects the landing analysis window.

    Initial implementation returns a fixed window for
    development and architecture testing.
    """

    def detect(self, telemetry):

        #
        # Development window
        #
        return LandingWindow(
            start_us=717_000_000,
            end_us=1_017_000_000,
        )

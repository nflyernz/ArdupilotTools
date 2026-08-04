"""
Landing window detector.
"""

from core.model import FlightLog
from core.flight_window import FlightWindow
from core.landing_window import LandingWindow
from core.scope import validate_flight_window


class LandingWindowDetector:
    """
    Detect landing analysis windows within a FlightWindow.

    The current implementation returns the complete FlightWindow as a
    single LandingWindow. Future versions will detect one or more
    landing attempts using LAND, MSG and MODE events.
    """

    def detect(
        self,
        flight_log: FlightLog,
        flight_window: FlightWindow,
    ) -> list[LandingWindow]:
        """
        Detect landing windows contained within the supplied FlightWindow.

        Parameters
        ----------
        flight_log
            Complete decoded flight log.

        flight_window
            Flight to analyse.

        Returns
        -------
        list[LandingWindow]
            Landing windows contained within the flight.
        """

        validate_flight_window(
            flight_log,
            flight_window,
        )

        #
        # Temporary implementation.
        #
        # Until landing detection is implemented, analyse the complete
        # FlightWindow as a single landing window.
        #
        return [
            LandingWindow(
                start_us=flight_window.start_us,
                end_us=flight_window.end_us,
            )
        ]
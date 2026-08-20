from .landing_attempt import LandingAttempt


class LandingAttemptExtractor:
    """
    Convert a bounded LandingWindow into a LandingAttempt.

    LandingWindowDetector is responsible for detecting the AUTO
    landing attempt and determining its temporal boundaries.
    """

    def __init__(
        self,
        flight_log,
    ):
        self.flight_log = flight_log

    def extract(
        self,
        landing_window,
    ) -> list[LandingAttempt]:

        return [
            LandingAttempt(
                start_us=landing_window.start_us,
                end_us=landing_window.end_us,
            )
        ]
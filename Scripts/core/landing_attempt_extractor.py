from .event_extractor import EventExtractor
from .events import EventType
from .landing_attempt import LandingAttempt


class LandingAttemptExtractor:
    """
    Split a LandingWindow into individual AUTO landing attempts.

    Detection is based solely on observed timeline events.
    No interpretation of landing quality or success is performed.
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

        events = EventExtractor().extract(
            self.flight_log,
            landing_window,
        )

        attempts = []

        start_us = None

        for event in events:

            #
            # Start of a landing attempt.
            #
            if (
                event.event == EventType.MSG
                and event.detail.startswith(
                    "Mission: 1 LandStart"
                )
            ):

                #
                # Close any unfinished attempt.
                #
                if start_us is not None:

                    attempts.append(
                        LandingAttempt(
                            start_us=start_us,
                            end_us=event.time_us,
                        )
                    )

                start_us = event.time_us
                continue

            #
            # End of a landing attempt.
            #
            if (
                start_us is not None
                and event.event == EventType.MSG
                and (
                    event.detail.startswith(
                        "Landing aborted"
                    )
                    or event.detail.startswith(
                        "Throttle disarmed"
                    )
                )
            ):

                attempts.append(
                    LandingAttempt(
                        start_us=start_us,
                        end_us=event.time_us,
                    )
                )

                start_us = None

        #
        # Final attempt continues until the end of the LandingWindow.
        #
        if start_us is not None:

            attempts.append(
                LandingAttempt(
                    start_us=start_us,
                    end_us=landing_window.end_us,
                )
            )

        return attempts
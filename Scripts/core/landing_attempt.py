from dataclasses import dataclass


@dataclass(slots=True)
class LandingAttempt:
    """
    One AUTO landing attempt contained within a LandingWindow.

    An attempt begins when ArduPlane enters a landing sequence
    (Mission: LandStart or equivalent restart) and ends when the
    landing is aborted, completes, or the LandingWindow ends.

    The class defines only the temporal scope. Interpretation of
    the attempt is performed elsewhere.
    """

    start_us: int
    end_us: int

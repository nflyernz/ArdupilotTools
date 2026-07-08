from dataclasses import dataclass


# Landing window close reasons
STAGE_ZERO = "STAGE_ZERO"
END_OF_LOG = "END_OF_LOG"


@dataclass
class LandingWindow:
    """
    One continuous period where the ArduPlane landing
    state machine is active.
    """

    start_us: int

    end_us: int = 0

    start_index: int = 0

    end_index: int = 0

    duration_s: float = 0.0

    closed: bool = False

    close_reason: str = ""

    @property
    def is_closed(self):
        return self.closed

    @property
    def is_long(self):
        """
        Long landing sequences may indicate loitering,
        repositioning or an aborted approach.
        """
        return self.duration_s > 120.0


class LandingWindows:
    """
    Find all landing windows within a flight.

    A landing window starts when LAND.stage changes
    from 0 to 1.

    A landing window ends when LAND.stage returns
    to 0, or at the end of the log.
    """

    def __init__(self, flight):

        self.flight = flight

    def find(self):

        land = self.flight.get("LAND")

        if land.empty:
            return []

        windows = []

        current = None

        previous_stage = 0

        for index, row in land.iterrows():

            stage = int(row.stage)

            #
            # Start of landing
            #
            if previous_stage == 0 and stage == 1:

                current = LandingWindow(
                    start_us=int(row.TimeUS),
                    start_index=index,
                )

            #
            # End of landing
            #
            elif (
                current is not None
                and previous_stage > 0
                and stage == 0
            ):

                current.end_us = int(row.TimeUS)
                current.end_index = index

                current.duration_s = (
                    current.end_us - current.start_us
                ) / 1e6

                current.closed = True
                current.close_reason = STAGE_ZERO

                windows.append(current)

                current = None

            previous_stage = stage

        #
        # Landing still active when log ends
        #
        if current is not None:

            current.end_us = int(land.iloc[-1].TimeUS)
            current.end_index = land.index[-1]

            current.duration_s = (
                current.end_us - current.start_us
            ) / 1e6

            current.closed = False
            current.close_reason = END_OF_LOG

            windows.append(current)

        return windows

"""
Landing window detector.
"""

from core.config import Config
from core.gps_stop import GPSStopDetector
from core.landing_window import LandingWindow
from core.modes import mode_name
from core.scope import validate_flight_window


class LandingWindowDetector:

    def __init__(self):

        self.config = Config(
            "Config/landing.yaml"
        )

    def detect(
        self,
        flight_log,
        flight_window,
    ):

        validate_flight_window(
            flight_log,
            flight_window,
        )

        land = flight_log.get("LAND")
        msg = flight_log.get("MSG")
        mode = flight_log.get("MODE")

        #
        # LAND telemetry is required to identify the beginning of
        # an AUTO landing attempt.
        #
        # GPS is not mandatory. When GPS is unavailable, other
        # termination evidence can still bound the attempt.
        #
        if land.empty:
            return []

        start_rows = land[
            (
                land["TimeUS"]
                >= flight_window.start_us
            )
            & (
                land["TimeUS"]
                <= flight_window.end_us
            )
            & (
                land["stage"]
                == 1
            )
            & (
                land["stage"].shift()
                != 1
            )
        ]

        # --------------------------------------------------------
        # Only accept LAND.stage 1 as a landing attempt when the
        # aircraft is in AUTO at the time of the transition.
        #
        # Find the most recent MODE record at or before each
        # stage-1 transition.
        # --------------------------------------------------------

        valid_starts = []

        for start in start_rows[
            "TimeUS"
        ].astype(int):

            if mode.empty:
                continue

            mode_rows = mode[
                mode["TimeUS"]
                <= start
            ]

            if mode_rows.empty:
                continue

            current_mode = (
                mode_rows.iloc[-1]
            )

            if (
                mode_name(
                    current_mode[
                        "ModeNum"
                    ]
                )
                != "AUTO"
            ):
                continue

            valid_starts.append(
                start
            )

        speed_limit = float(
            self.config.get(
                "landing_window.end_speed",
                3.0,
            )
        )

        persistence_seconds = float(
            self.config.get(
                "landing_window.end_speed_seconds",
                2.0,
            )
        )

        gps_stop_detector = (
            GPSStopDetector(
                speed_limit=(
                    speed_limit
                ),
                persistence_seconds=(
                    persistence_seconds
                ),
            )
        )

        windows = []

        for start in valid_starts:

            # ----------------------------------------------------
            # Candidate termination times.
            #
            # Each termination source is evaluated independently.
            # The earliest applicable boundary wins.
            # ----------------------------------------------------

            termination_events = []

            # ----------------------------------------------------
            # Landing abort / disarm messages.
            # ----------------------------------------------------

            if not msg.empty:

                for row in msg[
                    msg["TimeUS"]
                    > start
                ].itertuples():

                    event_t = int(
                        row.TimeUS
                    )

                    if (
                        event_t
                        > flight_window.end_us
                    ):
                        break

                    text = str(
                        row.Message
                    ).lower()

                    if (
                        "landing aborted"
                        in text
                    ):

                        termination_events.append(
                            (
                                event_t,
                                "abort",
                            )
                        )

                    elif (
                        "throttle disarmed"
                        in text
                    ):

                        termination_events.append(
                            (
                                event_t,
                                "disarm",
                            )
                        )

            # ----------------------------------------------------
            # Mode changes.
            #
            # The first transition away from AUTO terminates the
            # current landing attempt.
            # ----------------------------------------------------

            if not mode.empty:

                for row in mode[
                    mode["TimeUS"]
                    > start
                ].itertuples():

                    event_t = int(
                        row.TimeUS
                    )

                    if (
                        event_t
                        > flight_window.end_us
                    ):
                        break

                    if (
                        mode_name(
                            row.ModeNum
                        )
                        != "AUTO"
                    ):

                        termination_events.append(
                            (
                                event_t,
                                "mode",
                            )
                        )

                        break

            # ----------------------------------------------------
            # GPS groundspeed termination.
            #
            # GPSStopDetector owns the persistence algorithm and
            # publishes the event at the beginning of the sustained
            # low-speed run.
            #
            # GPS is optional evidence. No GPS event is added when
            # the stream is absent or insufficient.
            # ----------------------------------------------------

            gps_stop = (
                gps_stop_detector.detect(
                    flight_log,
                    flight_window,
                    start_us=start,
                )
            )

            if gps_stop is not None:

                termination_events.append(
                    (
                        gps_stop.time_us,
                        "gps",
                    )
                )

            # ----------------------------------------------------
            # Select the earliest termination.
            #
            # If no explicit event or GPS persistence occurs,
            # the parent FlightWindow remains the boundary.
            # ----------------------------------------------------

            if termination_events:

                termination_events.sort(
                    key=lambda item:
                    item[0]
                )

                (
                    end_limit,
                    end_reason,
                ) = (
                    termination_events[0]
                )

            else:

                end_limit = (
                    flight_window.end_us
                )

                end_reason = (
                    "flight_window_end"
                )

            # ----------------------------------------------------
            # Return the bounded landing attempt.
            # ----------------------------------------------------

            if end_limit > start:

                windows.append(
                    LandingWindow(
                        start_us=int(
                            start
                        ),
                        end_us=int(
                            end_limit
                        ),
                        end_reason=(
                            end_reason
                        ),
                    )
                )

        return windows
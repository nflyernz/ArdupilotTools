"""
Landing window detector.
"""

from core.config import Config
from core.model import FlightLog
from core.flight_window import FlightWindow
from core.landing_window import LandingWindow
from core.scope import validate_flight_window
from core.modes import mode_name


class LandingWindowDetector:

    def __init__(self):
        self.config = Config("Config/landing.yaml")

    def detect(self, flight_log, flight_window):
        validate_flight_window(flight_log, flight_window)

        land = flight_log.get("LAND")
        gps = flight_log.get("GPS")
        msg = flight_log.get("MSG")
        mode = flight_log.get("MODE")

        if land.empty or gps.empty:
            return []

        start_rows = land[
            (land["TimeUS"] >= flight_window.start_us) &
            (land["TimeUS"] <= flight_window.end_us) &
            (land["stage"] == 1) &
            (land["stage"].shift() != 1)
        ]

        # --------------------------------------------------------
        # Only accept LAND.stage 1 as a landing attempt when the
        # aircraft is in AUTO at the time of the transition.
        #
        # Find the most recent MODE record at or before each
        # stage-1 transition.
        # --------------------------------------------------------

        valid_starts = []

        for start in start_rows["TimeUS"].astype(int):

            if mode.empty:
                continue

            mode_rows = mode[
                (mode["TimeUS"] <= start)
            ]

            if mode_rows.empty:
                continue

            current_mode = mode_rows.iloc[-1]

            if mode_name(current_mode["ModeNum"]) != "AUTO":
                continue

            valid_starts.append(start)

        speed_limit = float(
            self.config.get(
                "landing_window.end_speed",
                3.0,
            )
        )

        persist = float(
            self.config.get(
                "landing_window.end_speed_seconds",
                2.0,
            )
        ) * 1_000_000

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
            # Landing abort / disarm messages
            # ----------------------------------------------------

            if not msg.empty:

                for row in msg[msg["TimeUS"] > start].itertuples():

                    event_t = int(row.TimeUS)

                    if event_t > flight_window.end_us:
                        break

                    text = str(row.Message).lower()

                    if "landing aborted" in text:
                        termination_events.append(
                            (event_t, "abort")
                        )

                    elif "throttle disarmed" in text:
                        termination_events.append(
                            (event_t, "disarm")
                        )

            # ----------------------------------------------------
            # Mode changes
            #
            # MODE messages are independent of GPS sampling.
            # The first transition away from AUTO terminates the
            # current landing attempt.
            # ----------------------------------------------------

            if not mode.empty:

                for row in mode[mode["TimeUS"] > start].itertuples():

                    event_t = int(row.TimeUS)

                    if event_t > flight_window.end_us:
                        break

                    if mode_name(row.ModeNum) != "AUTO":
                        termination_events.append(
                            (event_t, "mode")
                        )
                        break

            # ----------------------------------------------------
            # LAND.stage 0
            #
            # Stage 0 is retained as event information but does
            # not itself terminate the landing window.
            # ----------------------------------------------------

            if not land.empty:

                for row in land[land["TimeUS"] > start].itertuples():

                    event_t = int(row.TimeUS)

                    if event_t > flight_window.end_us:
                        break

                    if row.stage == 0:
                        continue

            # ----------------------------------------------------
            # GPS groundspeed termination
            #
            # This is calculated independently of the event
            # stream, so a DISARM, MODE change, or ABORT does not
            # require another GPS sample to be detected.
            # ----------------------------------------------------

            below_since = None
            gps_end = None

            gps_rows = gps[
                (gps["TimeUS"] >= start) &
                (gps["TimeUS"] <= flight_window.end_us)
            ]

            for row in gps_rows.itertuples():

                t = int(row.TimeUS)
                speed = float(row.Spd)

                if speed < speed_limit:

                    if below_since is None:
                        below_since = t

                    elif t - below_since >= persist:
                        gps_end = below_since
                        break

                else:
                    below_since = None

            if gps_end is not None:
                termination_events.append(
                    (gps_end, "gps")
                )

            # ----------------------------------------------------
            # Select the earliest termination.
            #
            # If no explicit event or GPS persistence occurs,
            # the parent flight window remains the boundary.
            # ----------------------------------------------------

            if termination_events:

                termination_events.sort(
                    key=lambda item: item[0]
                )

                end_limit = termination_events[0][0]

            else:
                end_limit = flight_window.end_us

            # ----------------------------------------------------
            # Return the bounded landing attempt.
            # ----------------------------------------------------

            if end_limit > start:

                windows.append(
                    LandingWindow(
                        start_us=int(start),
                        end_us=int(end_limit),
                    )
                )

        return windows
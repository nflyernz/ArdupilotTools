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

        speed_limit = float(
            self.config.get("landing_window.end_speed", 3.0)
        )
        persist = float(
            self.config.get("landing_window.end_speed_seconds", 2.0)
        ) * 1_000_000

        windows = []

        for start in start_rows["TimeUS"].astype(int):

            events = []

            for row in msg[msg["TimeUS"] > start].itertuples():
                text = str(row.Message).lower()
                if "landing aborted" in text:
                    events.append((int(row.TimeUS), "abort"))
                elif "throttle disarmed" in text:
                    events.append((int(row.TimeUS), "disarm"))

            for row in mode[mode["TimeUS"] > start].itertuples():
                if mode_name(row.ModeNum) != "AUTO":
                    events.append((int(row.TimeUS), "mode"))

            for row in land[land["TimeUS"] > start].itertuples():
                if row.stage == 0:
                    events.append((int(row.TimeUS), "stage0"))

            events.sort()

            end_limit = flight_window.end_us
            below_since = None

            gps_rows = gps[gps["TimeUS"] >= start]

            for row in gps_rows.itertuples():

                t = int(row.TimeUS)

                if t > end_limit:
                    break

                while events and events[0][0] <= t:
                    event_t, event_type = events.pop(0)

                    if event_type == "abort":
                        end_limit = None
                        break

                    if event_type == "stage0":
                        continue

                    end_limit = event_t
                    break

                if end_limit is None:
                    break

                if t > end_limit:
                    break

                if float(row.Spd) < speed_limit:
                    if below_since is None:
                        below_since = t
                    elif t - below_since >= persist:
                        end_limit = below_since
                        break
                else:
                    below_since = None

            if end_limit is not None and end_limit > start:
                windows.append(
                    LandingWindow(
                        start_us=int(start),
                        end_us=int(end_limit),
                    )
                )

        return windows
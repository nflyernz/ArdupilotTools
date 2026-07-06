from pathlib import Path

import pandas as pd

from pymavlink import mavutil

from .model import FlightLog


class FlightReader:

    def __init__(self, filename):

        self.filename = Path(filename)

    def read(self):

        wanted = {
            "MODE",
            "ATT",
            "AETR",
            "ARSP",
            "RFND",
            "TECS",
            "TEC2",
            "TEC3",
        }

        rows = {m: [] for m in wanted}

        log = mavutil.mavlink_connection(str(self.filename))

        while True:

            msg = log.recv_match()

            if msg is None:
                break

            name = msg.get_type()

            if name in wanted:

                rows[name].append(msg.to_dict())

        data = {}

        for name in wanted:

            data[name] = pd.DataFrame(rows[name])

        return FlightLog(data)

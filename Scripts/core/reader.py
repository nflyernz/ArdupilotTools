from pathlib import Path

import pandas as pd
from pymavlink import mavutil

from .config import Config
from .model import FlightLog
from .params import ParameterReader
from .segmentation import FlightSegmenter


class FlightReader:

    def __init__(self, filename):

        self.filename = Path(filename)
        self.config = Config("Config/landing.yaml")

    def read(self):

        flight = FlightLog()

        flight.messages = self._read_messages()

        self._read_parameters(flight)

        self._build_segments(flight)

        flight.metadata["log_file"] = str(self.filename)

        return flight

    def _read_messages(self):

        wanted = set(self.config.get("messages"))

        rows = {m: [] for m in wanted}

        log = mavutil.mavlink_connection(str(self.filename))

        while True:

            msg = log.recv_match()

            if msg is None:
                break

            name = msg.get_type()

            if name not in wanted:
                continue

            rows[name].append(msg.to_dict())

        messages = {}

        for name, records in rows.items():

            if records:
                messages[name] = pd.DataFrame(records)
            else:
                messages[name] = pd.DataFrame()

        return messages

    def _read_parameters(self, flight):

        paramfile = Path("Params") / (self.filename.stem + ".params")

        if not paramfile.exists():
            return

        reader = ParameterReader(
            paramfile,
            self.config
        )

        flight.parameters = reader.read()

        flight.metadata["parameter_file"] = str(paramfile)

    def _build_segments(self, flight):

        segmenter = FlightSegmenter(flight)

        flight.segments = segmenter.mode_segments()

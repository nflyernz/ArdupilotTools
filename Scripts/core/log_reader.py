from pathlib import Path

import pandas as pd
from pymavlink import mavutil

from .config import Config
from .flight_data import FlightLog
from .params import ParameterReader
from .flight_segmenter import FlightSegmenter
from .flight_window_detector import FlightWindowDetector


class UnsupportedFirmwareError(ValueError):
    """Log firmware is not supported by this analysis."""


class FlightReader:

    def __init__(self, filename):
        self.filename = Path(filename)
        self.config = Config("Config/landing.yaml")

    def read(self):
        flight = FlightLog()

        flight.messages = self._read_messages()

        self._validate_firmware(flight)
        self._read_parameters(flight)
        self._build_flights(flight)
        self._build_segments(flight)

        flight.metadata["log_file"] = str(self.filename)

        return flight

    def _validate_firmware(self, flight):
        version = flight.firmware_version()

        if version is None:
            raise UnsupportedFirmwareError(
                "no usable ArduPilot VER message found"
            )

        text = version["version"]

        if not text.startswith("ArduPlane "):
            raise UnsupportedFirmwareError(
                f"unsupported firmware: {text}"
            )

        if version["major"] != 4 or version["minor"] != 7:
            raise UnsupportedFirmwareError(
                f"{text}; v0.4 requires ArduPlane 4.7.x"
            )

    def _read_messages(self):
        wanted = set(self.config.get("messages"))
        rows = {name: [] for name in wanted}

        log = mavutil.mavlink_connection(str(self.filename))

        while True:
            msg = log.recv_match()

            if msg is None:
                break

            name = msg.get_type()

            if name in wanted:
                rows[name].append(msg.to_dict())

        messages = {}

        for name, records in rows.items():
            messages[name] = (
                pd.DataFrame(records)
                if records
                else pd.DataFrame()
            )

        return messages

    def _read_parameters(self, flight):
        paramfile = Path("Params") / (
            self.filename.stem + ".params"
        )

        flight.metadata["parameter_file"] = str(paramfile)
        flight.metadata["parameters_loaded"] = paramfile.exists()

        if not paramfile.exists():
            return

        flight.parameters = ParameterReader(
            paramfile,
            self.config,
        ).read()

    def _build_flights(self, flight):
        flight.flights = FlightWindowDetector().detect(flight)

    def _build_segments(self, flight):
        flight.segments = FlightSegmenter(
            flight
        ).mode_segments()
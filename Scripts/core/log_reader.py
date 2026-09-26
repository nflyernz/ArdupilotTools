import math
from pathlib import Path

import pandas as pd
from pymavlink import mavutil

from .config import Config
from .flight_data import FlightLog
from .flight_segmenter import FlightSegmenter
from .flight_window_detector import FlightWindowDetector
from .params import ParameterHistory, ParameterReader


class UnsupportedFirmwareError(ValueError):
    """Log firmware is not supported by this analysis."""


class FlightReader:

    def __init__(
        self,
        filename,
        config=None,
    ):
        self.filename = Path(filename)
        self.config = config or Config("Config/landing.yaml")

    def read(self):
        flight = FlightLog()

        (
            flight.messages,
            flight.parameter_history,
            decoded_metadata,
        ) = self._read_messages()
        flight.metadata.update(decoded_metadata)

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
        wanted.update(("MISE", "PARM", "POS", "STAT", "TECS"))
        rows = {name: [] for name in wanted}

        log = mavutil.mavlink_connection(str(self.filename))
        source_order = -1
        last_time_us = None

        while True:
            msg = log.recv_match()

            if msg is None:
                break

            name = msg.get_type()
            if name == "BAD_DATA":
                continue
            source_order += 1
            record = msg.to_dict()
            timestamp = record.get("TimeUS")
            if (
                isinstance(timestamp, (int, float))
                and math.isfinite(timestamp)
                and timestamp >= 0
                and int(timestamp) == timestamp
            ):
                last_time_us = int(timestamp)

            if name in wanted:
                record["_SourceOrder"] = source_order
                rows[name].append(record)

        messages = {}

        for name, records in rows.items():
            messages[name] = (
                pd.DataFrame(records)
                if records
                else pd.DataFrame()
            )

        parameter_history = ParameterHistory.from_records(rows["PARM"])

        return messages, parameter_history, {
            "last_decoded_source_order": source_order if source_order >= 0 else None,
            "last_decoded_time_us": last_time_us,
        }

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

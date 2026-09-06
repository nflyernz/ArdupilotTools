from dataclasses import dataclass, field
from typing import Dict, List, Any

import pandas as pd

from .flight_window import FlightWindow
from .params import ParameterHistory


@dataclass
class FlightLog:
    """
    Container for a decoded ArduPilot flight log.

    This is the central object passed to all analyzers.
    """

    # Decoded MAVLink messages
    messages: Dict[str, pd.DataFrame] = field(default_factory=dict)

    # Loaded from matching .params file
    parameters: Dict[str, Any] = field(default_factory=dict)

    # Reconstructed from timestamped PARM records in the BIN log
    parameter_history: ParameterHistory = field(
        default_factory=ParameterHistory
    )

    # Individual flights detected within the log
    flights: List[FlightWindow] = field(default_factory=list)

    # Derived from MODE messages
    segments: List = field(default_factory=list)

    # Derived events (touchdown, flare, etc.)
    events: List = field(default_factory=list)

    # General information about the flight
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get(self, name: str) -> pd.DataFrame:
        """
        Return a message dataframe.
        """
        return self.messages.get(name, pd.DataFrame())

    def has(self, name: str) -> bool:
        """
        True if the message exists and contains rows.
        """
        return (
            name in self.messages
            and not self.messages[name].empty
        )

    def message_types(self) -> List[str]:
        """
        Return sorted list of available message types.
        """
        return sorted(self.messages.keys())

    def seconds(self, name: str):
        """
        Return message time in seconds from the first sample.
        """
        df = self.get(name)

        if df.empty:
            return None

        return (df["TimeUS"] - df["TimeUS"].iloc[0]) / 1e6

    def param(self, name: str, default=None):
        """
        Return a parameter value.
        """
        return self.parameters.get(name, default)

    def has_param(self, name: str) -> bool:
        """
        True if a parameter exists.
        """
        return name in self.parameters

    def firmware_version(self):
        """
        Return firmware version information from the BIN VER message.

        Returns:
            dict or None:
                {
                    "major": int,
                    "minor": int,
                    "patch": int,
                    "version": str,
                }

        Returns None if no usable VER message is present.
        """

        ver = self.get("VER")

        if ver.empty:
            return None

        row = ver.iloc[0]

        return {
            "major": int(row["Maj"]),
            "minor": int(row["Min"]),
            "patch": int(row["Pat"]),
            "version": str(row["FWS"]),
        }

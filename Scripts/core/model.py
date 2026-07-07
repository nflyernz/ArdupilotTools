from dataclasses import dataclass, field
from typing import Dict, List, Any

import pandas as pd


@dataclass
class FlightLog:
    """
    Container for a decoded ArduPilot flight.

    This is the central object passed to all analyzers.
    """

    # Decoded MAVLink messages
    messages: Dict[str, pd.DataFrame] = field(default_factory=dict)

    # Loaded from matching .params file
    parameters: Dict[str, Any] = field(default_factory=dict)

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

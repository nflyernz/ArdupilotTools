from dataclasses import dataclass, field
from typing import Dict, List

import pandas as pd


@dataclass
class FlightLog:
    """
    Container for all decoded log messages.
    """

    messages: Dict[str, pd.DataFrame] = field(default_factory=dict)

    def get(self, name: str) -> pd.DataFrame:
        """
        Return a message dataframe.
        """

        return self.messages.get(name, pd.DataFrame())

    def has(self, name: str) -> bool:
        """
        True if message exists and contains rows.
        """

        return (
            name in self.messages
            and not self.messages[name].empty
        )

    def message_types(self) -> List[str]:

        return sorted(self.messages.keys())

    def seconds(self, name: str):

        df = self.get(name)

        if df.empty:
            return None

        return (df["TimeUS"] - df["TimeUS"].iloc[0]) / 1e6

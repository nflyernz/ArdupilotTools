from dataclasses import dataclass, field
from enum import Enum


class EventType(Enum):

    # Firmware messages (MSG log)
    MSG = "MSG"

    # Flight mode changes
    MODE = "MODE"

    # Arm / disarm
    ARM = "ARM"

    # Landing stages
    LAND_STAGE = "LAND_STAGE"

    # Rangefinder events
    RFND_FIRST_NONZERO = "RFND_FIRST_NONZERO"

    RFND_FIRST_IN_RANGE = "RFND_FIRST_IN_RANGE"

    RFND_CONTINUOUS = "RFND_CONTINUOUS"

    RFND_DISENGAGED = "RFND_DISENGAGED"

    # Derived events
    TOUCHDOWN = "TOUCHDOWN"

    GPS_STOPPED = "GPS_STOPPED"


@dataclass(order=True, slots=True)
class TimelineEvent:
    """
    A timestamped event in the flight timeline.

    Events may originate from:
      - ArduPilot firmware messages (MSG)
      - Flight mode changes
      - Derived analysis (touchdown, GPS stop, etc.)
      - Sensor events
    """

    time_us: int

    event: EventType = field(compare=False)

    detail: str = field(default="", compare=False)

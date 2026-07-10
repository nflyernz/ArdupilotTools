from dataclasses import dataclass
from enum import Enum


class EventType(Enum):

    LAND_STAGE = "LAND_STAGE"

    MODE = "MODE"

    ARM = "ARM"

    RANGEFINDER_FIRST_DATA = "RFND_FIRST_DATA"

    RANGEFINDER_IN_RANGE = "RFND_IN_RANGE"

    TOUCHDOWN = "TOUCHDOWN"

    GPS_STOPPED = "GPS_STOPPED"


@dataclass(order=True)
class TimelineEvent:

    time_us: int

    event: EventType

    detail: str = ""

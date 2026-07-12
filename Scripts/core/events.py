from dataclasses import dataclass, field
from enum import Enum


class EventType(Enum):

    LAND_STAGE = "LAND_STAGE"

    MODE = "MODE"

    ARM = "ARM"

    RFND_FIRST_NONZERO = "RFND_FIRST_NONZERO"

    RFND_FIRST_IN_RANGE = "RFND_FIRST_IN_RANGE"

    RFND_CONTINUOUS = "RFND_CONTINUOUS"

    TOUCHDOWN = "TOUCHDOWN"

    GPS_STOPPED = "GPS_STOPPED"


@dataclass(order=True)
class TimelineEvent:

    time_us: int

    event: EventType = field(compare=False)

    detail: str = field(default="", compare=False)

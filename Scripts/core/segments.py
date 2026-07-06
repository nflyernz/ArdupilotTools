from dataclasses import dataclass


@dataclass
class ModeSegment:
    mode: str
    start_us: int
    end_us: int
    duration_s: float

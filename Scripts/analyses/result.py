from dataclasses import dataclass, field
from pathlib import Path

from core.flight_window import FlightWindow
from core.landing_window import LandingWindow
from core.sensor_health_window import SensorHealthWindow


@dataclass(slots=True)
class AnalysisResult:
    log_path: Path
    flight_window: FlightWindow



    sensor_health_window: SensorHealthWindow | None = None
    sensor_health: object | None = None

    landing_windows: list[LandingWindow] = field(
        default_factory=list
    )

    report: object | None = None
from dataclasses import dataclass
from pathlib import Path

from core.flight_window import FlightWindow


@dataclass(slots=True)
class AnalysisResult:
    log_path: Path
    flight_window: FlightWindow

    telemetry: object | None = None
    sensor_health: object | None = None
    report: object | None = None
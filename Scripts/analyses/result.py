from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class AnalysisResult:

    log_path: Path

    telemetry: Any = None

    window: Any = None

    sensor_health: Any = None

    report: Any = None

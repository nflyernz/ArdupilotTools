"""User-facing workflow for Plane TAKEOFF-mode performance analysis."""

from pathlib import Path

from core.config import Config
from core.log_reader import FlightReader, UnsupportedFirmwareError
from core.takeoff_execution import TakeoffEntryContext
from core.takeoff_execution_detector import TakeoffExecutionDetector
from core.takeoff_performance import (
    TakeoffPerformanceProcessor,
    format_takeoff_performance_reports,
)


class TakeoffAnalysisPresentation:
    """Load one log and present triggered TAKEOFF-mode execution evidence."""

    def __init__(self, config=None):
        self.config = config or Config("Config/landing.yaml")

    def run(self):
        """Select, analyse, and present one DataFlash log."""
        log_path = self._select_log()
        if log_path is None:
            return

        try:
            flight_log = FlightReader(log_path, config=self.config).read()
        except UnsupportedFirmwareError as exc:
            print()
            print("Unsupported firmware.")
            print(exc)
            return
        except OSError as exc:
            print()
            print(f"Unable to read log: {exc}")
            return

        executions = TakeoffExecutionDetector().detect(flight_log)
        takeoff_executions = tuple(
            execution
            for execution in executions
            if execution.entry_context is TakeoffEntryContext.TAKEOFF_MODE
        )
        if not takeoff_executions:
            print()
            print("No TAKEOFF-mode executions found.")
            return

        analyses = tuple(
            analysis
            for execution in takeoff_executions
            if (
                analysis := TakeoffPerformanceProcessor(
                    flight_log,
                    execution,
                ).analyse()
            )
            is not None
        )
        already_airborne_executions = tuple(
            execution
            for execution in takeoff_executions
            if execution.already_airborne_entry is not None
            and execution.launch_trigger is None
        )
        if not analyses and not already_airborne_executions:
            count = len(takeoff_executions)
            noun = "execution" if count == 1 else "executions"
            print()
            print(
                f"{count} TAKEOFF-mode {noun} detected; "
                "none contained a firmware launch trigger."
            )
            return

        print()
        print(
            format_takeoff_performance_reports(
                analyses,
                detected_execution_count=len(takeoff_executions),
                already_airborne_executions=already_airborne_executions,
            )
        )

    @staticmethod
    def _select_log():
        """Select one BIN log using the established interactive list pattern."""
        log_paths = sorted(Path("Logs").glob("*.bin"))
        if not log_paths:
            print()
            print("No BIN logs found in Logs/")
            return None

        print()
        print("Available Logs")
        print("=" * 16)
        for index, log_path in enumerate(log_paths, start=1):
            print(f"{index}. {log_path.name}")
        print("0. Cancel")

        while True:
            choice = input("\nSelection: ").strip()
            if choice == "0":
                return None
            try:
                index = int(choice)
                if 1 <= index <= len(log_paths):
                    return log_paths[index - 1]
            except ValueError:
                pass
            print("Invalid selection.")

"""
Landing analysis workflow.
"""

from pathlib import Path

from analyses.result import AnalysisResult
from core.reader import FlightReader


class LandingAnalysis:
    """
    Landing analysis.

    Workflow:
        1. Select log
        2. Load telemetry
        3. Determine analysis window
        4. Run sensor processors
        5. Generate landing report
    """

    def run(self):

        log_path = self.select_log()

        if log_path is None:
            return None

        telemetry = self.load_telemetry(log_path)

        result = AnalysisResult(
            log_path=log_path,
            telemetry=telemetry,
        )

        print("\nLanding Analysis")
        print("----------------")
        print(f"Log      : {result.log_path.name}")
        print(f"Messages : {len(result.telemetry)}")

        #
        # Future workflow
        #
        # result.window = self.determine_window(result.telemetry)
        #
        # result.sensor_health = self.check_sensor_health(result.window)
        #
        # result.report = self.generate_report(result)
        #

        return result

    def select_log(self):

        filename = input("\nLog file: ").strip()

        if not filename:
            print("No log selected.")
            return None

        path = Path(filename)

        if not path.exists():
            print("Log not found.")
            return None

        return path

    def load_telemetry(self, log_path):

        reader = FlightReader(log_path)

        return reader.read()
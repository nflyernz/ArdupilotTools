"""
Landing analysis workflow.
"""

from pathlib import Path

from analyses.result import AnalysisResult
from core.airspeed import AirspeedProcessor
from core.landing_window_detector import LandingWindowDetector
from core.reader import FlightReader


class LandingAnalysis:
    """
    Landing analysis.

    Workflow:
        1. Select log(s)
        2. Load telemetry
        3. Check sensor health
        4. Determine landing window
        5. Run processors
        6. Generate report
    """

    def run(self):

        logs = self.select_logs()

        if not logs:
            return

        success = 0
        failed = 0

        print("\nLanding Analysis")
        print("----------------")
        print(f"Found {len(logs)} log(s)\n")

        for index, log_path in enumerate(logs, start=1):

            print(f"[{index:>3}/{len(logs)}] {log_path.name}")

            try:

                telemetry = self.load_telemetry(log_path)

                print("  ✓ Loaded")

                airspeed = AirspeedProcessor(telemetry)

                health = airspeed.health()

                if health is None:

                    print("  ✗ Airspeed : No ARSP data")
                
                elif health.validation.valid:
                
                    print("  ✓ Airspeed : PASS")
                
                else:
                
                    print("  ✗ Airspeed : FAIL")
                
                    grouped = {}
                
                    for failure in health.validation.failures:
                
                        grouped.setdefault(
                            failure.rule,
                            []
                        ).append(failure)
                
                    for rule, failures in grouped.items():
                
                        first = failures[0]
                
                        print(
                            f"      {rule:<12}"
                            f"x{len(failures):<2}  "
                            f"first {self.format_time(first.start_us)}"
                        )

                window = LandingWindowDetector().detect(telemetry)

                AnalysisResult(
                    log_path=log_path,
                    telemetry=telemetry,
                    window=window,
                )

                print(
                    f"  ✓ Window    : "
                    f"{self.format_time(window.start_us)} - "
                    f"{self.format_time(window.end_us)}"
                )

                success += 1

            except Exception as ex:

                print(f"  ✗ {ex}")
                failed += 1

            print()

        print("Summary")
        print("-------")
        print(f"Processed : {len(logs)}")
        print(f"Succeeded : {success}")
        print(f"Failed    : {failed}")

    def select_logs(self):

        entry = input("\nLog file or directory: ").strip()

        if not entry:
            print("No log selected.")
            return []

        path = Path(entry)

        if not path.exists():
            print("Path not found.")
            return []

        if path.is_file():
            return [path]

        logs = sorted(path.glob("*.BIN"))
        logs.extend(sorted(path.glob("*.bin")))

        if not logs:
            print("No log files found.")
            return []

        return logs

    def load_telemetry(self, log_path):

        reader = FlightReader(log_path)

        return reader.read()

    @staticmethod
    def format_time(time_us):

        total_ms = time_us // 1000

        minutes = total_ms // 60000
        seconds = (total_ms % 60000) // 1000
        milliseconds = total_ms % 1000

        return f"{minutes:02}:{seconds:02}.{milliseconds:03}"
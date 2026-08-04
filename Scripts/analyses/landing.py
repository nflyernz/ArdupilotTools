"""
Landing analysis workflow.
"""

from pathlib import Path

from analyses.result import AnalysisResult
from core.airspeed import AirspeedProcessor
from core.landing_window_detector import LandingWindowDetector
from core.reader import FlightReader
from core.sensor_health_window import SensorHealthWindowDetector
from core.time import format_time_us


class LandingAnalysis:
    """
    Landing analysis.

    Workflow:
        1. Select log(s)
        2. Load telemetry
        3. Select each FlightWindow
        4. Analyse each FlightWindow
        5. Present the result
        6. Generate one AnalysisResult per FlightWindow
    """

    def analyse(
        self,
        flight_log,
        flight_window,
    ) -> AnalysisResult:
        """
        Analyse one canonical FlightWindow.

        This method performs analysis only. It does not handle
        CLI input or presentation.
        """

        #
        # Sensor health window
        #
        health_window = (
            SensorHealthWindowDetector().detect(
                flight_log,
                flight_window,
            )
        )

        health = None

        if health_window is not None:

            airspeed = AirspeedProcessor(
                flight_log,
                flight_window,
            )

            health = airspeed.health(
                health_window
            )

        #
        # Landing windows
        #
        landing_windows = (
            LandingWindowDetector().detect(
                flight_log,
                flight_window,
            )
        )

        #
        # FlightReader records the source log in metadata.
        #
        log_path = Path(
            flight_log.metadata["log_file"]
        )

        return AnalysisResult(
            log_path=log_path,
            flight_window=flight_window,
            sensor_health_window=health_window,
            sensor_health=health,
            landing_windows=landing_windows,
        )

    def present_result(
        self,
        result: AnalysisResult,
        flight_index: int,
    ):
        """
        Present one FlightWindow analysis result.
        """

        flight_window = result.flight_window

        print()
        print(
            f"  Flight {flight_index}"
        )

        print(
            f"    Window     : "
            f"{format_time_us(flight_window.start_us)} - "
            f"{format_time_us(flight_window.end_us)}"
        )

        #
        # Sensor health
        #
        health_window = result.sensor_health_window
        health = result.sensor_health

        if health_window is None:

            print(
                "    ✗ Health    : "
                "No valid sensor-health window"
            )

        else:

            print(
                f"    ✓ Health    : "
                f"{format_time_us(health_window.start_us)} - "
                f"{format_time_us(health_window.end_us)}"
            )

            if health is None:

                print(
                    "    ✗ Airspeed  : "
                    "No ARSP data"
                )

            elif health.validation.valid:

                print(
                    "    ✓ Airspeed  : PASS"
                )

            else:

                print(
                    "    ✗ Airspeed  : FAIL"
                )

                grouped = {}

                for failure in health.validation.failures:

                    grouped.setdefault(
                        failure.rule,
                        [],
                    ).append(failure)

                for rule, failures in grouped.items():

                    first = failures[0]

                    print(
                        f"        {rule:<12}"
                        f"x{len(failures):<2}  "
                        f"first "
                        f"{format_time_us(first.start_us)}"
                    )

        #
        # Landing windows
        #
        print(
            f"    Landing windows : "
            f"{len(result.landing_windows)}"
        )

        for landing_index, landing_window in enumerate(
            result.landing_windows,
            start=1,
        ):

            print(
                f"      {landing_index}: "
                f"{format_time_us(landing_window.start_us)} - "
                f"{format_time_us(landing_window.end_us)}"
            )

    def run(self):

        logs = self.select_logs()

        if not logs:
            return []

        results = []
        framework_errors = 0

        print("\nLanding Analysis")
        print("----------------")
        print(f"Found {len(logs)} log(s)\n")

        for log_index, log_path in enumerate(
            logs,
            start=1,
        ):

            print(
                f"[{log_index:>3}/{len(logs)}] "
                f"{log_path.name}"
            )

            try:

                flight_log = self.load_telemetry(
                    log_path
                )

                print(
                    f"  ✓ Loaded     : "
                    f"{len(flight_log.flights)} flight(s)"
                )

                if not flight_log.flights:

                    print("  ✗ No flights detected")
                    print()
                    continue

                for flight_index, flight_window in enumerate(
                    flight_log.flights,
                    start=1,
                ):

                    result = self.analyse(
                        flight_log,
                        flight_window,
                    )

                    results.append(result)

                    self.present_result(
                        result,
                        flight_index,
                    )

            except Exception as ex:

                print(f"  ✗ {ex}")
                framework_errors += 1

            print()

        print("Summary")
        print("-------")
        print(f"Logs            : {len(logs)}")
        print(f"Flight Results  : {len(results)}")
        print(f"Framework Errors: {framework_errors}")

        return results

    def select_logs(self):

        entry = input(
            "\nLog file or directory: "
        ).strip()

        if not entry:

            print("No log selected.")
            return []

        path = Path(entry)

        if not path.exists():

            print("Path not found.")
            return []

        if path.is_file():

            return [path]

        logs = sorted(
            path.glob("*.BIN")
        )

        logs.extend(
            sorted(
                path.glob("*.bin")
            )
        )

        if not logs:

            print("No log files found.")
            return []

        return logs

    def load_telemetry(
        self,
        log_path,
    ):

        reader = FlightReader(
            log_path
        )

        return reader.read()
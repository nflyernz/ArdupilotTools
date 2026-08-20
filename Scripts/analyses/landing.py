"""
Landing analysis workflow.

User-facing presentation for the landing-analysis pipeline.
"""

from pathlib import Path

from analyses.result import AnalysisResult

from core.config import Config
from core.landing_attempt_extractor import (
    LandingAttemptExtractor,
)
from core.landing_attempt_processor import (
    LandingAttemptProcessor,
)
from core.landing_window_detector import (
    LandingWindowDetector,
)
from core.log_reader import (
    FlightReader,
    UnsupportedFirmwareError,
)
from core.time import format_time_us


class LandingAnalysis:
    """
    Landing analysis.

    Workflow:

        1. Select log(s)
        2. Load telemetry
        3. Process each FlightWindow
        4. Detect LandingWindows
        5. Extract LandingAttempts
        6. Build measured landing evidence
        7. Present the result

    Core landing-analysis code is responsible for measurement and
    event extraction. This class handles workflow and presentation.
    """

    def __init__(
        self,
        config=None,
    ):
        self.config = config or Config("Config/landing.yaml")

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

        landing_windows = (
            LandingWindowDetector(self.config).detect(
                flight_log,
                flight_window,
            )
        )

        analyses = []

        extractor = LandingAttemptExtractor(
            flight_log
        )

        for landing_index, landing_window in enumerate(
            landing_windows,
            start=1,
        ):

            attempts = extractor.extract(
                landing_window
            )

            for attempt_index, attempt in enumerate(
                attempts,
                start=1,
            ):

                analysis = LandingAttemptProcessor(
                    flight_log,
                    flight_window,
                    landing_window,
                    attempt,
                    self.config,
                ).build()

                analyses.append(
                    (
                        landing_index,
                        attempt_index,
                        analysis,
                    )
                )

        log_path = Path(
            flight_log.metadata["log_file"]
        )

        return AnalysisResult(
            flight_log=flight_log,
            log_path=log_path,
            flight_window=flight_window,
            landing_windows=landing_windows,
            report=analyses,
        )

    def present_result(
        self,
        result: AnalysisResult,
        flight_index: int,
    ):
        """
        Present one FlightWindow landing-analysis result.
        """

        print()
        print("=" * 70)
        print()
        print(
            f"FLIGHT {flight_index}"
        )
        print()
        print("=" * 70)

        analyses = result.report or []

        if not analyses:
            print()
            print("No landing attempts detected.")
            return

        for (
            landing_index,
            attempt_index,
            analysis,
        ) in analyses:

            self._present_attempt(
                landing_index,
                attempt_index,
                analysis,
            )

    def _present_attempt(
        self,
        landing_index,
        attempt_index,
        analysis,
    ):
        """
        Present one LandingAttemptAnalysis.
        """

        attempt = analysis.attempt

        print()
        print(
            f"Landing {landing_index} "
            f"Attempt {attempt_index}"
        )
        print("-" * 70)

        self._row(
            "Window",
            (
                f"{format_time_us(attempt.start_us)} -> "
                f"{format_time_us(attempt.end_us)}"
            ),
        )

        self._row(
            "Duration",
            self._value(
                analysis.duration_s,
                2,
                " s",
            ),
        )

        #
        # Approach
        #

        print()
        print("APPROACH")

        self._row(
            "Approach altitude",
            self._value(
                analysis.approach_start_altitude,
                1,
                " m",
            ),
        )

        self._row(
            "Glide slope",
            self._value(
                analysis.glide_slope_degrees,
                1,
                " deg",
            ),
        )

        #
        # Preflare
        #

        print()
        print("PREFLARE")

        self._row(
            "Time",
            self._time(
                analysis.preflare_time_us
            ),
        )

        self._row(
            "Preflare height",
            self._value(
                analysis.preflare_altitude,
                2,
                " m",
            ),
        )

        self._row(
            "Airspeed",
            self._value(
                analysis.preflare_airspeed,
                2,
                " m/s",
            ),
        )

        self._row(
            "GPS groundspeed",
            self._value(
                analysis.preflare_gps_speed,
                2,
                " m/s",
            ),
        )

        self._row(
            "Sink rate",
            self._value(
                analysis.preflare_sink_rate,
                2,
                " m/s",
            ),
        )

        #
        # Flare
        #

        print()
        print("FLARE")

        self._row(
            "Time",
            self._time(
                analysis.flare_time_us
            ),
        )

        self._row(
            "Flare-timing height",
            self._value(
                analysis.flare_altitude,
                2,
                " m",
            ),
        )

        self._row(
            "Sink rate",
            self._value(
                analysis.flare_sink_rate,
                2,
                " m/s",
            ),
        )

        self._row(
            "Airspeed",
            self._value(
                analysis.flare_airspeed,
                2,
                " m/s",
            ),
        )

        self._row(
            "GPS groundspeed",
            self._value(
                analysis.flare_gps_speed,
                2,
                " m/s",
            ),
        )

        self._row(
            "Flare distance to target",
            self._value(
                analysis.flare_distance,
                1,
                " m",
            ),
        )

        #
        # Rangefinder
        #
        # Rangefinder is optional. Only display this section when
        # rangefinder evidence exists for the attempt.
        #

        if self._has_rangefinder_evidence(
            analysis
        ):

            print()
            print("RANGEFINDER")

            self._row(
                "First non-zero",
                self._time(
                    analysis
                    .rangefinder_first_nonzero_time_us
                ),
            )

            self._row(
                "First distance",
                self._value(
                    analysis
                    .rangefinder_first_nonzero_distance,
                    2,
                    " m",
                ),
            )

            self._row(
                "First in range",
                self._time(
                    analysis
                    .rangefinder_first_in_range_time_us
                ),
            )

            self._row(
                "In-range distance",
                self._value(
                    analysis
                    .rangefinder_first_in_range_distance,
                    2,
                    " m",
                ),
            )

            self._row(
                "Continuous from",
                self._time(
                    analysis
                    .rangefinder_continuous_time_us
                ),
            )

        #
        # Landing / rollout completion
        #

        print()
        print("LANDING / ROLLOUT COMPLETION")

        if analysis.gps_stop_time_us is not None:

            self._row(
                "GPS stop",
                self._time(
                    analysis.gps_stop_time_us
                ),
            )

            self._row(
                "Flare -> stop",
                self._value(
                    analysis.flare_to_gps_stop_s,
                    2,
                    " s",
                ),
            )

            self._row(
                "Distance from target",
                self._value(
                    analysis
                    .landing_end_target_distance_m,
                    1,
                    " m",
                ),
            )

        self._row(
            "End reason",
            self._end_reason(
                analysis.end_reason
            ),
        )

    def run(self):
        """
        Run landing analysis from the CLI menu.
        """

        logs = self.select_logs()

        if not logs:
            return []

        results = []
        framework_errors = 0

        print()
        print("Landing Analysis")
        print("=" * 70)

        print()
        print(
            f"Found {len(logs)} log(s)"
        )

        for log_index, log_path in enumerate(
            logs,
            start=1,
        ):

            print()
            print(
                f"[{log_index:>3}/{len(logs)}] "
                f"{log_path.name}"
            )

            try:

                flight_log = self.load_telemetry(
                    log_path
                )

                print(
                    f"Loaded: "
                    f"{len(flight_log.flights)} "
                    f"flight(s)"
                )

                if not flight_log.flights:
                    print(
                        "No flights detected."
                    )
                    continue

                for (
                    flight_index,
                    flight_window,
                ) in enumerate(
                    flight_log.flights,
                    start=1,
                ):

                    result = self.analyse(
                        flight_log,
                        flight_window,
                    )

                    results.append(
                        result
                    )

                    self.present_result(
                        result,
                        flight_index,
                    )

            except UnsupportedFirmwareError as ex:

                print(
                    f"Unsupported firmware: {ex}"
                )

                framework_errors += 1

            except OSError as ex:

                print(
                    f"Unable to read log: {ex}"
                )

                framework_errors += 1

        print()
        print("=" * 70)
        print()
        print("SUMMARY")
        print()

        self._row(
            "Logs",
            str(len(logs)),
        )

        self._row(
            "Flight results",
            str(len(results)),
        )

        self._row(
            "Framework errors",
            str(framework_errors),
        )

        return results

    def select_logs(self):
        """
        Select one BIN log or all BIN logs in a directory.
        """

        entry = input(
            "\nLog file or directory: "
        ).strip()

        if not entry:

            print(
                "No log selected."
            )

            return []

        path = Path(entry)

        if not path.exists():

            print(
                "Path not found."
            )

            return []

        if path.is_file():

            return [
                path
            ]

        logs = sorted(
            path.glob("*.BIN")
        )

        logs.extend(
            sorted(
                path.glob("*.bin")
            )
        )

        if not logs:

            print(
                "No log files found."
            )

            return []

        return logs

    def load_telemetry(
        self,
        log_path,
    ):
        """
        Load one ArduPilot BIN log.
        """

        reader = FlightReader(
            log_path,
            config=self.config,
        )

        return reader.read()

    @staticmethod
    def _row(
        label,
        value,
    ):
        """
        Print one aligned report row.
        """

        print(
            f"{label:<28}{value}"
        )

    @staticmethod
    def _value(
        value,
        decimals=2,
        suffix="",
    ):
        """
        Format an optional numeric value.
        """

        if value is None:
            return "Unavailable"

        return (
            f"{value:.{decimals}f}"
            f"{suffix}"
        )

    @staticmethod
    def _time(
        time_us,
    ):
        """
        Format an optional TimeUS value.
        """

        if time_us is None:
            return "Unavailable"

        return format_time_us(
            time_us
        )

    @staticmethod
    def _has_rangefinder_evidence(
        analysis,
    ):
        """
        True when the attempt contains rangefinder evidence.

        Rangefinder is an optional sensor.
        """

        return any(
            value is not None
            for value in (
                analysis
                .rangefinder_first_nonzero_time_us,

                analysis
                .rangefinder_first_nonzero_distance,

                analysis
                .rangefinder_first_in_range_time_us,

                analysis
                .rangefinder_first_in_range_distance,

                analysis
                .rangefinder_continuous_time_us,
            )
        )

    @staticmethod
    def _end_reason(
        reason,
    ):
        """
        Convert internal landing-window termination reason into
        user-facing factual wording.
        """

        labels = {
            "gps": "GPS stop",
            "abort": "Landing aborted",
            "flight_window_end": (
                "Flight ended before landing stop detected"
            ),
        }

        return labels.get(
            reason,
            str(reason),
        )

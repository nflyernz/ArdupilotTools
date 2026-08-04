from dataclasses import dataclass, field

import pandas as pd
import yaml

from .flight_window import FlightWindow
from .model import FlightLog
from .scope import (
    filter_telemetry,
    validate_child_window,
    validate_flight_window,
)
from .time import native_rate


# ============================================================
# Validation
# ============================================================

@dataclass
class AirspeedValidationFailure:
    rule: str
    description: str
    criteria: dict
    evidence: dict
    recommendation: str | None = None
    start_us: int | None = None
    end_us: int | None = None

    def __str__(self):

        lines = [
            f"Rule           : {self.rule}",
            f"Description    : {self.description}",
            f"Criteria       : {self.criteria}",
            f"Evidence       : {self.evidence}",
        ]

        if self.recommendation:

            lines.append(
                f"Recommendation : {self.recommendation}"
            )

        if self.start_us is not None:

            lines.append(
                f"Start Time     : "
                f"{self.start_us / 1_000_000:.3f} s"
            )

        if self.end_us is not None:

            lines.append(
                f"End Time       : "
                f"{self.end_us / 1_000_000:.3f} s"
            )

        return "\n".join(lines)


@dataclass
class AirspeedValidationReport:
    valid: bool = True
    rules_evaluated: int = 0
    failures: list[AirspeedValidationFailure] = field(
        default_factory=list
    )

    def add(
        self,
        failure: AirspeedValidationFailure,
    ):

        self.failures.append(failure)
        self.valid = False


# ============================================================
# Summary
# ============================================================

@dataclass
class AirspeedSummary:
    start_speed: float
    end_speed: float
    minimum_speed: float
    maximum_speed: float
    mean_speed: float


# ============================================================
# Analysis
# ============================================================

@dataclass
class AirspeedAnalysis:
    start_us: int
    end_us: int

    native_rate: float
    requested_rate: float

    summary: AirspeedSummary
    profile: pd.DataFrame
    validation: AirspeedValidationReport


# ============================================================
# Processor
# ============================================================

class AirspeedProcessor:

    def __init__(
        self,
        flight_log: FlightLog,
        flight_window: FlightWindow,
        sample_period=1.0,
        config_file="Config/sensors.yaml",
    ):

        validate_flight_window(
            flight_log,
            flight_window,
        )

        self.flight_log = flight_log
        self.flight_window = flight_window
        self.sample_period = sample_period

        with open(config_file, "r") as fp:
            config = yaml.safe_load(fp)

        self.config = config["airspeed"]

    # --------------------------------------------------------

    def health(
        self,
        sensor_health_window,
    ):

        return self._process(
            sensor_health_window
        )

    # --------------------------------------------------------

    def analyse(
        self,
        analysis_window=None,
    ):

        if analysis_window is None:
            analysis_window = self.flight_window

        return self._process(
            analysis_window
        )

    # --------------------------------------------------------

    def _process(
        self,
        window,
    ):

        validate_child_window(
            self.flight_window,
            window,
        )

        arsp = filter_telemetry(
            self.flight_log.get("ARSP"),
            window,
        )

        if arsp is None or arsp.empty:
            return None

        arsp = arsp.copy()

        measured_native_rate = native_rate(
            arsp.TimeUS
        )

        summary = self._build_summary(arsp)
        validation = self._validate(arsp)
        profile = self._build_profile(arsp)

        return AirspeedAnalysis(
            start_us=int(arsp.TimeUS.iloc[0]),
            end_us=int(arsp.TimeUS.iloc[-1]),
            native_rate=measured_native_rate,
            requested_rate=1.0 / self.sample_period,
            summary=summary,
            profile=profile,
            validation=validation,
        )

    # --------------------------------------------------------

    def _build_summary(
        self,
        arsp: pd.DataFrame,
    ) -> AirspeedSummary:

        return AirspeedSummary(
            start_speed=float(
                arsp.Airspeed.iloc[0]
            ),
            end_speed=float(
                arsp.Airspeed.iloc[-1]
            ),
            minimum_speed=float(
                arsp.Airspeed.min()
            ),
            maximum_speed=float(
                arsp.Airspeed.max()
            ),
            mean_speed=float(
                arsp.Airspeed.mean()
            ),
        )

    # --------------------------------------------------------

    def _build_profile(
        self,
        arsp: pd.DataFrame,
    ) -> pd.DataFrame:

        bucket_us = int(
            self.sample_period * 1_000_000
        )

        profile = (
            arsp
            .assign(
                Bucket=lambda df: (
                    (
                        df.TimeUS
                        - df.TimeUS.iloc[0]
                    )
                    // bucket_us
                )
            )
            .groupby(
                "Bucket",
                as_index=False,
            )
            .agg(
                TimeUS=(
                    "TimeUS",
                    "first",
                ),
                Airspeed=(
                    "Airspeed",
                    "mean",
                ),
            )
        )

        return profile

    # --------------------------------------------------------

    def _validate(
        self,
        arsp: pd.DataFrame,
    ) -> AirspeedValidationReport:

        report = AirspeedValidationReport()

        validators = (
            self._validate_missing_samples,
            self._validate_missing_values,
            self._validate_timestamp_order,
            self._validate_sample_gap,
            self._validate_negative_values,
            self._validate_step_change,
            self._validate_low_speed,
        )

        report.rules_evaluated = len(
            validators
        )

        for validator in validators:

            failures = validator(arsp)

            if failures:

                for failure in failures:
                    report.add(failure)

        return report

    # ========================================================
    # Validation Rules
    # ========================================================

    def _validate_missing_samples(
        self,
        arsp: pd.DataFrame,
    ):

        cfg = self.config[
            "validation"
        ]["missing_samples"]

        if not cfg["enabled"]:
            return []

        return []

    # --------------------------------------------------------

    def _validate_missing_values(
        self,
        arsp: pd.DataFrame,
    ):

        cfg = self.config[
            "validation"
        ]["missing_values"]

        if not cfg["enabled"]:
            return []

        failures = []

        invalid = arsp[
            arsp.Airspeed.isna()
        ]

        if invalid.empty:
            return failures

        failures.append(
            AirspeedValidationFailure(
                rule="missing_values",
                description=(
                    "Missing airspeed samples detected."
                ),
                criteria={
                    "field": "Airspeed",
                    "must_not_be_null": True,
                },
                evidence={
                    "count": len(invalid),
                },
                recommendation=(
                    "Inspect log integrity or "
                    "airspeed sensor."
                ),
                start_us=int(
                    invalid.TimeUS.iloc[0]
                ),
                end_us=int(
                    invalid.TimeUS.iloc[-1]
                ),
            )
        )

        return failures

    # --------------------------------------------------------

    def _validate_timestamp_order(
        self,
        arsp: pd.DataFrame,
    ):

        cfg = self.config[
            "validation"
        ]["timestamp_order"]

        if not cfg["enabled"]:
            return []

        failures = []

        delta = arsp.TimeUS.diff()

        invalid = arsp[
            delta <= 0
        ]

        if invalid.empty:
            return failures

        evidence = []

        for index in invalid.index:

            evidence.append(
                {
                    "row": int(index),
                    "timestamp": int(
                        arsp.loc[
                            index,
                            "TimeUS",
                        ]
                    ),
                }
            )

        failures.append(
            AirspeedValidationFailure(
                rule="timestamp_order",
                description=(
                    "Airspeed timestamps are "
                    "not strictly increasing."
                ),
                criteria={
                    "timestamp_difference_us": "> 0",
                },
                evidence={
                    "count": len(invalid),
                    "samples": evidence,
                },
                recommendation=(
                    "Inspect the flight log for "
                    "corrupted or duplicated "
                    "ARSP records."
                ),
                start_us=int(
                    invalid.TimeUS.iloc[0]
                ),
                end_us=int(
                    invalid.TimeUS.iloc[-1]
                ),
            )
        )

        return failures

    # --------------------------------------------------------

    def _validate_sample_gap(
        self,
        arsp: pd.DataFrame,
    ):

        cfg = self.config[
            "validation"
        ]["sample_gap"]

        if not cfg["enabled"]:
            return []

        failures = []

        maximum_gap_us = (
            cfg["maximum_ms"] * 1000
        )

        delta = arsp.TimeUS.diff()

        gaps = arsp[
            delta > maximum_gap_us
        ]

        for index in gaps.index:

            previous = arsp.loc[
                index - 1
            ]

            current = arsp.loc[
                index
            ]

            failures.append(
                AirspeedValidationFailure(
                    rule="sample_gap",
                    description=(
                        "Gap detected between "
                        "consecutive airspeed samples."
                    ),
                    criteria={
                        "maximum_gap_ms":
                            cfg["maximum_ms"],
                    },
                    evidence={
                        "gap_ms": float(
                            delta.loc[index]
                            / 1000.0
                        ),
                        "previous_timestamp":
                            int(previous.TimeUS),
                        "current_timestamp":
                            int(current.TimeUS),
                    },
                    recommendation=(
                        "Inspect telemetry logging "
                        "or airspeed sensor "
                        "communication."
                    ),
                    start_us=int(
                        previous.TimeUS
                    ),
                    end_us=int(
                        current.TimeUS
                    ),
                )
            )

        return failures

    # --------------------------------------------------------

    def _validate_negative_values(
        self,
        arsp: pd.DataFrame,
    ):

        cfg = self.config[
            "validation"
        ]["negative_values"]

        if not cfg["enabled"]:
            return []

        failures = []

        invalid = arsp[
            arsp.Airspeed < 0
        ]

        for _, row in invalid.iterrows():

            failures.append(
                AirspeedValidationFailure(
                    rule="negative_values",
                    description=(
                        "Negative airspeed detected."
                    ),
                    criteria={
                        "minimum_airspeed": 0.0,
                    },
                    evidence={
                        "airspeed": float(
                            row.Airspeed
                        ),
                    },
                    recommendation=(
                        "Inspect pitot tube, "
                        "differential pressure sensor "
                        "or calibration."
                    ),
                    start_us=int(
                        row.TimeUS
                    ),
                    end_us=int(
                        row.TimeUS
                    ),
                )
            )

        return failures

    # --------------------------------------------------------

    def _validate_step_change(
        self,
        arsp: pd.DataFrame,
    ):

        cfg = self.config[
            "validation"
        ]["step_change"]

        if not cfg["enabled"]:
            return []

        failures = []

        threshold = cfg["threshold"]
        interval_ms = cfg["interval_ms"]

        events = []

        for index in range(
            len(arsp) - 1
        ):

            start_time = (
                arsp.TimeUS.iloc[index]
            )

            target_time = (
                start_time
                + interval_ms * 1000
            )

            end = arsp.TimeUS.searchsorted(
                target_time
            )

            if end >= len(arsp):
                break

            change = abs(
                arsp.Airspeed.iloc[end]
                - arsp.Airspeed.iloc[index]
            )

            if change > threshold:
                events.append(
                    (
                        index,
                        end,
                        change,
                    )
                )

        for start, end, change in events:

            before = arsp.iloc[start]
            after = arsp.iloc[end]

            failures.append(
                AirspeedValidationFailure(
                    rule="step_change",
                    description=(
                        "Large airspeed step "
                        "change detected."
                    ),
                    criteria={
                        "maximum_change":
                            threshold,
                    },
                    evidence={
                        "before": float(
                            before.Airspeed
                        ),
                        "after": float(
                            after.Airspeed
                        ),
                        "change": float(
                            change
                        ),
                    },
                    recommendation=(
                        "Inspect pitot tubing and "
                        "pressure sensor for spikes."
                    ),
                    start_us=int(
                        before.TimeUS
                    ),
                    end_us=int(
                        after.TimeUS
                    ),
                )
            )

        return failures

    # --------------------------------------------------------

    def _validate_low_speed(
        self,
        arsp: pd.DataFrame,
    ):

        cfg = self.config[
            "validation"
        ]["low_speed"]

        if not cfg["enabled"]:
            return []

        failures = []

        maximum_duration = (
            cfg["maximum_duration"]
            * 1_000_000
        )

        low = (
            arsp.Airspeed
            < cfg["threshold"]
        )

        if not low.any():
            return failures

        start = None

        for index, state in enumerate(low):

            if state and start is None:

                start = index

            elif (
                not state
                and start is not None
            ):

                end = index - 1

                duration = (
                    arsp.TimeUS.iloc[end]
                    - arsp.TimeUS.iloc[start]
                )

                if duration > maximum_duration:

                    section = arsp.iloc[
                        start:end + 1
                    ]

                    failures.append(
                        AirspeedValidationFailure(
                            rule="low_speed",
                            description=(
                                "Airspeed remained "
                                "at low for an "
                                "extended period."
                            ),
                            criteria={
                                "maximum_duration_seconds":
                                    cfg[
                                        "maximum_duration"
                                    ],
                            },
                            evidence={
                                "duration_seconds":
                                    float(
                                        duration
                                        / 1_000_000
                                    ),
                                "samples":
                                    len(section),
                            },
                            recommendation=(
                                "Confirm this period "
                                "is expected "
                                "(e.g. post-landing). "
                                "Otherwise inspect "
                                "the pitot system."
                            ),
                            start_us=int(
                                section.TimeUS.iloc[0]
                            ),
                            end_us=int(
                                section.TimeUS.iloc[-1]
                            ),
                        )
                    )

                start = None

        #
        # Handle run continuing to end of window.
        #
        if start is not None:

            end = len(arsp) - 1

            duration = (
                arsp.TimeUS.iloc[end]
                - arsp.TimeUS.iloc[start]
            )

            if duration > maximum_duration:

                section = arsp.iloc[
                    start:end + 1
                ]

                failures.append(
                    AirspeedValidationFailure(
                        rule="low_speed",
                        description=(
                            "Airspeed remained low "
                            "for an extended period."
                        ),
                        criteria={
                            "maximum_duration_seconds":
                                cfg[
                                    "maximum_duration"
                                ],
                        },
                        evidence={
                            "duration_seconds":
                                float(
                                    duration
                                    / 1_000_000
                                ),
                            "samples":
                                len(section),
                        },
                        recommendation=(
                            "Confirm this period is "
                            "expected "
                            "(e.g. post-landing). "
                            "Otherwise inspect the "
                            "pitot system."
                        ),
                        start_us=int(
                            section.TimeUS.iloc[0]
                        ),
                        end_us=int(
                            section.TimeUS.iloc[-1]
                        ),
                    )
                )

        return failures
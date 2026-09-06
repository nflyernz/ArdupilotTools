"""Assertion-based tests for event-time flight-window parameters."""

import math

import pandas as pd

from core.config import Config
from core.flight_data import FlightLog
from core.flight_window import FlightWindow
from core.flight_window_detector import FlightWindowDetector
from core.log_reader import FlightReader
from core.params import ParameterChange, ParameterHistory


CONFIG = Config("Config/landing.yaml")

EXPECTED_REAL_LOG_WINDOWS = {
    "log_11.bin": (
        (1_052_151_775, 1_711_544_862),
    ),
    "log_17.bin": (
        (656_723_277, 924_883_724),
        (1_095_783_170, 1_680_743_260),
        (1_966_307_340, 2_051_367_266),
        (2_573_683_601, 2_863_678_803),
    ),
    "log_19.bin": (
        (543_383_960, 763_918_413),
    ),
    "log_26.bin": (
        (718_296_867, 1_061_696_792),
        (1_265_796_876, 1_496_337_183),
        (1_665_016_996, 2_435_437_142),
        (2_543_496_838, 2_793_037_498),
    ),
}


def detect_windows(
    samples,
    history=None,
    companion_parameters=None,
    speed_threshold=FlightWindowDetector.DEFAULT_THRESHOLD,
):
    """Detect public flight windows from compact GPS evidence."""
    flight_log = FlightLog(
        messages={
            "GPS": pd.DataFrame(
                [
                    {
                        "TimeUS": time_us,
                        "Spd": speed,
                    }
                    for time_us, speed in samples
                ]
            )
        },
        parameters=companion_parameters or {},
        parameter_history=(
            history
            if history is not None
            else ParameterHistory()
        ),
    )

    return FlightWindowDetector(
        speed_threshold=speed_threshold,
    ).detect(flight_log)


def test_startup_value_raises_effective_threshold():
    history = ParameterHistory({"AIRSPEED_STALL": 20.0})

    windows = detect_windows(
        (
            (0, 6.0),
            (2_000_000, 6.0),
            (3_000_000, 11.0),
            (5_000_000, 11.0),
        ),
        history,
    )

    assert windows == [FlightWindow(3_000_000, 5_000_000)]


def test_missing_history_uses_configured_floor():
    windows = detect_windows(
        (
            (0, 8.0),
            (2_000_000, 8.0),
        ),
        speed_threshold=7.0,
    )

    assert windows == [FlightWindow(0, 2_000_000)]


def test_late_first_occurrence_is_prospective():
    history = ParameterHistory(
        changes={
            "AIRSPEED_STALL": (
                ParameterChange(1_000_000, 20.0),
            )
        }
    )

    windows = detect_windows(
        (
            (0, 6.0),
            (1_000_000, 6.0),
            (2_000_000, 11.0),
            (4_000_000, 11.0),
        ),
        history,
    )

    assert windows == [FlightWindow(2_000_000, 4_000_000)]


def test_change_between_flights_affects_only_second_candidate():
    history = ParameterHistory(
        {"AIRSPEED_STALL": 10.0},
        {
            "AIRSPEED_STALL": (
                ParameterChange(40_000_000, 20.0),
            )
        },
    )

    windows = detect_windows(
        (
            (0, 6.0),
            (2_000_000, 6.0),
            (3_000_000, 0.0),
            (33_000_000, 0.0),
            (41_000_000, 9.0),
            (42_000_000, 11.0),
            (44_000_000, 11.0),
        ),
        history,
    )

    assert windows == [
        FlightWindow(0, 2_000_000),
        FlightWindow(42_000_000, 44_000_000),
    ]


def test_change_during_start_persistence_breaks_candidate():
    history = ParameterHistory(
        {"AIRSPEED_STALL": 10.0},
        {
            "AIRSPEED_STALL": (
                ParameterChange(1_000_000, 20.0),
            )
        },
    )

    windows = detect_windows(
        (
            (0, 6.0),
            (1_000_000, 6.0),
            (2_000_000, 6.0),
        ),
        history,
    )

    assert windows == []


def test_change_during_flight_preserves_start_and_ground_duration():
    history = ParameterHistory(
        {"AIRSPEED_STALL": 10.0},
        {
            "AIRSPEED_STALL": (
                ParameterChange(10_000_000, 20.0),
            )
        },
    )
    before_ground_timeout = (
        (0, 6.0),
        (2_000_000, 6.0),
        (10_000_000, 6.0),
        (39_000_000, 6.0),
    )

    assert detect_windows(
        before_ground_timeout,
        history,
    ) == [FlightWindow(0, 39_000_000)]
    assert detect_windows(
        before_ground_timeout + ((40_000_000, 6.0),),
        history,
    ) == [FlightWindow(0, 2_000_000)]


def test_change_during_ground_persistence_can_cancel_candidate():
    history = ParameterHistory(
        {"AIRSPEED_STALL": 10.0},
        {
            "AIRSPEED_STALL": (
                ParameterChange(10_000_000, 20.0),
                ParameterChange(25_000_000, 10.0),
            )
        },
    )

    windows = detect_windows(
        (
            (0, 6.0),
            (2_000_000, 6.0),
            (10_000_000, 6.0),
            (25_000_000, 6.0),
            (50_000_000, 6.0),
        ),
        history,
    )

    assert windows == [FlightWindow(0, 50_000_000)]


def test_change_is_effective_at_exact_gps_timestamp():
    history = ParameterHistory(
        {"AIRSPEED_STALL": 10.0},
        {
            "AIRSPEED_STALL": (
                ParameterChange(1_000_000, 20.0),
            )
        },
    )

    windows = detect_windows(
        (
            (1_000_000, 10.0),
            (2_000_000, 11.0),
            (4_000_000, 11.0),
        ),
        history,
    )

    assert windows == [FlightWindow(2_000_000, 4_000_000)]


def test_nonfinite_values_use_configured_floor():
    for stall_speed in (math.nan, math.inf, -math.inf):
        history = ParameterHistory({"AIRSPEED_STALL": stall_speed})

        assert detect_windows(
            (
                (0, 6.0),
                (2_000_000, 6.0),
            ),
            history,
        ) == [FlightWindow(0, 2_000_000)]


def test_nonpositive_values_use_configured_floor():
    for stall_speed in (0.0, -1.0):
        history = ParameterHistory({"AIRSPEED_STALL": stall_speed})

        assert detect_windows(
            (
                (0, 6.0),
                (2_000_000, 6.0),
            ),
            history,
        ) == [FlightWindow(0, 2_000_000)]


def test_below_floor_stall_value_keeps_floor():
    history = ParameterHistory({"AIRSPEED_STALL": 8.0})

    assert detect_windows(
        (
            (0, 6.0),
            (2_000_000, 6.0),
        ),
        history,
    ) == [FlightWindow(0, 2_000_000)]


def test_above_floor_stall_value_raises_threshold():
    history = ParameterHistory({"AIRSPEED_STALL": 20.0})

    assert detect_windows(
        (
            (0, 6.0),
            (2_000_000, 6.0),
        ),
        history,
    ) == []


def test_nondefault_stall_value_is_used():
    history = ParameterHistory({"AIRSPEED_STALL": 16.0})

    windows = detect_windows(
        (
            (0, 7.0),
            (2_000_000, 7.0),
            (3_000_000, 9.0),
            (5_000_000, 9.0),
        ),
        history,
    )

    assert windows == [FlightWindow(3_000_000, 5_000_000)]


def test_speed_equal_to_effective_threshold_is_not_airborne():
    history = ParameterHistory({"AIRSPEED_STALL": 20.0})

    assert detect_windows(
        (
            (0, 10.0),
            (2_000_000, 10.0),
        ),
        history,
    ) == []


def test_companion_value_is_not_a_fallback():
    windows = detect_windows(
        (
            (0, 6.0),
            (2_000_000, 6.0),
        ),
        companion_parameters={
            "AIRSPEED_STALL": 20.0,
        },
    )

    assert windows == [FlightWindow(0, 2_000_000)]


def test_real_log_flight_window_boundaries():
    for log_name, expected in EXPECTED_REAL_LOG_WINDOWS.items():
        flight_log = FlightReader(
            f"Logs/{log_name}",
            config=CONFIG,
        ).read()
        actual = tuple(
            (window.start_us, window.end_us)
            for window in flight_log.flights
        )

        assert actual == expected, log_name


test_startup_value_raises_effective_threshold()
test_missing_history_uses_configured_floor()
test_late_first_occurrence_is_prospective()
test_change_between_flights_affects_only_second_candidate()
test_change_during_start_persistence_breaks_candidate()
test_change_during_flight_preserves_start_and_ground_duration()
test_change_during_ground_persistence_can_cancel_candidate()
test_change_is_effective_at_exact_gps_timestamp()
test_nonfinite_values_use_configured_floor()
test_nonpositive_values_use_configured_floor()
test_below_floor_stall_value_keeps_floor()
test_above_floor_stall_value_raises_threshold()
test_nondefault_stall_value_is_used()
test_speed_equal_to_effective_threshold_is_not_airborne()
test_companion_value_is_not_a_fallback()
test_real_log_flight_window_boundaries()

print("Event-time FlightWindowDetector tests: PASS")

"""Focused tests for landing-attempt GPS-stop causality."""

import pandas as pd
from core.flight_data import FlightLog
from core.flight_window import FlightWindow
from core.landing_window_detector import LandingWindowDetector

AUTO_MODE = 10
MANUAL_MODE = 0


def detect_windows(
    gps_samples,
    message_samples=(),
    mode_samples=(),
    land_samples=((1_000_000, 1),),
    end_us=8_000_000,
):
    """Build compact synthetic evidence and detect landing windows."""
    flight_window = FlightWindow(0, end_us)
    flight_log = FlightLog(
        messages={
            "GPS": pd.DataFrame(
                gps_samples,
                columns=("TimeUS", "Spd"),
            ),
            "LAND": pd.DataFrame(
                land_samples,
                columns=("TimeUS", "stage"),
            ),
            "MODE": pd.DataFrame(
                ((0, AUTO_MODE), *mode_samples),
                columns=("TimeUS", "ModeNum"),
            ),
            "MSG": pd.DataFrame(
                message_samples,
                columns=("TimeUS", "Message"),
            ),
        },
        flights=[flight_window],
    )

    return LandingWindowDetector().detect(
        flight_log,
        flight_window,
    )


def test_post_disarm_gps_cannot_confirm_prior_run():
    """A sample after disarm cannot retroactively qualify GPS stop."""
    windows = detect_windows(
        gps_samples=(
            (2_000_000, 2.0),
            (3_000_000, 2.0),
            (5_000_000, 2.0),
        ),
        message_samples=((4_000_000, "Throttle disarmed"),),
    )

    assert len(windows) == 1
    assert windows[0].end_us == 4_000_000
    assert windows[0].end_reason == "disarm"


def test_in_attempt_gps_confirmation_remains_backdated():
    """A fully in-attempt run still ends at its first low sample."""
    windows = detect_windows(
        gps_samples=(
            (2_000_000, 2.0),
            (4_000_000, 2.0),
        ),
        message_samples=((5_000_000, "Throttle disarmed"),),
    )

    assert len(windows) == 1
    assert windows[0].end_us == 2_000_000
    assert windows[0].end_reason == "gps"


def test_post_mode_exit_gps_cannot_confirm_prior_run():
    """A sample after mode exit cannot retroactively qualify GPS stop."""
    windows = detect_windows(
        gps_samples=(
            (2_000_000, 2.0),
            (3_000_000, 2.0),
            (5_000_000, 2.0),
        ),
        mode_samples=((4_000_000, MANUAL_MODE),),
    )

    assert len(windows) == 1
    assert windows[0].end_us == 4_000_000
    assert windows[0].end_reason == "mode"


def test_stage_restart_transfers_gps_observation_ownership():
    """The restart timestamp and later GPS belong to the next attempt."""
    windows = detect_windows(
        gps_samples=(
            (2_000_000, 2.0),
            (4_000_000, 2.0),
            (4_500_000, 4.0),
            (5_000_000, 2.0),
            (7_000_000, 2.0),
        ),
        land_samples=(
            (1_000_000, 1),
            (3_000_000, 2),
            (4_000_000, 1),
        ),
    )

    assert len(windows) == 2
    assert windows[0].end_us == 4_000_000
    assert windows[0].end_reason == "stage_restart"
    assert windows[1].end_us == 5_000_000
    assert windows[1].end_reason == "gps"


test_post_disarm_gps_cannot_confirm_prior_run()
test_in_attempt_gps_confirmation_remains_backdated()
test_post_mode_exit_gps_cannot_confirm_prior_run()
test_stage_restart_transfers_gps_observation_ownership()

print("Landing-window GPS-stop causality tests: PASS")

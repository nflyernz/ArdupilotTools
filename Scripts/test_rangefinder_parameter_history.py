"""Assertion-based tests for event-time rangefinder parameters."""

import math

import pandas as pd

from core.config import Config
from core.events import EventType
from core.flight_data import FlightLog
from core.flight_window import FlightWindow
from core.landing_window import LandingWindow
from core.landing_window_detector import LandingWindowDetector
from core.log_reader import FlightReader
from core.params import ParameterChange, ParameterHistory
from core.rangefinder import RangefinderEvents


CONFIG = Config("Config/landing.yaml")


def build_events(samples, history=None, companion_parameters=None):
    """Build rangefinder events from compact synthetic evidence."""
    start_us = min(time_us for time_us, _ in samples)
    end_us = max(time_us for time_us, _ in samples)
    flight_window = FlightWindow(start_us, end_us)
    flight_log = FlightLog(
        messages={
            "RFND": pd.DataFrame(
                [
                    {
                        "TimeUS": time_us,
                        "Dist": distance,
                    }
                    for time_us, distance in samples
                ]
            )
        },
        parameters=companion_parameters or {},
        parameter_history=(
            history
            if history is not None
            else ParameterHistory()
        ),
        flights=[flight_window],
    )
    window = LandingWindow(
        start_us,
        end_us,
        "test",
    )

    return RangefinderEvents(
        flight_log,
        flight_window,
        window,
        CONFIG,
    ).build()


def events_of_type(events, event_type):
    """Return events of one type."""
    return [
        event
        for event in events
        if event.event == event_type
    ]


def event_signatures(events, excluded=()):
    """Return complete event values, optionally excluding event types."""
    return [
        (
            event.time_us,
            event.event,
            event.detail,
        )
        for event in events
        if event.event not in excluded
    ]


def assert_no_first_in_range(events):
    """Assert that no first-in-range evidence was published."""
    assert not events_of_type(
        events,
        EventType.RFND_FIRST_IN_RANGE,
    )


def test_startup_value_and_event_detail():
    history = ParameterHistory(
        {"RNGFND1_MAX": 10.0}
    )
    events = build_events(
        (
            (100, 12.0),
            (200, 10.0),
        ),
        history,
    )

    first_in_range = events_of_type(
        events,
        EventType.RFND_FIRST_IN_RANGE,
    )

    assert len(first_in_range) == 1
    assert first_in_range[0].time_us == 200
    assert first_in_range[0].detail == "10.00 / 10.00 m"


def test_decrease_uses_new_value_for_later_samples():
    history = ParameterHistory(
        {"RNGFND1_MAX": 10.0},
        {
            "RNGFND1_MAX": (
                ParameterChange(200, 6.0),
            )
        },
    )
    events = build_events(
        (
            (100, 11.0),
            (200, 8.0),
            (300, 6.0),
        ),
        history,
    )

    first_in_range = events_of_type(
        events,
        EventType.RFND_FIRST_IN_RANGE,
    )

    assert len(first_in_range) == 1
    assert first_in_range[0].time_us == 300
    assert first_in_range[0].detail == "6.00 / 6.00 m"


def test_increase_does_not_apply_retroactively():
    history = ParameterHistory(
        {"RNGFND1_MAX": 6.0},
        {
            "RNGFND1_MAX": (
                ParameterChange(150, 10.0),
            )
        },
    )
    events = build_events(
        (
            (100, 8.0),
            (200, 9.0),
        ),
        history,
    )

    first_in_range = events_of_type(
        events,
        EventType.RFND_FIRST_IN_RANGE,
    )

    assert len(first_in_range) == 1
    assert first_in_range[0].time_us == 200
    assert first_in_range[0].detail == "9.00 / 10.00 m"


def test_change_is_effective_at_same_timestamp():
    history = ParameterHistory(
        {"RNGFND1_MAX": 10.0},
        {
            "RNGFND1_MAX": (
                ParameterChange(200, 6.0),
            )
        },
    )
    events = build_events(
        (
            (200, 8.0),
            (300, 5.0),
        ),
        history,
    )

    first_in_range = events_of_type(
        events,
        EventType.RFND_FIRST_IN_RANGE,
    )

    assert len(first_in_range) == 1
    assert first_in_range[0].time_us == 300
    assert first_in_range[0].detail == "5.00 / 6.00 m"


def test_late_first_occurrence_does_not_apply_retroactively():
    history = ParameterHistory(
        {},
        {
            "RNGFND1_MAX": (
                ParameterChange(200, 6.0),
            )
        },
    )
    events = build_events(
        (
            (100, 5.0),
            (200, 5.0),
        ),
        history,
    )

    first_in_range = events_of_type(
        events,
        EventType.RFND_FIRST_IN_RANGE,
    )

    assert len(first_in_range) == 1
    assert first_in_range[0].time_us == 200


def test_missing_value_keeps_other_lifecycle_evidence():
    events = build_events(
        (
            (1_000_000, 5.0),
            (2_000_000, 0.0),
        )
    )

    assert_no_first_in_range(events)
    assert len(events_of_type(
        events,
        EventType.RFND_FIRST_NONZERO,
    )) == 1
    assert len(events_of_type(
        events,
        EventType.RFND_CONTINUOUS,
    )) == 1
    assert len(events_of_type(
        events,
        EventType.RFND_DISENGAGED,
    )) == 1


def test_nonfinite_values_are_unavailable():
    for value in (math.nan, math.inf, -math.inf):
        events = build_events(
            ((100, 5.0),),
            ParameterHistory(
                {"RNGFND1_MAX": value}
            ),
        )

        assert_no_first_in_range(events)


def test_nonpositive_values_are_unavailable():
    for value in (0.0, -1.0):
        events = build_events(
            ((100, 5.0),),
            ParameterHistory(
                {"RNGFND1_MAX": value}
            ),
        )

        assert_no_first_in_range(events)


def test_companion_value_is_not_a_fallback():
    events = build_events(
        ((100, 5.0),),
        companion_parameters={
            "RNGFND1_MAX": 10.0,
        },
    )

    assert_no_first_in_range(events)


def test_other_lifecycle_events_ignore_maximum_range():
    samples = (
        (1_000_000, 4.0),
        (2_000_000, 7.0),
        (3_000_000, 0.0),
        (4_000_000, 4.0),
    )
    usable = build_events(
        samples,
        ParameterHistory(
            {"RNGFND1_MAX": 10.0}
        ),
    )
    unavailable = build_events(
        samples,
        ParameterHistory(),
    )
    changing = build_events(
        samples,
        ParameterHistory(
            {"RNGFND1_MAX": 10.0},
            {
                "RNGFND1_MAX": (
                    ParameterChange(2_000_000, 6.0),
                )
            },
        ),
    )
    excluded = (EventType.RFND_FIRST_IN_RANGE,)

    assert event_signatures(usable, excluded) == (
        event_signatures(unavailable, excluded)
    )
    assert event_signatures(usable, excluded) == (
        event_signatures(changing, excluded)
    )
    first_in_range = events_of_type(
        changing,
        EventType.RFND_FIRST_IN_RANGE,
    )
    assert len(first_in_range) == 1
    assert first_in_range[0].time_us == 1_000_000


def test_log_11_uses_embedded_event_time_value():
    flight_log = FlightReader(
        "Logs/log_11.bin",
        config=CONFIG,
    ).read()
    flight_window = flight_log.flights[0]
    landing_windows = LandingWindowDetector(
        CONFIG
    ).detect(
        flight_log,
        flight_window,
    )
    expected = (
        (1_399_291_553, "5.21 / 10.00 m"),
        (1_523_091_499, "5.61 / 10.00 m"),
    )

    assert flight_log.param("RNGFND1_MAX") == 9.0
    assert len(landing_windows) == len(expected)

    for landing_window, expected_event in zip(
        landing_windows,
        expected,
        strict=True,
    ):
        events = RangefinderEvents(
            flight_log,
            flight_window,
            landing_window,
            CONFIG,
        ).build()
        first_in_range = events_of_type(
            events,
            EventType.RFND_FIRST_IN_RANGE,
        )

        assert len(first_in_range) == 1
        assert (
            first_in_range[0].time_us,
            first_in_range[0].detail,
        ) == expected_event
        assert flight_log.parameter_history.value_at(
            "RNGFND1_MAX",
            first_in_range[0].time_us,
        ) == 10.0


test_startup_value_and_event_detail()
test_decrease_uses_new_value_for_later_samples()
test_increase_does_not_apply_retroactively()
test_change_is_effective_at_same_timestamp()
test_late_first_occurrence_does_not_apply_retroactively()
test_missing_value_keeps_other_lifecycle_evidence()
test_nonfinite_values_are_unavailable()
test_nonpositive_values_are_unavailable()
test_companion_value_is_not_a_fallback()
test_other_lifecycle_events_ignore_maximum_range()
test_log_11_uses_embedded_event_time_value()

print("Event-time rangefinder parameter tests: PASS")

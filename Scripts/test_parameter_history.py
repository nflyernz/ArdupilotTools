"""Assertion-based tests for timestamped BIN parameter history."""

import math
from pathlib import Path

from core.config import Config
from core.log_reader import FlightReader
from core.params import (
    ParameterChange,
    ParameterHistory,
    ParameterReader,
)


def history_from(*records):
    """Build a history from compact synthetic PARM records."""
    return ParameterHistory.from_records(records)


def assert_raises(exception_type, message, callback):
    """Assert that callback raises the expected exception and message."""
    try:
        callback()
    except exception_type as error:
        if message not in str(error):
            raise AssertionError(
                f"expected {message!r} in {str(error)!r}"
            ) from error
    else:
        raise AssertionError(
            f"expected {exception_type.__name__}"
        )


def test_baseline_and_stepwise_lookup():
    history = history_from(
        {"Name": "TEST", "Value": 1.0, "TimeUS": 1_000_000},
        {"Name": "BASE", "Value": 4.0, "TimeUS": 1_050_000},
        {"Name": "TEST", "Value": 2.0, "TimeUS": 1_160_001},
        {"Name": "TEST", "Value": 3.0, "TimeUS": 2_000_000},
    )

    assert history.initial_values == {"TEST": 1.0, "BASE": 4.0}
    assert history.value_at("TEST", 0) == 1.0
    assert history.value_at("TEST", 1_160_000) == 1.0
    assert history.value_at("TEST", 1_160_001) == 2.0
    assert history.value_at("TEST", 1_500_000) == 2.0
    assert history.value_at("TEST", 2_000_000) == 3.0
    assert history.value_at("TEST", 5_000_000) == 3.0
    assert history.value_at("MISSING", 1_000_000) is None
    assert history.changes["TEST"][0].time_us == 1_160_001
    assert history.latest_values == {
        "TEST": 3.0,
        "BASE": 4.0,
    }


def test_late_first_occurrence_has_no_baseline():
    history = history_from(
        {"Name": "BASE", "Value": 1.0, "TimeUS": 0},
        {"Name": "LATE", "Value": 2.0, "TimeUS": 110_001},
    )

    assert history.value_at("LATE", 110_000) is None
    assert history.value_at("LATE", 110_001) == 2.0
    assert history.latest_values == {"BASE": 1.0, "LATE": 2.0}


def test_startup_duplicate_replaces_baseline():
    history = history_from(
        {"Name": "TEST", "Value": 1.0, "TimeUS": 0},
        {"Name": "TEST", "Value": 2.0, "TimeUS": 50_000},
    )

    assert history.initial_values == {"TEST": 2.0}
    assert history.changes == {}


def test_startup_gap_boundary_is_strict():
    history = history_from(
        {"Name": "TEST", "Value": 1.0, "TimeUS": 0},
        {"Name": "TEST", "Value": 2.0, "TimeUS": 110_000},
        {"Name": "TEST", "Value": 3.0, "TimeUS": 220_001},
    )

    assert history.initial_values == {"TEST": 2.0}
    assert history.changes == {
        "TEST": (ParameterChange(220_001, 3.0),)
    }


def test_duplicate_timestamps_and_repeated_values():
    history = history_from(
        {"Name": "TEST", "Value": 1.0, "TimeUS": 0},
        {"Name": "TEST", "Value": 2.0, "TimeUS": 110_001},
        {"Name": "TEST", "Value": 3.0, "TimeUS": 110_001},
        {"Name": "TEST", "Value": 3.0, "TimeUS": 120_000},
    )

    assert history.changes == {
        "TEST": (
            ParameterChange(110_001, 2.0),
            ParameterChange(110_001, 3.0),
        )
    }
    assert history.value_at("TEST", 110_001) == 3.0


def test_direct_construction_stably_sorts_changes():
    history = ParameterHistory(
        {"TEST": 1.0},
        {
            "TEST": (
                ParameterChange(10_000_000, 4.0),
                ParameterChange(5_000_000, 2.0),
                ParameterChange(5_000_000, 3.0),
            )
        },
    )

    assert history.changes["TEST"] == (
        ParameterChange(5_000_000, 2.0),
        ParameterChange(5_000_000, 3.0),
        ParameterChange(10_000_000, 4.0),
    )
    assert history.value_at("TEST", 5_000_000) == 3.0


def test_incomplete_and_malformed_name_value_records():
    history = history_from(
        {"Name": "VALID", "Value": 1.0, "TimeUS": 0},
        {"Name": "VALID", "TimeUS": 1},
        {"Name": "", "Value": 2.0, "TimeUS": 2},
        {"Name": 4, "Value": 2.0, "TimeUS": 3},
    )

    assert history.initial_values == {"VALID": 1.0}

    assert_raises(
        SystemExit,
        "Invalid parameter name format",
        lambda: history_from({"Name": "invalid", "Value": 1.0}),
    )
    assert_raises(
        SystemExit,
        "Error converting not-a-number to float",
        lambda: history_from(
            {"Name": "VALID", "Value": "not-a-number"}
        ),
    )


def test_missing_timestamp_matches_amc_semantics():
    startup = history_from({"Name": "TEST", "Value": 1.0})
    assert startup.initial_values == {"TEST": 1.0}

    history = history_from(
        {"Name": "TEST", "Value": 1.0, "TimeUS": 0},
        {"Name": "OTHER", "Value": 1.0, "TimeUS": 110_001},
        {"Name": "TEST", "Value": 2.0},
        {"Name": "TEST", "Value": 2.0, "TimeUS": 120_000},
        {"Name": "TEST", "Value": 3.0, "TimeUS": 130_000},
    )

    assert history.changes["TEST"] == (
        ParameterChange(130_000, 3.0),
    )
    assert history.value_at("TEST", 125_000) == 1.0
    assert history.value_at("TEST", 130_000) == 3.0


def test_timestamp_validation():
    assert_raises(
        ValueError,
        "must be numeric",
        lambda: history_from(
            {"Name": "VALID", "Value": 1.0, "TimeUS": "bad"}
        ),
    )

    for timestamp in (math.nan, math.inf, -math.inf):
        assert_raises(
            ValueError,
            "must be finite",
            lambda timestamp=timestamp: history_from(
                {
                    "Name": "VALID",
                    "Value": 1.0,
                    "TimeUS": timestamp,
                }
            ),
        )

    assert_raises(
        ValueError,
        "must be non-decreasing",
        lambda: history_from(
            {"Name": "FIRST", "Value": 1.0, "TimeUS": 2},
            {"Name": "SECOND", "Value": 2.0, "TimeUS": 1},
        ),
    )

    equal = history_from(
        {"Name": "FIRST", "Value": 1.0, "TimeUS": 0},
        {"Name": "SECOND", "Value": 2.0, "TimeUS": 110_001},
        {"Name": "FIRST", "Value": 3.0, "TimeUS": 110_001},
    )
    assert equal.value_at("FIRST", 110_001) == 3.0


def test_nonfinite_values_and_query_times_match_amc():
    history = history_from(
        {"Name": "NAN_VALUE", "Value": math.nan, "TimeUS": 0},
        {"Name": "POS_INF", "Value": math.inf, "TimeUS": 1},
        {"Name": "NEG_INF", "Value": -math.inf, "TimeUS": 2},
    )
    assert math.isnan(history.value_at("NAN_VALUE", 0))
    assert history.value_at("POS_INF", 1) == math.inf
    assert history.value_at("NEG_INF", 2) == -math.inf

    for time_us in (math.nan, math.inf, -math.inf):
        assert_raises(
            ValueError,
            "Parameter query time_us must be finite",
            lambda time_us=time_us: history.value_at("MISSING", time_us),
        )


def test_real_log_retention_and_companion_parameters():
    config = Config("Config/landing.yaml")
    expected_parameters = ParameterReader(
        Path("Params/log_17.params"),
        config,
    ).read()

    assert "PARM" not in set(config.get("messages"))

    flight_log = FlightReader(
        "Logs/log_17.bin",
        config=config,
    ).read()
    parm = flight_log.get("PARM")

    assert not parm.empty
    assert len(parm) == 1614
    assert int(parm.iloc[1]["TimeUS"] - parm.iloc[0]["TimeUS"]) == 121_201
    assert flight_log.parameter_history.initial_values == {
        "FORMAT_VERSION": 13.0
    }
    assert flight_log.parameter_history.value_at(
        "AUTOTUNE_LEVEL",
        339_624_649,
    ) is None
    assert flight_log.parameter_history.value_at(
        "AUTOTUNE_LEVEL",
        339_624_650,
    ) == 6.0

    assert flight_log.parameters == expected_parameters
    assert flight_log.param("RNGFND1_MAX") == expected_parameters.get(
        "RNGFND1_MAX"
    )
    assert flight_log.has_param("RNGFND1_MAX") == (
        "RNGFND1_MAX" in expected_parameters
    )


test_baseline_and_stepwise_lookup()
test_late_first_occurrence_has_no_baseline()
test_startup_duplicate_replaces_baseline()
test_startup_gap_boundary_is_strict()
test_duplicate_timestamps_and_repeated_values()
test_direct_construction_stably_sorts_changes()
test_incomplete_and_malformed_name_value_records()
test_missing_timestamp_matches_amc_semantics()
test_timestamp_validation()
test_nonfinite_values_and_query_times_match_amc()
test_real_log_retention_and_companion_parameters()

print("Timestamped parameter history: PASS")

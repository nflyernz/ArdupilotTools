"""Standalone regression checks for the v0.5 battery core layer."""

import math

import pandas as pd

from core.battery import BatteryProcessor
from core.flight_data import FlightLog
from core.flight_window import FlightWindow


WINDOW = FlightWindow(start_us=10_000_000, end_us=20_000_000)


def flight_with(messages):
    return FlightLog(messages=messages, flights=[WINDOW])


def processor(rows, instance=0):
    return BatteryProcessor(
        flight_with({"BAT": pd.DataFrame(rows)}),
        WINDOW,
        instance,
    )


def assert_close(actual, expected):
    assert actual is not None
    assert math.isclose(actual, expected, rel_tol=1e-9)


# Absent and empty BAT data are safely unavailable.
assert BatteryProcessor(flight_with({}), WINDOW, 0).analyse() is None
assert processor([]).analyse() is None

# Missing optional measurement/counter fields and NaNs stay unavailable.
incomplete = processor([
    {"TimeUS": 10_000_000, "Inst": 0, "Volt": float("nan"),
     "Curr": float("nan")},
]).analyse()
assert incomplete is not None
assert incomplete.start_voltage is None
assert incomplete.maximum_current is None
assert incomplete.consumed_mah is None
assert incomplete.load_event is None

rows = [
    # Pre-window sample is a counter baseline only.
    {"TimeUS": 9_000_000, "Inst": 0, "Volt": 16.0, "Curr": 1.0,
     "CurrTot": 100.0, "EnrgTot": 10.0},
    {"TimeUS": 10_000_000, "Inst": 0, "Volt": 15.8, "Curr": 2.0,
     "CurrTot": 102.0, "EnrgTot": 10.1},
    {"TimeUS": 12_000_000, "Inst": 0, "Volt": 15.0, "Curr": 10.0,
     "CurrTot": 110.0, "EnrgTot": 10.4},
    {"TimeUS": 17_000_000, "Inst": 0, "Volt": 15.5, "Curr": 4.0,
     "CurrTot": 120.0, "EnrgTot": 10.8},
    {"TimeUS": 20_000_000, "Inst": 0, "Volt": 15.4, "Curr": 3.0,
     "CurrTot": 125.0, "EnrgTot": 11.0},
    # Post-window data must not affect flight measurements or deltas.
    {"TimeUS": 21_000_000, "Inst": 0, "Volt": 1.0, "Curr": 500.0,
     "CurrTot": 900.0, "EnrgTot": 90.0},
    # A second monitor must not affect instance zero.
    {"TimeUS": 12_000_000, "Inst": 1, "Volt": 50.0, "Curr": 99.0,
     "CurrTot": 900.0, "EnrgTot": 90.0},
]

subject = processor(rows)
assert subject.available_instances() == [0, 1]
analysis = subject.analyse()
assert analysis is not None
assert analysis.instance == 0
assert analysis.start_us == WINDOW.start_us
assert analysis.end_us == WINDOW.end_us
assert_close(analysis.duration_s, 10.0)
assert_close(analysis.start_voltage, 15.8)
assert_close(analysis.final_voltage, 15.4)
assert_close(analysis.minimum_voltage, 15.0)
assert_close(analysis.maximum_current, 10.0)
assert_close(analysis.average_current, 4.75)
assert_close(analysis.maximum_power, 150.0)
assert_close(analysis.consumed_mah, 25.0)
assert_close(analysis.consumed_wh, 1.0)
assert_close(analysis.mah_per_minute, 150.0)

event = analysis.load_event
assert event is not None
assert event.time_us == 12_000_000
assert_close(event.current, 10.0)
assert_close(event.voltage_before, 15.8)
assert_close(event.minimum_voltage, 15.0)
assert_close(event.voltage_sag, 0.8)
assert_close(event.sag_per_ampere, 0.08)
assert_close(event.voltage_after_recovery, 15.5)
assert_close(event.voltage_recovery, 0.5)

# A real sample at or after the target is mandatory for recovery.
short = processor(rows[:3]).analyse()
assert short is not None and short.load_event is not None
assert short.load_event.voltage_after_recovery is None
assert short.load_event.voltage_recovery is None

# A counter reset inside the flight is explicitly unavailable.
reset_rows = [
    {"TimeUS": 9_000_000, "Inst": 0, "Volt": 16.0, "Curr": 1.0,
     "CurrTot": 100.0, "EnrgTot": 10.0},
    {"TimeUS": 10_000_000, "Inst": 0, "Volt": 15.8, "Curr": 2.0,
     "CurrTot": 110.0, "EnrgTot": 11.0},
    {"TimeUS": 15_000_000, "Inst": 0, "Volt": 15.5, "Curr": 3.0,
     "CurrTot": 5.0, "EnrgTot": 0.5},
]
reset = processor(reset_rows).analyse()
assert reset is not None
assert reset.consumed_mah is None
assert reset.consumed_wh is None
assert any("CurrTot is non-monotonic" in text for text in reset.counter_warnings)
assert any("EnrgTot is non-monotonic" in text for text in reset.counter_warnings)

# A zero-length FlightWindow has no valid duration or consumption rate.
zero_window = FlightWindow(start_us=10_000_000, end_us=10_000_000)
zero_flight = FlightLog(
    messages={"BAT": pd.DataFrame([
        {"TimeUS": 10_000_000, "Inst": 0, "Volt": 15.0, "Curr": 2.0,
         "CurrTot": 10.0, "EnrgTot": 1.0},
    ])},
    flights=[zero_window],
)
zero = BatteryProcessor(zero_flight, zero_window, 0).analyse()
assert zero is not None
assert zero.duration_s is None
assert zero.mah_per_minute is None

print("Battery core regression: PASS")

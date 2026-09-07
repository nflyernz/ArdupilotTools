"""Real-log regression checks for bounded Battery Load Events."""

import math

from core.battery import BatteryLoadEventType, BatteryProcessor
from core.config import Config
from core.log_reader import FlightReader

CONFIG = Config("Config/battery.yaml")

EXPECTED_FLIGHT_WINDOWS = {
    "log_0": [
        (736_623_934, 1_255_563_796),
        (1_557_743_834, 2_138_504_106),
        (2_356_423_935, 2_905_163_817),
    ],
    "log_11": [
        (1_052_151_775, 1_711_544_862),
    ],
    "log_17": [
        (656_723_277, 924_883_724),
        (1_095_783_170, 1_680_743_260),
        (1_966_307_340, 2_051_367_266),
        (2_573_683_601, 2_863_678_803),
    ],
    "log_19": [
        (543_383_960, 763_918_413),
    ],
    "log_26": [
        (718_296_867, 1_061_696_792),
        (1_265_796_876, 1_496_337_183),
        (1_665_016_996, 2_435_437_142),
        (2_543_496_838, 2_793_037_498),
    ],
}

EXPECTED_SUSTAINED_COUNTS = {
    "log_0": 0,
    "log_11": 1,
    "log_17": 2,
    "log_19": 0,
    "log_26": 3,
}

EXPECTED_AUTO_COUNTS = {
    "log_0": 3,
    "log_11": 1,
    "log_17": 4,
    "log_19": 1,
    "log_26": 4,
}

EXPECTED_LOG_0_TAKEOFFS = [
    {
        "start_us": 736_623_934,
        "end_us": 741_644_934,
        "duration_s": 5.021,
        "consumed_mah_at_start": 180.98727416992188,
        "pre_load_voltage": 16.185604095458984,
        "minimum_voltage": 14.321511268615723,
        "current_at_minimum_voltage": 19.19270896911621,
        "peak_current": 20.391357421875,
        "average_current": 18.40607567310333,
        "voltage_sag": 1.8640928268432617,
        "recovery_time_us": 746_684_830,
        "voltage_after_recovery": 14.795086860656738,
        "voltage_recovery": 0.4735755920410156,
        "low_voltage_margin": 1.121511459350586,
        "critical_voltage_margin": 1.5215110778808594,
    },
    {
        "start_us": 1_557_743_834,
        "end_us": 1_565_543_662,
        "duration_s": 7.799828,
        "consumed_mah_at_start": 933.067138671875,
        "pre_load_voltage": 15.999691009521484,
        "minimum_voltage": 14.239733695983887,
        "current_at_minimum_voltage": 18.8485107421875,
        "peak_current": 20.697507858276367,
        "average_current": 18.54113606000558,
        "voltage_sag": 1.7599573135375977,
        "recovery_time_us": 1_570_583_850,
        "voltage_after_recovery": 15.235671043395996,
        "voltage_recovery": 0.9959373474121094,
        "low_voltage_margin": 1.03973388671875,
        "critical_voltage_margin": 1.4397335052490234,
    },
    {
        "start_us": 2_356_423_935,
        "end_us": 2_363_963_489,
        "duration_s": 7.539554,
        "consumed_mah_at_start": 1753.75634765625,
        "pre_load_voltage": 15.328081130981445,
        "minimum_voltage": 13.771028518676758,
        "current_at_minimum_voltage": 18.06925392150879,
        "peak_current": 19.61344337463379,
        "average_current": 17.606689809163413,
        "voltage_sag": 1.5570526123046875,
        "recovery_time_us": 2_368_984_429,
        "voltage_after_recovery": 14.38729190826416,
        "voltage_recovery": 0.6162633895874023,
        "low_voltage_margin": 0.5710287094116211,
        "critical_voltage_margin": 0.9710283279418945,
    },
]


def events_of_type(analyses, event_type):
    return [
        event
        for analysis in analyses
        for event in analysis.bounded_load_events
        if event.event_type == event_type
    ]


def analyse_log(log_name):
    flight_log = FlightReader(
        f"Logs/{log_name}.bin",
        config=CONFIG,
    ).read()
    assert [
        (window.start_us, window.end_us) for window in flight_log.flights
    ] == EXPECTED_FLIGHT_WINDOWS[log_name]

    analyses = []
    for window in flight_log.flights:
        analysis = BatteryProcessor(
            flight_log,
            window,
            0,
            config=CONFIG,
        ).analyse()
        assert analysis is not None
        analyses.append(analysis)

    return flight_log, analyses


def test_real_log_event_counts_and_configuration():
    results = {}
    for log_name, expected_count in EXPECTED_SUSTAINED_COUNTS.items():
        results[log_name] = analyse_log(log_name)
        _, analyses = results[log_name]
        sustained = events_of_type(
            analyses,
            BatteryLoadEventType.SUSTAINED_HIGH_THROTTLE,
        )
        assert len(sustained) == expected_count
        takeoffs = events_of_type(
            analyses,
            BatteryLoadEventType.TAKEOFF,
        )
        assert len(takeoffs) == EXPECTED_AUTO_COUNTS[log_name]
        assert all(
            analysis.start_us <= event.start_us <= event.end_us <= analysis.end_us
            for analysis in analyses
            for event in analysis.bounded_load_events
        )

    log_0, log_0_analyses = results["log_0"]
    assert log_0.parameters == {}
    configuration = log_0_analyses[0].session_configuration
    assert configuration.lookup_time_us == 736_623_934
    assert configuration.capacity_mah == 5000.0
    assert math.isclose(configuration.low_voltage, 13.199999809265137)
    assert math.isclose(
        configuration.critical_voltage,
        12.800000190734863,
    )
    assert configuration.failsafe_voltage_source == 0.0
    assert configuration.warnings == ()

    log_17_configuration = results["log_17"][1][0].session_configuration
    assert log_17_configuration.capacity_mah == 3900.0
    assert log_17_configuration.low_voltage == 14.0
    assert math.isclose(
        log_17_configuration.critical_voltage,
        13.399999618530273,
    )


def test_log_0_auto_takeoff_evidence():
    _, analyses = analyse_log("log_0")
    takeoffs = events_of_type(
        analyses,
        BatteryLoadEventType.TAKEOFF,
    )
    assert len(takeoffs) == 3

    for event, expected in zip(
        takeoffs,
        EXPECTED_LOG_0_TAKEOFFS,
        strict=True,
    ):
        assert event.start_us == expected["start_us"]
        assert event.end_us == expected["end_us"]
        assert event.recovery_time_us == expected["recovery_time_us"]
        for field in (
            "duration_s",
            "consumed_mah_at_start",
            "pre_load_voltage",
            "minimum_voltage",
            "current_at_minimum_voltage",
            "peak_current",
            "average_current",
            "voltage_sag",
            "voltage_after_recovery",
            "voltage_recovery",
            "low_voltage_margin",
            "critical_voltage_margin",
        ):
            assert math.isclose(
                getattr(event, field),
                expected[field],
                rel_tol=1e-9,
            )


test_real_log_event_counts_and_configuration()
test_log_0_auto_takeoff_evidence()

print("Battery load-event real-log regression: PASS")

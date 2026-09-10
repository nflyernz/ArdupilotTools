"""Assertion-based regression coverage for the v0.5 landing analysis."""

from pathlib import Path

from analyses.landing import LandingAnalysis
from core.config import Config
from core.landing_attempt_processor import LandingAttemptProcessor
from core.log_reader import FlightReader


LOGS = (
    "log_11.bin",
    "log_17.bin",
    "log_19.bin",
    "log_26.bin",
)

# (flight number, GPS-stop TimeUS, flare-to-stop seconds, target distance m)
COMPLETED_CASES = {
    "log_19.bin": (1, 743_104_000, 6.70, 19.1),
    "log_26.bin": (4, 2_775_037_000, 5.50, 29.4),
}

LOG_17_FLIGHT_4_DISARM_US = 2_848_866_277
TIME_TOLERANCE_US = 150_000
SECONDS_TOLERANCE = 0.20
DISTANCE_TOLERANCE_M = 1.0


def assert_close(actual, expected, tolerance, label):
    if actual is None or abs(actual - expected) > tolerance:
        raise AssertionError(
            f"{label}: expected {expected} ± {tolerance}, got {actual}"
        )


def analyses_for(flight_log, flight_window):
    return LandingAnalysis(config=config).analyse(
        flight_log,
        flight_window,
    ).report or []


def analysis_at_gps_stop(report, expected_time_us):
    matches = [
        analysis
        for _, _, analysis in report
        if analysis.gps_stop_time_us is not None
        and abs(analysis.gps_stop_time_us - expected_time_us)
        <= TIME_TOLERANCE_US
    ]

    if len(matches) != 1:
        raise AssertionError(
            f"expected one GPS-ended analysis near {expected_time_us}, "
            f"got {len(matches)}"
        )

    return matches[0]


config = Config("Config/landing.yaml")
all_analyses = []
loaded_logs = {}

for log_name in LOGS:
    log_path = Path("Logs") / log_name
    flight_log = FlightReader(log_path, config=config).read()
    loaded_logs[log_name] = flight_log

    if not flight_log.flights:
        raise AssertionError(f"{log_name}: no FlightWindow detected")

    for flight_window in flight_log.flights:
        all_analyses.extend(analyses_for(flight_log, flight_window))


# Existing validation cases must still represent each termination path.
end_reasons = [analysis.end_reason for _, _, analysis in all_analyses]
for reason in ("abort", "disarm", "flight_window_end", "gps"):
    if reason not in end_reasons:
        raise AssertionError(f"expected a {reason}-ended landing attempt")

# GPS observations after disarm cannot retroactively qualify an earlier run.
log_17_report = analyses_for(
    loaded_logs["log_17.bin"],
    loaded_logs["log_17.bin"].flights[3],
)
log_17_matches = [
    analysis
    for _, _, analysis in log_17_report
    if analysis.attempt.end_us == LOG_17_FLIGHT_4_DISARM_US
]

if len(log_17_matches) != 1:
    raise AssertionError(
        "log_17.bin flight 4: expected one attempt ending at "
        f"DISARM {LOG_17_FLIGHT_4_DISARM_US}, got {len(log_17_matches)}"
    )

log_17_analysis = log_17_matches[0]
if log_17_analysis.end_reason != "disarm":
    raise AssertionError("log_17.bin flight 4: expected DISARM end reason")
if log_17_analysis.gps_stop_time_us is not None:
    raise AssertionError(
        "log_17.bin flight 4: post-disarm GPS was accepted"
    )

# At least one logged attempt has no flare event; absence is evidence, not error.
if not any(analysis.flare_time_us is None for _, _, analysis in all_analyses):
    raise AssertionError("expected at least one no-flare landing attempt")

# Completed-case values are descriptive regressions, with practical tolerances.
for log_name, (
    flight_number,
    expected_stop_us,
    expected_flare_to_stop_s,
    expected_target_distance_m,
) in COMPLETED_CASES.items():
    flight_log = loaded_logs[log_name]
    report = analyses_for(
        flight_log,
        flight_log.flights[flight_number - 1],
    )
    analysis = analysis_at_gps_stop(report, expected_stop_us)

    if analysis.end_reason != "gps":
        raise AssertionError(f"{log_name}: expected GPS end reason")

    assert_close(
        analysis.gps_stop_time_us,
        expected_stop_us,
        TIME_TOLERANCE_US,
        f"{log_name} GPS stop",
    )
    assert_close(
        analysis.flare_to_gps_stop_s,
        expected_flare_to_stop_s,
        SECONDS_TOLERANCE,
        f"{log_name} flare-to-GPS-stop",
    )
    assert_close(
        analysis.landing_end_target_distance_m,
        expected_target_distance_m,
        DISTANCE_TOLERANCE_M,
        f"{log_name} target distance",
    )

    if analysis.preflare_time_us is None or analysis.flare_time_us is None:
        raise AssertionError(
            f"{log_name}: completed case lacks known preflare/flare evidence"
        )


# Optional ARSP and RFND must remain non-fatal and explicitly unavailable.
optional_log = loaded_logs["log_19.bin"]
optional_log.messages["ARSP"] = optional_log.get("ARSP").iloc[0:0]
optional_log.messages["RFND"] = optional_log.get("RFND").iloc[0:0]
optional_report = analyses_for(optional_log, optional_log.flights[0])
optional_analysis = analysis_at_gps_stop(optional_report, 743_104_000)

if optional_analysis.preflare_airspeed is not None:
    raise AssertionError("missing ARSP must leave preflare airspeed unavailable")

rangefinder_fields = (
    optional_analysis.rangefinder_first_nonzero_time_us,
    optional_analysis.rangefinder_first_nonzero_distance,
    optional_analysis.rangefinder_first_in_range_time_us,
    optional_analysis.rangefinder_first_in_range_distance,
    optional_analysis.rangefinder_continuous_time_us,
)
if any(value is not None for value in rangefinder_fields):
    raise AssertionError("missing RFND must leave rangefinder evidence unavailable")


# Incomplete CMD snapshots are not accepted as mission-target evidence.
cmd = optional_log.get("CMD").iloc[0:0].copy()
cmd.loc[0] = {
    "TimeUS": 1,
    "CTot": 3,
    "CNum": 0,
    "CId": 16,
    "Lat": 0,
    "Lng": 0,
}
cmd.loc[1] = {
    "TimeUS": 2,
    "CTot": 3,
    "CNum": 2,
    "CId": 21,
    "Lat": -35_0000000,
    "Lng": 174_0000000,
}
if LandingAttemptProcessor._complete_cmd_snapshots(cmd):
    raise AssertionError("incomplete CMD snapshot was accepted")

print("Landing analysis regression: PASS")

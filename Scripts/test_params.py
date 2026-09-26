"""Real BIN logs provide embedded parameter evidence."""

from core.config import Config
from core.log_reader import FlightReader


def test_embedded_parm_and_history_are_available():
    """Read raw PARM and its history from the real BIN."""
    flight_log = FlightReader(
        "Logs/log_17.bin",
        config=Config("Config/landing.yaml"),
    ).read()
    raw_parm = flight_log.get("PARM")

    assert not raw_parm.empty
    assert {"TimeUS", "Name", "Value"}.issubset(raw_parm.columns)
    level_records = raw_parm.loc[raw_parm["Name"] == "AUTOTUNE_LEVEL"]
    assert not level_records.empty
    first_level = level_records.iloc[0]
    assert flight_log.parameter_history.value_at(
        "AUTOTUNE_LEVEL",
        int(first_level["TimeUS"]),
    ) == float(first_level["Value"])

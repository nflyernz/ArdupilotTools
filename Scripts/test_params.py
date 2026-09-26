"""Real BIN logs provide parameter evidence without companion files."""

from pathlib import Path

from core.config import Config
from core.log_reader import FlightReader


def test_embedded_parm_and_history_are_available_without_companion_file(
    monkeypatch,
    tmp_path,
):
    """Read the real BIN from a directory with no companion snapshots."""
    log_path = Path(__file__).resolve().parents[1] / "Logs/log_17.bin"
    monkeypatch.chdir(tmp_path)

    flight_log = FlightReader(
        log_path,
        config=Config("Config/landing.yaml"),
    ).read()
    raw_parm = flight_log.get("PARM")

    assert flight_log.metadata["parameters_loaded"] is False
    assert not raw_parm.empty
    assert {"TimeUS", "Name", "Value"}.issubset(raw_parm.columns)
    level_records = raw_parm.loc[raw_parm["Name"] == "AUTOTUNE_LEVEL"]
    assert not level_records.empty
    first_level = level_records.iloc[0]
    assert flight_log.parameter_history.value_at(
        "AUTOTUNE_LEVEL",
        int(first_level["TimeUS"]),
    ) == float(first_level["Value"])

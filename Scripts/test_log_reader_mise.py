"""Focused tests for retaining runtime mission and status evidence."""

from dataclasses import dataclass

from core.log_reader import FlightReader
from core.takeoff_execution import (
    TakeoffEntryContext,
    TakeoffTerminationReason,
)
from core.takeoff_execution_detector import TakeoffExecutionDetector


class _ReaderConfig:
    """Minimal configuration deliberately omitting core retained evidence."""

    MESSAGES = ("ARM", "GPS", "MODE", "MSG", "VER")

    def get(self, key, default=None):
        """Return only the configured message list needed by FlightReader."""
        if key == "messages":
            return self.MESSAGES
        return default


@dataclass(frozen=True)
class _Message:
    """Small pymavlink message stand-in."""

    message_type: str
    fields: dict

    def get_type(self):
        """Return the DataFlash message name."""
        return self.message_type

    def to_dict(self):
        """Return the normally decoded message fields."""
        return dict(self.fields)


class _Connection:
    """Finite pymavlink connection stand-in."""

    def __init__(self, messages):
        self._messages = iter(messages)

    def recv_match(self):
        """Return the next decoded message, then signal log end."""
        return next(self._messages, None)


def _record(message_type, **fields):
    """Build one decoded DataFlash message."""
    return _Message(
        message_type,
        {
            "mavpackettype": message_type,
            **fields,
        },
    )


def _read(monkeypatch, messages):
    """Read a synthetic decoded stream through normal FlightReader flow."""
    connection = _Connection(messages)
    monkeypatch.setattr(
        "core.log_reader.mavutil.mavlink_connection",
        lambda _filename: connection,
    )
    return FlightReader(
        "synthetic_takeoff.bin",
        config=_ReaderConfig(),
    ).read()


def _firmware_record():
    """Return supported ArduPlane firmware evidence."""
    return _record(
        "VER",
        TimeUS=100_000,
        Maj=4,
        Min=7,
        Pat=1,
        FWS="ArduPlane V4.7.1",
    )


def _mise_record():
    """Return a complete representative runtime mission-execution row."""
    return _record(
        "MISE",
        TimeUS=1_000_000,
        CTot=3,
        CNum=1,
        CId=22,
        Prm1=12.0,
        Prm2=0.0,
        Prm3=0.0,
        Prm4=0.0,
        Lat=-35.0,
        Lng=174.0,
        Alt=40.0,
        Frame=3,
    )


def _stat_record(time_us, stage, suppressed):
    """Return one representative Plane runtime status row."""
    return _record(
        "STAT",
        TimeUS=time_us,
        isFlying=1,
        isFlyProb=0.98,
        Armed=1,
        Safety=0,
        Crash=0,
        Still=0,
        Stage=stage,
        Hit=0,
        AFloor=0,
        Throt=65.0,
        ThH=0.0,
        DCrt=0.0,
        DAlt=0.0,
        Sup=suppressed,
    )


def _pos_record():
    """Return canonical vehicle-position evidence."""
    return _record(
        "POS",
        TimeUS=1_250_000,
        Lat=-35.0,
        Lng=174.0,
        Alt=42.5,
        RelHomeAlt=12.25,
        RelOriginAlt=11.75,
    )


def test_normal_reader_retains_full_mise_records(monkeypatch):
    """MISE uses normal full-dictionary retention despite config omission."""
    assert "MISE" not in _ReaderConfig().get("messages")

    flight_log = _read(
        monkeypatch,
        (
            _firmware_record(),
            _mise_record(),
        ),
    )
    mise = flight_log.get("MISE")

    assert len(mise) == 1
    assert tuple(mise.columns) == (
        "mavpackettype",
        "TimeUS",
        "CTot",
        "CNum",
        "CId",
        "Prm1",
        "Prm2",
        "Prm3",
        "Prm4",
        "Lat",
        "Lng",
        "Alt",
        "Frame",
    )
    assert int(mise.iloc[0]["TimeUS"]) == 1_000_000
    assert int(mise.iloc[0]["CNum"]) == 1
    assert int(mise.iloc[0]["CId"]) == 22


def test_normal_reader_without_mise_preserves_empty_message_behavior(monkeypatch):
    """An absent retained message remains an empty FlightLog dataframe."""
    flight_log = _read(monkeypatch, (_firmware_record(),))

    assert flight_log.get("MISE").empty
    assert not flight_log.has("MISE")


def test_reader_exposed_mise_is_consumed_by_takeoff_detector(monkeypatch):
    """Normal reader output supplies runtime evidence directly to detector."""
    flight_log = _read(
        monkeypatch,
        (
            _firmware_record(),
            _record(
                "MODE",
                TimeUS=900_000,
                Mode=10,
                ModeNum=10,
            ),
            _mise_record(),
            _record(
                "MSG",
                TimeUS=2_000_000,
                Message="Triggered AUTO. GPS speed = 2.0",
            ),
            _record(
                "MSG",
                TimeUS=3_000_000,
                Message="Takeoff complete at 40m",
            ),
        ),
    )

    executions = TakeoffExecutionDetector().detect(flight_log)

    assert len(executions) == 1
    execution = executions[0]
    assert execution.start_us == 1_000_000
    assert execution.end_us == 3_000_000
    assert execution.termination_reason is TakeoffTerminationReason.COMPLETED
    assert execution.launch_trigger is not None
    assert execution.launch_trigger.time_us == 2_000_000
    assert execution.completion is not None
    assert execution.completion.time_us == 3_000_000


def test_normal_reader_retains_full_stat_records(monkeypatch):
    """STAT uses normal full-dictionary retention despite config omission."""
    assert "STAT" not in _ReaderConfig().get("messages")

    flight_log = _read(
        monkeypatch,
        (
            _firmware_record(),
            _stat_record(1_500_000, stage=1, suppressed=1),
        ),
    )
    status = flight_log.get("STAT")

    assert len(status) == 1
    assert tuple(status.columns) == (
        "mavpackettype",
        "TimeUS",
        "isFlying",
        "isFlyProb",
        "Armed",
        "Safety",
        "Crash",
        "Still",
        "Stage",
        "Hit",
        "AFloor",
        "Throt",
        "ThH",
        "DCrt",
        "DAlt",
        "Sup",
    )
    assert int(status.iloc[0]["TimeUS"]) == 1_500_000
    assert int(status.iloc[0]["Stage"]) == 1
    assert int(status.iloc[0]["Sup"]) == 1
    assert float(status.iloc[0]["Throt"]) == 65.0


def test_normal_reader_without_stat_preserves_empty_message_behavior(monkeypatch):
    """An absent retained STAT message remains an empty dataframe."""
    flight_log = _read(monkeypatch, (_firmware_record(),))

    assert flight_log.get("STAT").empty
    assert not flight_log.has("STAT")


def test_normal_reader_retains_full_pos_records(monkeypatch):
    """POS reaches FlightLog unchanged despite configuration omission."""
    assert "POS" not in _ReaderConfig().get("messages")

    flight_log = _read(
        monkeypatch,
        (
            _firmware_record(),
            _pos_record(),
        ),
    )
    position = flight_log.get("POS")

    assert len(position) == 1
    assert tuple(position.columns) == (
        "mavpackettype",
        "TimeUS",
        "Lat",
        "Lng",
        "Alt",
        "RelHomeAlt",
        "RelOriginAlt",
    )
    assert int(position.iloc[0]["TimeUS"]) == 1_250_000
    assert float(position.iloc[0]["RelHomeAlt"]) == 12.25


def test_normal_reader_without_pos_preserves_empty_message_behavior(monkeypatch):
    """An absent retained POS message remains an empty dataframe."""
    flight_log = _read(monkeypatch, (_firmware_record(),))

    assert flight_log.get("POS").empty
    assert not flight_log.has("POS")


def test_reader_exposed_stat_is_consumed_by_takeoff_detector(monkeypatch):
    """Normal reader output supplies STAT evidence directly to detector."""
    flight_log = _read(
        monkeypatch,
        (
            _firmware_record(),
            _record("MODE", TimeUS=1_000_000, Mode=13, ModeNum=13),
            _stat_record(2_000_000, stage=1, suppressed=0),
            _stat_record(3_000_000, stage=3, suppressed=0),
            _stat_record(3_100_000, stage=3, suppressed=0),
            _record("MODE", TimeUS=4_000_000, Mode=5, ModeNum=5),
        ),
    )

    executions = TakeoffExecutionDetector().detect(flight_log)

    assert len(executions) == 1
    execution = executions[0]
    assert execution.entry_context is TakeoffEntryContext.TAKEOFF_MODE
    assert execution.start_us == 1_000_000
    assert execution.end_us == 4_000_000
    assert execution.takeoff_control_completion is not None
    assert execution.takeoff_control_completion.time_us == 3_000_000

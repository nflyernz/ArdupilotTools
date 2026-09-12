"""Focused tests for retaining runtime MISE evidence in FlightLog."""

from dataclasses import dataclass

from core.log_reader import FlightReader
from core.takeoff_execution import TakeoffTerminationReason
from core.takeoff_execution_detector import TakeoffExecutionDetector


class _ReaderConfig:
    """Minimal configuration deliberately omitting core MISE retention."""

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

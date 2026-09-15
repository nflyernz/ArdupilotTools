"""Focused tests for TAKEOFF analysis menu integration and presentation."""

from pathlib import Path

import analyse
import analyses.takeoff as takeoff_module
from analyses.takeoff import TakeoffAnalysisPresentation
from core.flight_data import FlightLog
from core.takeoff_execution import (
    TakeoffEntryContext,
    TakeoffExecution,
    TakeoffExecutionEvent,
    TakeoffExecutionEventType,
    TakeoffTerminationReason,
)


def _execution(*, triggered):
    """Build one detected Mode-13 execution with optional trigger evidence."""
    events = (
        (
            TakeoffExecutionEvent(
                2_000_000,
                TakeoffExecutionEventType.TRIGGERED_AUTO,
            ),
        )
        if triggered
        else ()
    )
    return TakeoffExecution(
        start_us=1_000_000,
        end_us=3_000_000,
        mission_item_number=None,
        command_id=None,
        termination_reason=TakeoffTerminationReason.MODE_EXIT,
        events=events,
        entry_context=TakeoffEntryContext.TAKEOFF_MODE,
    )


def _run_with_executions(monkeypatch, executions):
    """Run presentation with a normally loaded synthetic FlightLog."""
    flight_log = FlightLog()

    class _Reader:
        def __init__(self, _path, config=None):
            self.config = config

        def read(self):
            return flight_log

    monkeypatch.setattr(takeoff_module, "FlightReader", _Reader)
    monkeypatch.setattr(
        takeoff_module.TakeoffAnalysisPresentation,
        "_select_log",
        staticmethod(lambda: Path("Logs/synthetic.bin")),
    )
    monkeypatch.setattr(
        takeoff_module.TakeoffExecutionDetector,
        "detect",
        lambda _self, _flight_log: executions,
    )
    TakeoffAnalysisPresentation(config=object()).run()


def test_menu_lists_and_dispatches_takeoff_analysis(monkeypatch, capsys):
    """Selection 8 invokes the TAKEOFF workflow and returns to the menu."""
    calls = []
    responses = iter(("8", "", "0"))
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(responses))
    monkeypatch.setattr(
        TakeoffAnalysisPresentation,
        "run",
        lambda _self: calls.append("run"),
    )

    analyse.menu()

    output = capsys.readouterr().out
    assert "8. Takeoff Analysis" in output
    assert calls == ["run"]
    assert output.count("Flight Analysis") == 2


def test_takeoff_presentation_handles_no_detected_executions(monkeypatch, capsys):
    """An empty detector result produces a concise operator message."""
    _run_with_executions(monkeypatch, ())

    assert "No TAKEOFF-mode executions found." in capsys.readouterr().out


def test_takeoff_presentation_handles_mode13_without_trigger(monkeypatch, capsys):
    """Detected Mode-13 windows without trigger evidence are not analysed."""
    _run_with_executions(
        monkeypatch,
        (_execution(triggered=False), _execution(triggered=False)),
    )

    output = capsys.readouterr().out
    assert (
        "2 TAKEOFF-mode executions detected; none contained a firmware launch trigger."
        in output
    )
    assert "TAKEOFF 1" not in output


def test_takeoff_presentation_uses_existing_pipeline_and_detected_count(
    monkeypatch,
    capsys,
):
    """Triggered results flow through the processor and multi-report formatter."""
    _run_with_executions(
        monkeypatch,
        (_execution(triggered=True), _execution(triggered=False)),
    )

    output = capsys.readouterr().out
    assert "2 TAKEOFF-mode executions detected" in output
    assert "1 triggered takeoff analysed" in output
    assert "1 non-trigger execution omitted" in output
    assert "Largest pitch tracking error" not in output
    assert "pitch residual" not in output.lower()
    assert "2000000" not in output

"""Portable BIN-only Radio Link episode and presentation contracts."""

from pathlib import Path

import analyse
import analyses.radio_link as radio_presentation
import pandas as pd
import pytest
from core.flight_data import FlightLog
from core.params import ParameterChange, ParameterHistory
from core.radio_link import RadioLinkDetector


def arm(time, state):
    return "ARM", {"TimeUS": time, "ArmState": state}


def rc(time, flags, override=0):
    return "RCI2", {"TimeUS": time, "Flags": flags, "OMask": override}


def msg(time, text):
    return "MSG", {"TimeUS": time, "Message": text}


def mode(time, number, reason=1):
    return "MODE", {"TimeUS": time, "ModeNum": number, "Rsn": reason}


def output(time, throttle):
    return "RCOU", {"TimeUS": time, "C3": throttle}


def stat(time, armed=1, suppressed=0):
    return "STAT", {"TimeUS": time, "Armed": armed, "Sup": suppressed}


def _log(*events, history=None, end=None):
    """Build one FlightLog in original DataFlash cross-message order."""
    rows = {
        "VER": [{
            "TimeUS": 0,
            "_SourceOrder": -1,
            "Maj": 4,
            "Min": 7,
            "Pat": 1,
            "FWS": "ArduPlane V4.7.1 (synthetic)",
        }],
    }
    for order, (kind, fields) in enumerate(events):
        rows.setdefault(kind, []).append({**fields, "_SourceOrder": order})
    last_time = max((fields["TimeUS"] for _, fields in events), default=0)
    return FlightLog(
        messages={kind: pd.DataFrame(values) for kind, values in rows.items()},
        parameter_history=history or ParameterHistory(
            {
                "SERVO3_FUNCTION": 70,
                "SERVO3_MIN": 1100,
                "RCMAP_THROTTLE": 3,
                "THR_FAILSAFE": 1,
                "THR_FS_VALUE": 950,
                "RC_FS_TIMEOUT": 1,
            }
        ),
        flights=[],
        metadata={
            "last_decoded_time_us": end if end is not None else last_time,
            "last_decoded_source_order": len(events) - 1,
        },
    )


def _detect(*events, **kwargs):
    return RadioLinkDetector().detect(_log(*events, **kwargs))


def _report(result):
    return radio_presentation.format_radio_link_report(result, Path("synthetic.bin"))


def test_single_short_long_recovery_uses_distinct_bin_evidence():
    """Sampled input, firmware action, and MODE responses retain their own times."""
    result = _detect(
        arm(1_000_000, 1),
        mode(1_100_000, 0),
        rc(2_000_000, 1),
        rc(10_000_000, 2),
        msg(10_100_000, "Throttle failsafe on"),
        mode(10_200_000, 1, 3),
        msg(10_200_100, "RC Short Failsafe: switched to Circle"),
        mode(15_000_000, 11, 3),
        msg(15_000_100, "RC Long Failsafe On: switched to RTL"),
        msg(20_050_000, "Throttle failsafe off"),
        rc(20_100_000, 1),
        msg(20_200_000, "RC Long Failsafe Cleared"),
        arm(30_000_000, 0),
    )

    assert len(result.episodes) == 1
    episode = result.episodes[0]
    assert (episode.start.time_us, episode.revalid.time_us) == (
        10_000_000, 20_100_000,
    )
    assert (episode.short_mode[1], episode.long_mode[1]) == ("CIRCLE", "RTL")
    assert (episode.short_on.time_us, episode.long_on.time_us) == (
        10_200_100, 15_000_100,
    )
    assert episode.long_clear.time_us == 20_200_000
    assert episode.throttle_off.time_us == 20_050_000
    assert episode.input_duration_s == pytest.approx(10.100)
    assert episode.action_duration_s == pytest.approx(9.9999)
    assert episode.long_duration_s == pytest.approx(5.1999)
    assert episode.armed == "armed throughout"
    assert episode.mode_at_clear == "RTL"


def test_four_recoveries_create_four_episodes_including_short_only_rtl():
    """A repeated short state in unchanged RTL is a new episode."""
    result = _detect(
        arm(1_000_000, 1),
        mode(1_100_000, 0),
        rc(2_000_000, 1),
        rc(10_000_000, 2),
        mode(10_100_000, 1, 3),
        msg(10_100_100, "RC Short Failsafe: switched to Circle"),
        msg(13_000_000, "RC Short Failsafe Cleared"),
        mode(13_000_100, 0, 48),
        rc(13_100_000, 1),
        rc(20_000_000, 2),
        mode(20_100_000, 1, 3),
        msg(20_100_100, "RC Short Failsafe: switched to Circle"),
        mode(25_000_000, 11, 3),
        msg(25_000_100, "RC Long Failsafe On: switched to RTL"),
        rc(30_000_000, 1),
        msg(30_100_000, "RC Long Failsafe Cleared"),
        rc(32_000_000, 2),
        msg(32_100_000, "RC Short Failsafe On"),
        msg(34_000_000, "RC Short Failsafe Cleared"),
        rc(34_100_000, 1),
        rc(36_000_000, 2),
        msg(36_100_000, "RC Short Failsafe On"),
        msg(38_000_000, "RC Short Failsafe Cleared"),
        rc(38_100_000, 1),
        arm(40_000_000, 0),
    )

    episodes = result.episodes
    assert len(episodes) == 4
    assert [ep.start.time_us for ep in episodes] == [
        10_000_000, 20_000_000, 32_000_000, 36_000_000,
    ]
    assert [ep.input_duration_s for ep in episodes] == [3.1, 10.0, 2.1, 2.1]
    assert [bool(ep.long_on) for ep in episodes] == [False, True, False, False]
    assert all(ep.short_on and ep.action_clear for ep in episodes)
    assert episodes[0].recovery_mode[1] == "MANUAL"
    assert episodes[1].long_mode[1] == "RTL"
    assert all(ep.short_mode is None and ep.mode_at_start == "RTL" for ep in episodes[2:])
    assert all(ep.armed == "armed throughout" for ep in episodes)


def test_valid_rc_throughout_has_no_episode_or_rf_health_verdict():
    result = _detect(
        arm(1_000_000, 1),
        rc(2_000_000, 1),
        rc(3_000_000, 1),
        rc(4_000_000, 1),
        msg(4_100_000, "RC Protocol: CRSF"),
        arm(5_000_000, 0),
    )

    assert result.episodes == []
    report = _report(result)
    assert "Armed RC-failsafe episodes: 0" in report
    assert "RF health not assessed" in report
    assert "link healthy" not in report.lower()


def test_open_episode_has_no_invented_recovery_or_completed_duration():
    result = _detect(
        arm(1_000_000, 1),
        rc(2_000_000, 1),
        rc(10_000_000, 2),
        msg(10_100_000, "RC Short Failsafe On"),
        rc(12_000_000, 2),
        end=40_000_000,
    )

    episode = result.episodes[0]
    assert episode.revalid is None
    assert episode.action_clear is None
    assert episode.input_duration_s is None
    assert episode.action_duration_s is None
    assert episode.armed == "armed at start"
    report = _report(result)
    assert "Input invalid (RCI2 sampled): 00:10.000–?; unavailable" in report
    assert "episode open at log boundary" in report
    assert "00:40.000" not in report


def test_high_stale_rxlq_cannot_change_rci2_episode():
    base = (
        arm(1_000_000, 1), rc(2_000_000, 1), rc(10_000_000, 2),
        msg(10_100_000, "RC Short Failsafe On"),
        msg(20_000_000, "RC Short Failsafe Cleared"),
        rc(20_100_000, 1),
    )
    baseline_result = _detect(*base)
    stale_result = _detect(
        *base[:3],
        ("RSSI", {"TimeUS": 10_050_000, "RXLQ": 100}),
        base[3],
        ("RSSI", {"TimeUS": 15_000_000, "RXLQ": 100}),
        base[4],
        ("RSSI", {"TimeUS": 20_050_000, "RXLQ": 100}),
        base[5],
    )
    baseline = baseline_result.episodes[0]
    stale = stale_result.episodes[0]

    assert (stale.start.time_us, stale.revalid.time_us) == (
        baseline.start.time_us, baseline.revalid.time_us,
    )
    assert stale.input_duration_s == baseline.input_duration_s == 10.1
    assert stale.short_on and stale.short_clear
    assert _report(stale_result) == _report(baseline_result)


def test_missing_msg_preserves_rc_episode_and_unstaged_mode_response():
    result = _detect(
        arm(1_000_000, 1), mode(1_100_000, 0), rc(2_000_000, 1),
        rc(10_000_000, 2), mode(10_100_000, 1, 3), rc(20_000_000, 1),
    )

    episode = result.episodes[0]
    assert episode.input_duration_s == 10.0
    assert episode.short_on is None and episode.long_on is None
    assert [(position.time_us, name) for position, name in episode.unassigned_modes] == [
        (10_100_000, "CIRCLE")
    ]
    report = _report(result)
    assert "Short assertion: MSG evidence unavailable" in report
    assert "CIRCLE" in report and "short/long stage unknown" in report


def test_missing_mode_keeps_msg_action_claim_qualified():
    result = _detect(
        arm(1_000_000, 1), rc(2_000_000, 1), rc(10_000_000, 2),
        msg(10_100_000, "RC Short Failsafe: switched to Circle"),
        msg(20_000_000, "RC Short Failsafe Cleared"), rc(20_100_000, 1),
    )

    assert result.episodes[0].short_mode is None
    assert result.episodes[0].short_claim == "CIRCLE"
    assert "MSG claims → CIRCLE; MODE record unavailable" in _report(result)


def test_missing_rci2_reports_action_only_without_input_duration():
    result = _detect(
        arm(1_000_000, 1),
        msg(10_000_000, "RC Short Failsafe On"),
        msg(12_000_000, "RC Short Failsafe Cleared"),
        msg(20_000_000, "RC Short Failsafe On"),
        msg(23_000_000, "RC Short Failsafe Cleared"),
    )

    assert len(result.episodes) == 2
    assert [ep.input_duration_s for ep in result.episodes] == [None, None]
    assert [ep.action_duration_s for ep in result.episodes] == [2.0, 3.0]
    assert "RCI2 unavailable" in _report(result)


def test_disarmed_invalid_period_is_not_numbered_as_armed_test_episode():
    result = _detect(
        arm(1_000_000, 0), rc(2_000_000, 1),
        rc(3_000_000, 2), rc(4_000_000, 1),
        arm(5_000_000, 1), rc(6_000_000, 2), rc(7_000_000, 1),
        arm(8_000_000, 0),
    )

    assert len(result.episodes) == 2
    assert [ep.armed for ep in result.episodes] == [
        "disarmed at start", "armed throughout",
    ]
    assert result.omitted_unarmed == 1
    report = _report(result)
    assert "Armed RC-failsafe episodes: 1" in report
    assert "Unarmed startup/episode evidence omitted: 1" in report
    assert "00:03.000–00:04.000" not in report
    assert "00:06.000–00:07.000" in report


def test_unknown_arm_state_is_visible_but_not_counted_as_armed():
    result = _detect(rc(2_000_000, 1), rc(3_000_000, 2), rc(4_000_000, 1))

    assert result.episodes[0].armed == "unknown"
    report = _report(result)
    assert "Armed RC-failsafe episodes: 0" in report
    assert "No confirmed armed episodes" in report
    assert "00:03.000–00:04.000" in report
    assert "Episodes with unknown armed state: 1" in report


def test_disarm_during_episode_prevents_armed_throughout_claim():
    result = _detect(
        arm(1_000_000, 1), rc(2_000_000, 1),
        rc(3_000_000, 2), arm(4_000_000, 0), rc(5_000_000, 1),
    )

    episode = result.episodes[0]
    assert episode.armed == "armed at start"
    assert "Disarmed during episode" in episode.warnings
    assert "armed throughout" not in _report(result)


def test_stat_armed_fallback_is_explicitly_sampled_when_arm_missing():
    result = _detect(
        stat(1_000_000, armed=1), rc(2_000_000, 1),
        rc(3_000_000, 2), rc(4_000_000, 1),
    )

    assert result.episodes[0].armed == "armed at sampled STAT only; ARM unavailable"
    assert "ARM unavailable" in _report(result)


def test_commanded_throttle_uses_only_interval_samples_and_never_claims_motor_state():
    result = _detect(
        arm(1_000_000, 1), rc(2_000_000, 1),
        output(9_000_000, 1300),
        rc(10_000_000, 2), output(11_000_000, 1100),
        stat(11_500_000, suppressed=1), output(12_000_000, 1200),
        rc(13_000_000, 1), output(14_000_000, 1900),
    )

    episode = result.episodes[0]
    assert "RCOU.C3 1100–1200 µs (sampled input-invalid span)" in episode.throttle
    assert "configured minimum" not in episode.throttle
    assert episode.suppression == "STAT.Sup sampled 1"
    report = _report(result)
    assert "Throttle command (aircraft BIN)" in report
    assert "motor activity unknown" in report
    assert "motor running" not in report.lower()
    assert "1900" not in report and "1300" not in report


def test_throttle_mapping_change_omits_misleading_whole_span_pwm_summary():
    history = ParameterHistory(
        {"SERVO3_FUNCTION": 70, "SERVO3_MIN": 1100},
        {"SERVO3_FUNCTION": (ParameterChange(12_000_000, 0),)},
    )
    result = _detect(
        arm(1_000_000, 1), rc(2_000_000, 1), rc(10_000_000, 2),
        output(11_000_000, 1100), output(13_000_000, 1400),
        rc(14_000_000, 1), history=history,
    )

    episode = result.episodes[0]
    assert episode.throttle is None
    assert any("mapping changed/absent" in note for note in episode.warnings)


def test_menu_dispatches_radio_link_without_changing_existing_choices(monkeypatch, capsys):
    calls = []
    responses = iter(("11", "0"))
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(responses))
    monkeypatch.setattr(
        radio_presentation.RadioLinkAnalysisPresentation,
        "run",
        lambda _self: calls.append("radio"),
    )

    analyse.menu()

    output_text = capsys.readouterr().out
    assert "11. Radio Link Analysis" in output_text
    assert "10. Takeoff Analysis" in output_text
    assert "2. Event Timeline" in output_text
    assert calls == ["radio"]


def test_presentation_uses_shared_single_log_selector_and_ground_log(
    monkeypatch, capsys,
):
    selected = Path("Logs/synthetic.bin")
    log = _log(
        arm(1_000_000, 1), rc(2_000_000, 1),
        rc(3_000_000, 2), rc(4_000_000, 1),
    )
    calls = []

    class Reader:
        def __init__(self, path, config):
            calls.append((path, config))

        def read(self):
            return log

    monkeypatch.setattr(radio_presentation, "select_log_input", lambda: [selected])
    monkeypatch.setattr(radio_presentation, "FlightReader", Reader)
    config = object()

    radio_presentation.RadioLinkAnalysisPresentation(config=config).run()

    assert calls == [(selected, config)]
    assert log.flights == []
    output_text = capsys.readouterr().out
    assert "Radio Link / RC Failsafe — synthetic.bin" in output_text
    assert "Armed RC-failsafe episodes: 1" in output_text
    assert "00:03.000–00:04.000" in output_text

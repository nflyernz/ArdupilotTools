"""Portable optional EdgeTX overlay evidence and ambiguity contracts."""

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

import analyses.radio_link as presentation
import pandas as pd
import pytest
from core.edgetx import (
    AlignmentAnchor,
    analyse_edgetx,
    bounded_alignment,
    gps_clock_from_flight,
    read_edgetx_csv,
)
from core.flight_data import FlightLog
from core.radio_link import FailsafeEpisode, Position, RadioLinkResult


BASE = datetime(2026, 10, 5, tzinfo=timezone.utc)
GPS_EPOCH = datetime(1980, 1, 6, tzinfo=timezone.utc)
HEADER = [
    "Date", "Time", "GPS", "RQly(%)", "1RSS(dB)", "2RSS(dB)",
    "RSNR(dB)", "RFMD", "TPWR(mW)", "TRSS(dB)", "TQly(%)", "FM",
    "Hdg(°)", "Hdg(°)",
]


def _gps_record(boot_s, absolute_s, coordinate=None, *, week_zero=False, order=0):
    # The firmware subtracts 18 s when converting logged GPS week/time to UTC.
    instant = BASE + timedelta(seconds=absolute_s + 18)
    elapsed = instant - GPS_EPOCH
    week = elapsed.days // 7
    gms = int((elapsed - timedelta(weeks=week)).total_seconds() * 1000)
    lat, lng = coordinate or (-35.3589, 174.1017)
    return {
        "TimeUS": int(boot_s * 1e6), "_SourceOrder": order,
        "I": 0, "U": 1, "Status": 3, "GWk": 0 if week_zero else week,
        "GMS": gms, "Lat": lat, "Lng": lng,
    }


def _flight(*, zero_week=False, with_gps=True, slope=1):
    records = []
    for index, boot in enumerate((1, 5, 20, 40, 50)):
        records.append(_gps_record(boot, boot * slope,
                       (-35.35 + index * 0.0001, 174.10 + index * 0.0001),
                       order=index))
    if zero_week:
        records.insert(0, _gps_record(0, 0, week_zero=True, order=-1))
    return FlightLog(messages={"GPS": pd.DataFrame(records) if with_gps else pd.DataFrame()})


def _result(*intervals):
    episodes = [FailsafeEpisode(start=Position(int(start * 1e6), index * 2, "RCI2"),
                                revalid=Position(int(end * 1e6), index * 2 + 1, "RCI2"),
                                armed="armed throughout")
                for index, (start, end) in enumerate(intervals)]
    return RadioLinkResult("ArduPlane V4.7.1", episodes=episodes)


def _row(seconds, *, offset=0, quality=100, rssi=-75, snr=0, mode=2,
         power=50, gps="", fm="", trss=-70, tqly=0):
    clock = (BASE + timedelta(seconds=seconds - offset)).replace(tzinfo=None)
    return {
        "Date": clock.strftime("%Y-%m-%d"), "Time": clock.strftime("%H:%M:%S.%f")[:-3],
        "GPS": gps, "RQly(%)": quality, "1RSS(dB)": rssi,
        "2RSS(dB)": 0, "RSNR(dB)": snr, "RFMD": mode,
        "TPWR(mW)": power, "TRSS(dB)": trss, "TQly(%)": tqly,
        "FM": fm, "Hdg(°)": "",
    }


def _write(tmp_path, rows, *, header=HEADER, name="radio.csv"):
    path = tmp_path / name
    with path.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        for row in rows:
            writer.writerow([row.get(name, "") for name in header])
    return path


def _gap(seconds, *, offset=0):
    return _row(seconds, offset=offset, quality=0, rssi=0, snr=0,
                mode=0, power=0, trss=0, tqly=0)


def _pattern_rows(*, offset=0, gps=False):
    coordinates = {1: "-35.350000 174.100000", 40: "-35.349700 174.100300"}
    return [
        _row(0, offset=offset),
        _row(1, offset=offset, gps=coordinates.get(1, "") if gps else ""),
        _gap(10, offset=offset), _gap(11, offset=offset),
        _row(14, offset=offset, quality=20, rssi=-100),
        _row(17, offset=offset, quality=30, rssi=-95),
        _gap(20, offset=offset), _gap(21, offset=offset),
        _row(30, offset=offset),
        _row(40, offset=offset, gps=coordinates.get(40, "") if gps else ""),
        _row(50, offset=offset),
    ]


def test_gps_zero_week_startup_is_excluded_and_affine_time_is_mapped():
    flight = _flight(zero_week=True, slope=1.002)
    clock = gps_clock_from_flight(flight)
    assert clock is not None
    assert clock.first_boot_s == 1
    assert len(clock.anchors) == 5
    assert clock.slope == pytest.approx(1.002, abs=1e-7)
    assert clock.utc_at(25) == BASE + timedelta(seconds=25.05)
    assert clock.rms_residual_s < 0.001
    assert gps_clock_from_flight(_flight(with_gps=False)) is None


def test_parser_preserves_duplicate_header_and_field_level_availability(tmp_path):
    rows = [
        _row(0, quality=82, rssi=-110, snr=0, tqly=0),
        _gap(0.1), _gap(0.2),
        _row(0.3, quality=0, rssi=0, snr=0, trss=-80, tqly=5),
        _row(0.4, quality=3, rssi=-115, snr=-2, mode=0),
    ]
    session = read_edgetx_csv(_write(tmp_path, rows))
    assert session.header.count("Hdg(°)") == 2
    assert [row.availability for row in session.rows] == [
        "active", "unavailable", "unavailable", "partial", "active",
    ]
    assert session.rows[0].observed("RSNR(dB)") == 0
    assert session.rows[0].observed("2RSS(dB)") is None
    assert session.rows[3].observed("RQly(%)") is None
    assert session.rows[3].observed("RFMD") == 2
    assert session.rows[4].observed("RFMD") == 0
    assert session.extrema("RQly(%)") == (3, 82)
    assert session.extrema("1RSS(dB)") == (-115, -110)
    assert session.extrema("2RSS(dB)") is None
    assert [(run.availability, run.count) for run in session.runs] == [
        ("active", 1), ("unavailable", 2), ("partial", 1), ("active", 1),
    ]


def test_out_of_range_quality_is_not_reported_as_rf_evidence(tmp_path):
    session = read_edgetx_csv(_write(tmp_path, [
        _row(0, quality=999, rssi=0),
        _row(1, quality=80, rssi=-90),
    ]))
    assert session.rows[0].availability == "partial"
    assert session.rows[0].observed("RQly(%)") is None
    assert session.extrema("RQly(%)") == (80, 80)


@pytest.mark.parametrize("rows,header", [
    ([], HEADER),
    ([_row(0)], [name for name in HEADER if name != "RQly(%)"]),
    ([_row(1), _row(0)], HEADER),
])
def test_parser_rejects_empty_missing_required_or_unordered_csv(tmp_path, rows, header):
    with pytest.raises(ValueError):
        read_edgetx_csv(_write(tmp_path, rows, header=header))


def test_good_clock_pattern_can_pair_automatically_without_claiming_alignment(tmp_path):
    session = read_edgetx_csv(_write(tmp_path, _pattern_rows()))
    overlay = analyse_edgetx(_result((10.2, 10.8)), _flight(), session,
                             explicit=False, local_zone=timezone.utc)
    assert overlay.pairing == "accepted automatic"
    assert overlay.alignment.status == "unavailable"
    assert overlay.episode_rf == {}
    assert overlay.session.extrema("RQly(%)") == (20, 100)


def test_wrong_clock_explicit_pair_uses_coordinates_for_coarse_context(tmp_path):
    session = read_edgetx_csv(_write(tmp_path, _pattern_rows(offset=3600, gps=True)))
    overlay = analyse_edgetx(_result((10.2, 10.8)), _flight(), session,
                             explicit=True, local_zone=timezone.utc)
    assert overlay.pairing == "accepted explicit"
    assert overlay.alignment.status == "coarse"
    assert overlay.alignment.offset_s == pytest.approx(3600, abs=0.01)
    assert len(overlay.alignment.anchor_offsets_s) >= 2
    assert overlay.alignment.bound_s is None
    assert any("clock discrepancy" in warning for warning in overlay.warnings)
    assert overlay.episode_rf == {}


def test_split_recovery_csv_can_pair_by_ordered_modes_without_filling_gap(tmp_path):
    rows = [_row(40, fm="RTL "), _row(42, fm="MANU")]
    session = read_edgetx_csv(_write(tmp_path, rows))
    flight = _flight()
    flight.messages["MODE"] = pd.DataFrame([
        {"ModeNum": 11, "TimeUS": 20_000_000},
        {"ModeNum": 0, "TimeUS": 40_000_000},
    ])
    overlay = analyse_edgetx(_result((10, 30)), flight, session,
                             local_zone=timezone.utc)
    assert [row.fm for row in session.rows] == ["RTL", "MANU"]
    assert overlay.pairing == "accepted explicit"
    assert overlay.alignment.status == "unavailable"
    assert overlay.episode_rf == {}
    assert any("episode alignment unavailable" in note for note in overlay.warnings)


def test_coarse_gap_context_is_distinct_from_numeric_rf_aggregation(tmp_path):
    rows = _pattern_rows(gps=True)
    # Widen the first placeholder block around the BIN interval.
    rows = [rows[0], rows[1], _gap(5), _gap(19),
            _row(22), _gap(25), _gap(26), _row(30), rows[-2], rows[-1]]
    session = read_edgetx_csv(_write(tmp_path, rows))
    overlay = analyse_edgetx(_result((10, 14)), _flight(), session,
                             local_zone=timezone.utc)
    assert overlay.alignment.status == "coarse"
    assert 1 in overlay.episode_context
    assert "not a proven bound" in overlay.episode_context[1]
    assert overlay.episode_rf == {}


def test_two_bin_episodes_get_two_distinct_coarse_gaps_without_rf_numbers(tmp_path):
    rows = [_row(0, gps="-35.350000 174.100000"),
            _gap(5), _gap(19), _row(22),
            _gap(25), _gap(39),
            _row(40, gps="-35.349700 174.100300"), _row(50)]
    session = read_edgetx_csv(_write(tmp_path, rows))
    overlay = analyse_edgetx(_result((10, 14), (30, 34)), _flight(), session,
                             local_zone=timezone.utc)
    assert sorted(overlay.episode_context) == [1, 2]
    assert overlay.episode_rf == {}
    assert len(overlay.session.runs) == 5


def test_bounded_numeric_aggregation_requires_two_landmarks_and_sample_age(tmp_path):
    session = read_edgetx_csv(_write(tmp_path, _pattern_rows()))
    flight = _flight()
    anchors = [AlignmentAnchor(5, (BASE + timedelta(seconds=5)).replace(tzinfo=None), 0.05),
               AlignmentAnchor(40, (BASE + timedelta(seconds=40)).replace(tzinfo=None), 0.05)]
    one = bounded_alignment(gps_clock_from_flight(flight), anchors[:1], timezone.utc)
    assert one.status == "unavailable"
    disagree = bounded_alignment(
        gps_clock_from_flight(flight),
        [anchors[0], AlignmentAnchor(40, (BASE + timedelta(seconds=41)).replace(
            tzinfo=None), 0.05)], timezone.utc,
    )
    assert disagree.status == "unavailable"
    overlay = analyse_edgetx(_result((12, 18)), flight, session,
                             local_zone=timezone.utc, anchors=anchors,
                             sample_age_bound_s=0.1)
    assert overlay.alignment.status == "bounded"
    assert len(overlay.alignment.anchor_intervals_s) == 2
    assert overlay.episode_rf[1]["RQly(%)"] == (20, 30)
    assert overlay.episode_rf[1]["1RSS(dB)"] == (-100, -95)
    without_age = analyse_edgetx(_result((12, 18)), flight, session,
                                 local_zone=timezone.utc, anchors=anchors)
    assert without_age.episode_rf == {}


def test_near_recovery_burst_cannot_be_promoted_with_timing_uncertainty(tmp_path):
    rows = _pattern_rows()
    rows.insert(6, _row(17.9, quality=3, rssi=-115))
    session = read_edgetx_csv(_write(tmp_path, rows))
    flight = _flight()
    anchors = [AlignmentAnchor(5, (BASE + timedelta(seconds=5)).replace(tzinfo=None), 0.3),
               AlignmentAnchor(40, (BASE + timedelta(seconds=40)).replace(tzinfo=None), 0.3)]
    overlay = analyse_edgetx(_result((12, 18)), flight, session,
                             local_zone=timezone.utc, anchors=anchors,
                             sample_age_bound_s=0.2)
    assert overlay.session.extrema("RQly(%)")[0] == 3
    assert overlay.episode_rf[1]["RQly(%)"][0] == 20
    assert overlay.episode_rf[1]["1RSS(dB)"][0] == -100


def test_gps_mapped_session_window_excludes_unrelated_earlier_csv_run(tmp_path):
    rows = [_row(-500, quality=1, rssi=-120), *_pattern_rows(gps=True)]
    session = read_edgetx_csv(_write(tmp_path, rows))
    overlay = analyse_edgetx(_result((10, 14)), _flight(), session,
                             local_zone=timezone.utc)
    assert len(overlay.session.rows) == len(rows) - 1
    assert overlay.session.extrema("RQly(%)") == (20, 100)
    assert any("outside GPS-mapped" in warning for warning in overlay.warnings)


def test_auto_selection_rejects_two_equally_supported_csv_candidates(
    tmp_path, monkeypatch,
):
    rows = _pattern_rows()
    _write(tmp_path, rows, name="one.csv")
    _write(tmp_path, rows, name="two.csv")
    monkeypatch.setattr("builtins.input", lambda _: "a")
    real_analysis = presentation.analyse_edgetx
    monkeypatch.setattr(
        presentation, "analyse_edgetx",
        lambda *args, **kwargs: real_analysis(
            *args, local_zone=timezone.utc, **kwargs),
    )
    response = presentation._optional_csv(
        tmp_path / "aircraft.bin", _result((10.2, 10.8)), _flight(),
    )
    assert isinstance(response, str)
    assert "2 accepted CSV candidates" in response


def test_ambiguous_auto_and_missing_gps_keep_bin_result_unchanged(tmp_path):
    rows = [_row(0), _gap(10), _gap(11), _row(20)]
    session = read_edgetx_csv(_write(tmp_path, rows))
    result = _result((12, 18), (25, 30))
    before = [(ep.start, ep.revalid) for ep in result.episodes]
    auto = analyse_edgetx(result, _flight(), session,
                          explicit=False, local_zone=timezone.utc)
    missing = analyse_edgetx(result, _flight(with_gps=False), session,
                             local_zone=timezone.utc)
    assert auto.pairing == "unpaired"
    assert missing.alignment.status == "unavailable"
    assert len(result.episodes) == 2
    assert [(ep.start, ep.revalid) for ep in result.episodes] == before


def test_presentation_labels_bin_and_csv_provenance_without_numeric_episode_claim(tmp_path):
    session = read_edgetx_csv(_write(tmp_path, _pattern_rows(gps=True)))
    result = _result((10, 14))
    overlay = analyse_edgetx(result, _flight(), session, local_zone=timezone.utc)
    report = presentation.format_edgetx_overlay(overlay)
    assert "EdgeTX CSV session observed RQly" in report
    assert "episode-specific RF aggregation unavailable" in report
    assert "EdgeTX CSV radio-clock span" in report
    assert "diagnostic spread, not an uncertainty bound" in report
    assert "packet rate unverified" in report
    assert "not measured radiated power or configuration" in report
    assert "2RSS" not in report


def test_radio_link_menu_path_accepts_optional_csv_after_bin_report(
    tmp_path, monkeypatch, capsys,
):
    csv_path = _write(tmp_path, _pattern_rows(gps=True))
    result = _result((10, 14))
    flight = _flight()
    class Reader:
        def __init__(self, path, config):
            pass
        def read(self):
            return flight
    class Detector:
        def detect(self, log):
            return result
    monkeypatch.setattr(presentation, "select_log_input", lambda: [Path("synthetic.bin")])
    monkeypatch.setattr(presentation, "FlightReader", Reader)
    monkeypatch.setattr(presentation, "RadioLinkDetector", Detector)
    monkeypatch.setattr("builtins.input", lambda _: str(csv_path))
    presentation.RadioLinkAnalysisPresentation(config=object()).run()
    output = capsys.readouterr().out
    assert "Radio Link / RC Failsafe" in output
    assert "EdgeTX CSV — radio.csv" in output
    assert "Armed RC-failsafe episodes: 1" in output


def test_skipping_csv_preserves_exact_bin_report(tmp_path, monkeypatch):
    result = _result((10, 14))
    flight = _flight()
    baseline = presentation.format_radio_link_report(result, tmp_path / "aircraft.bin")
    monkeypatch.setattr("builtins.input", lambda _: "")
    assert presentation._optional_csv(tmp_path / "aircraft.bin", result, flight) is None
    assert presentation.format_radio_link_report(result, tmp_path / "aircraft.bin") == baseline


def test_bad_optional_csv_returns_warning_without_touching_bin_result(
    tmp_path, monkeypatch,
):
    bad = tmp_path / "bad.csv"
    bad.write_text("Date,Time\n2026-10-05,00:00:00.000\n")
    result = _result((10, 14))
    before = [(episode.start, episode.revalid) for episode in result.episodes]
    monkeypatch.setattr("builtins.input", lambda _: str(bad))
    response = presentation._optional_csv(tmp_path / "aircraft.bin", result, _flight())
    assert "CSV unavailable" in response
    assert [(episode.start, episode.revalid) for episode in result.episodes] == before

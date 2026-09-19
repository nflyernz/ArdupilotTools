"""Focused tests for persistent physical battery Pack ID metadata."""

from pathlib import Path

import pytest
from analyses.battery import BatteryAnalysisPresentation
from core.battery_pack_store import (
    BatteryPackStore,
    BatteryPackStoreFormatError,
    LogPackState,
    fingerprint_log,
)


def _inputs(monkeypatch, *responses):
    """Provide deterministic answers to battery-pack prompts."""
    values = iter(responses)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(values))


def _log(path: Path, content: bytes = b"same DataFlash content") -> Path:
    """Create one compact stand-in BIN with controlled content."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_fingerprint_uses_content_not_filename_or_path(tmp_path):
    """Moved or renamed identical content retains one SHA-256 identity."""
    first = _log(tmp_path / "first" / "log_1.bin")
    renamed = _log(tmp_path / "elsewhere" / "renamed.BIN")
    different = _log(tmp_path / "future" / "log_1.bin", b"different content")

    first_fingerprint = fingerprint_log(first)

    assert len(first_fingerprint) == 64
    assert first_fingerprint == fingerprint_log(renamed)
    assert first_fingerprint != fingerprint_log(different)


def test_tracked_associations_and_known_pack_ids_round_trip(tmp_path):
    """Known IDs and tracked source associations survive store reload."""
    path = tmp_path / "Data" / "battery_packs.json"
    first_fingerprint = "1" * 64
    second_fingerprint = "2" * 64
    store = BatteryPackStore(path)

    store.create_and_associate(first_fingerprint, "Pack 1")
    store.associate(second_fingerprint, "Pack 1")
    reloaded = BatteryPackStore(path)

    assert reloaded.pack_ids == ("Pack 1",)
    assert reloaded.association_for(first_fingerprint).state is LogPackState.TRACKED
    assert reloaded.association_for(first_fingerprint).pack_id == "Pack 1"
    assert reloaded.association_for(second_fingerprint).pack_id == "Pack 1"


def test_explicit_not_tracked_state_round_trips_without_synthetic_pack(tmp_path):
    """Declining tracking is durable and creates no placeholder Pack ID."""
    path = tmp_path / "Data" / "battery_packs.json"
    fingerprint = "3" * 64
    store = BatteryPackStore(path)

    store.mark_not_tracked(fingerprint)
    reloaded = BatteryPackStore(path)
    association = reloaded.association_for(fingerprint)

    assert reloaded.pack_ids == ()
    assert association.state is LogPackState.NOT_TRACKED
    assert association.pack_id is None


def test_malformed_store_is_reported_and_not_overwritten(tmp_path):
    """Invalid existing JSON raises explicitly and remains byte-for-byte intact."""
    path = tmp_path / "Data" / "battery_packs.json"
    path.parent.mkdir()
    malformed = b'{"version": 1, "pack_ids": '
    path.write_bytes(malformed)

    with pytest.raises(BatteryPackStoreFormatError, match="Unable to read"):
        BatteryPackStore(path)

    assert path.read_bytes() == malformed


def test_unseen_log_can_create_pack_then_resolves_without_reprompt(
    monkeypatch,
    tmp_path,
):
    """A created association is reused for identical content without input."""
    store_path = tmp_path / "Data" / "battery_packs.json"
    log_path = _log(tmp_path / "flight.bin")
    presentation = BatteryAnalysisPresentation(
        config=object(),
        pack_store=BatteryPackStore(store_path),
    )
    _inputs(monkeypatch, "1", "LiPo-A")

    assert presentation._resolve_pack_id(log_path) == (True, "LiPo-A")

    reloaded_presentation = BatteryAnalysisPresentation(
        config=object(),
        pack_store=BatteryPackStore(store_path),
    )
    monkeypatch.setattr(
        "builtins.input",
        lambda _prompt="": pytest.fail("known association prompted again"),
    )
    assert reloaded_presentation._resolve_pack_id(log_path) == (True, "LiPo-A")


def test_unseen_log_can_select_existing_or_persist_not_tracked(
    monkeypatch,
    tmp_path,
):
    """Both remaining unseen-log decisions persist and suppress later prompts."""
    store_path = tmp_path / "Data" / "battery_packs.json"
    seed_log = _log(tmp_path / "seed.bin", b"seed")
    selected_log = _log(tmp_path / "selected.bin", b"selected")
    untracked_log = _log(tmp_path / "untracked.bin", b"untracked")
    store = BatteryPackStore(store_path)
    store.create_and_associate(fingerprint_log(seed_log), "Pack 1")
    presentation = BatteryAnalysisPresentation(config=object(), pack_store=store)

    _inputs(monkeypatch, "1", "1")
    assert presentation._resolve_pack_id(selected_log) == (True, "Pack 1")

    _inputs(monkeypatch, "3")
    assert presentation._resolve_pack_id(untracked_log) == (True, None)

    reloaded = BatteryPackStore(store_path)
    assert reloaded.association_for(fingerprint_log(selected_log)).pack_id == "Pack 1"
    assert reloaded.association_for(fingerprint_log(untracked_log)).state is (
        LogPackState.NOT_TRACKED
    )
    repeated = BatteryAnalysisPresentation(config=object(), pack_store=reloaded)
    monkeypatch.setattr(
        "builtins.input",
        lambda _prompt="": pytest.fail("not-tracked log prompted again"),
    )
    assert repeated._resolve_pack_id(untracked_log) == (True, None)

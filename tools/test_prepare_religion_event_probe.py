import importlib.util
import hashlib
from pathlib import Path

import pytest
from lxml import etree


SCRIPT = Path(__file__).parent / "experiments" / "prepare_religion_event_probe.py"
spec = importlib.util.spec_from_file_location("prepare_religion_event_probe", SCRIPT)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    source = tmp_path / "source" / "RemselysAlexanderII.modinfo"
    source.parent.mkdir()
    source.write_bytes(probe.SOURCE.read_bytes())
    target = tmp_path / "Documents" / "My Games" / "Sid Meier's Civilization VI" / "Mods" / "RemselysAlexanderII"
    target.mkdir(parents=True)
    (target / source.name).write_bytes(source.read_bytes())
    (target / "unrelated.txt").write_text("preserve me")
    monkeypatch.setattr(probe, "SOURCE", source)
    monkeypatch.setattr(probe, "STAGE", tmp_path / "stage")
    monkeypatch.setattr(probe.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(probe, "game_running", lambda: False)
    return source, target


def test_stage_install_restore_preserves_unrelated_files(sandbox):
    source, target = sandbox
    candidate = probe.stage()
    parsed = etree.parse(str(candidate))
    rel = probe.RELATIVE
    assert len(parsed.xpath("./Files/File[text()=$path]", path=rel)) == 1
    assert len(parsed.xpath("./InGameActions/AddGameplayScripts/File[text()=$path]", path=rel)) == 1
    probe.install(candidate)
    assert (target / rel).read_bytes() == probe.PROBE.read_bytes()
    assert (target / source.name).read_bytes() == candidate.read_bytes()
    assert (target / "unrelated.txt").read_text() == "preserve me"
    probe.restore(candidate)
    assert (target / source.name).read_bytes() == source.read_bytes()
    assert not (target / rel).exists()
    assert (target / "unrelated.txt").read_text() == "preserve me"


def test_install_refuses_changed_modinfo_and_existing_probe(sandbox):
    source, target = sandbox
    candidate = probe.stage()
    info = target / source.name
    info.write_text("changed")
    with pytest.raises(SystemExit, match="differs"):
        probe.install(candidate)
    assert info.read_text() == "changed"
    info.write_bytes(source.read_bytes())
    existing = target / probe.RELATIVE
    existing.parent.mkdir(parents=True)
    existing.write_text("different probe")
    with pytest.raises(SystemExit, match="already exists"):
        probe.install(candidate)
    assert existing.read_text() == "different probe"


def test_running_game_refuses_install_before_modifying_files(sandbox, monkeypatch):
    source, target = sandbox
    candidate = probe.stage()
    monkeypatch.setattr(probe, "game_running", lambda: True)
    with pytest.raises(SystemExit, match="Close Civilization"):
        probe.install(candidate)
    assert (target / source.name).read_bytes() == source.read_bytes()
    assert not (target / probe.RELATIVE).exists()


def test_restore_accepts_exact_known_legacy_probe(sandbox, monkeypatch):
    source, target = sandbox
    candidate = probe.stage()
    probe.install(candidate)
    legacy = b"previous known read-only probe"
    target_probe = target / probe.RELATIVE
    target_probe.write_bytes(legacy)
    monkeypatch.setattr(probe, "LEGACY_PROBE_SHA256", frozenset({hashlib.sha256(legacy).hexdigest()}))
    probe.restore(candidate)
    assert (target / source.name).read_bytes() == source.read_bytes()
    assert not target_probe.exists()


def test_restore_refuses_unknown_modified_probe(sandbox):
    source, target = sandbox
    candidate = probe.stage()
    probe.install(candidate)
    target_probe = target / probe.RELATIVE
    target_probe.write_text("modified externally")
    with pytest.raises(SystemExit, match="differs"):
        probe.restore(candidate)
    assert target_probe.read_text() == "modified externally"
    assert (target / source.name).read_bytes() == candidate.read_bytes()

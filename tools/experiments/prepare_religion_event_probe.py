"""Stage or temporarily install a read-only probe into the existing mod.

Default: stage only in art/build/religion-probe. --install requires Civ VI to be
closed, the installed modinfo to match the source exactly, and no existing probe.
It edits only that modinfo and adds a new Lua file; it does not reinstall/delete
the mod, alter saves, change gameplay state or start the game. --restore undoes
those two changes only when the installed files still match the staged probe.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
from pathlib import Path

from lxml import etree


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "mod" / "RemselysAlexanderII.modinfo"
PROBE = ROOT / "tools" / "experiments" / "religion_event_probe.lua"
STAGE = ROOT / "art" / "build" / "religion-probe"
RELATIVE = "Lua/RemselysAlexanderII_ReligionProbe.lua"
# Exact digest of the read-only probe installed for the 17 Nov 2026 trial.
# Its operation constant was nil in gameplay; retain its identity solely so
# that `--restore` can safely remove it after the source probe is updated.
LEGACY_PROBE_SHA256 = frozenset({
    "b053375b8a029408f77fda45489c3c7526ac29e80e665f05ce6600de36086157",
})


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def game_running() -> bool:
    result = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], check=True, capture_output=True, text=True)
    output = result.stdout.lower()
    return '"civilizationvi.exe"' in output or '"civilizationvi_dx12.exe"' in output


def stage() -> Path:
    STAGE.mkdir(parents=True, exist_ok=True)
    original = SOURCE.read_bytes()
    root = etree.fromstring(original)
    action = root.find("./InGameActions/AddGameplayScripts[@id='REMSELY_InGame_Scripts']")
    files = root.find("./Files")
    if action is None or files is None:
        raise SystemExit("Expected gameplay action or file list not found.")
    if root.xpath(".//File[text()=$path]", path=RELATIVE):
        raise SystemExit("Probe already present in source modinfo; inspect manually.")
    etree.SubElement(action, "File").text = RELATIVE
    etree.SubElement(files, "File").text = RELATIVE
    candidate = STAGE / SOURCE.name
    candidate.write_bytes(etree.tostring(root, encoding="UTF-8", xml_declaration=True, pretty_print=True))
    (STAGE / "original.modinfo").write_bytes(original)
    shutil.copy2(PROBE, STAGE / "RemselysAlexanderII_ReligionProbe.lua")
    print(f"Staged probe: {candidate}")
    print(f"Original modinfo SHA-256: {hashlib.sha256(original).hexdigest()}")
    return candidate


def install(candidate: Path) -> None:
    if os.name != "nt" or game_running():
        raise SystemExit("Close Civilization VI before installing the diagnostic probe.")
    target = Path.home() / "Documents" / "My Games" / "Sid Meier's Civilization VI" / "Mods" / "RemselysAlexanderII"
    target_info = target / SOURCE.name
    target_probe = target / RELATIVE
    temporary = target_info.with_suffix(".modinfo.remsely-probe.tmp")
    if not target_info.is_file() or digest(target_info) != digest(SOURCE):
        raise SystemExit("Installed modinfo differs from source or is missing; no files changed.")
    if target_probe.exists():
        raise SystemExit("A probe file already exists in the installed mod; no files changed.")
    if temporary.exists():
        raise SystemExit("The temporary modinfo path already exists; no files changed.")
    target_probe.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PROBE, target_probe)
    try:
        temporary.write_bytes(candidate.read_bytes())
        os.replace(temporary, target_info)
    except BaseException:
        target_probe.unlink(missing_ok=True)
        temporary.unlink(missing_ok=True)
        raise
    print(f"Installed read-only probe in {target}; restart the game.")


def restore(candidate: Path) -> None:
    if os.name != "nt" or game_running():
        raise SystemExit("Close Civilization VI before restoring the diagnostic probe.")
    target = Path.home() / "Documents" / "My Games" / "Sid Meier's Civilization VI" / "Mods" / "RemselysAlexanderII"
    target_info = target / SOURCE.name
    target_probe = target / RELATIVE
    temporary = target_info.with_suffix(".modinfo.remsely-probe.tmp")
    if not target_info.is_file() or digest(target_info) != digest(candidate):
        raise SystemExit("Installed modinfo differs from staged probe; no files changed.")
    recognized_probe_hashes = LEGACY_PROBE_SHA256 | {digest(PROBE)}
    if not target_probe.is_file() or digest(target_probe) not in recognized_probe_hashes or temporary.exists():
        raise SystemExit("Installed probe differs or temporary path exists; no files changed.")
    temporary.write_bytes((STAGE / "original.modinfo").read_bytes())
    os.replace(temporary, target_info)
    target_probe.unlink()
    print(f"Removed read-only probe from {target}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--install", action="store_true")
    mode.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    path = stage()
    if args.install:
        install(path)
    elif args.restore:
        restore(path)

"""Stage, temporarily install, or restore the passive input probe.

Installation uses the actual installed modinfo as its base, preserving any
existing religion probe. It never modifies the repository's modinfo or saves.
Use a different --out directory for each distinct base modinfo; pass the same
--out to --restore to recover exactly the original installed bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASE = ROOT / 'mod/RemselysAlexanderII.modinfo'
DEFAULT_OUT = ROOT / 'art/build/voice-input-probe'
EXPERIMENTS = Path(__file__).resolve().parent
XML = 'UI/RemselysAlexanderII_VoiceInputProbe.xml'
LUA = 'UI/RemselysAlexanderII_VoiceInputProbe.lua'
ACTION = 'REMSELY_VoiceInputProbe'
MODINFO = 'RemselysAlexanderII.modinfo'
TEMP = MODINFO + '.voice-input-probe.tmp'


def build_candidate(original: bytes) -> bytes:
    root = ET.fromstring(original)
    actions, files = root.find('./InGameActions'), root.find('./Files')
    if actions is None or files is None:
        raise ValueError('Expected InGameActions and Files sections')
    if any(n.get('id') == ACTION for n in actions) or any(
            (n.text or '').strip() in (XML, LUA) for n in files.findall('./File')):
        raise ValueError('Input probe already exists in the base modinfo')
    action = ET.SubElement(actions, 'AddUserInterfaces', {'id': ACTION})
    props = ET.SubElement(action, 'Properties')
    ET.SubElement(props, 'Context').text = 'InGame'
    ET.SubElement(action, 'File').text = XML
    for path in (XML, LUA):
        ET.SubElement(files, 'File').text = path
    ET.indent(root, space='  ')
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def prepare(base: Path, out: Path) -> dict:
    original = base.read_bytes()
    candidate = build_candidate(original)
    staged = {
        Path(MODINFO): candidate,
        Path('original.modinfo'): original,
        Path(XML): (EXPERIMENTS / 'voice_input_probe.xml').read_bytes(),
        Path(LUA): (EXPERIMENTS / 'voice_input_probe.lua').read_bytes(),
    }
    # Never overwrite a different staged experiment silently.
    for path, content in staged.items():
        dest = out / path
        if dest.exists() and dest.read_bytes() != content:
            raise FileExistsError(f'Staged file differs: {dest}')
    for path, content in staged.items():
        dest = out / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
    result = {'base_path': str(base), 'base_sha256': hashlib.sha256(original).hexdigest(),
              'candidate_sha256': hashlib.sha256(candidate).hexdigest(),
              'files': [XML, LUA], 'installed': False}
    return result


def game_running() -> bool:
    result = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], check=True,
                            capture_output=True, text=True)
    output = result.stdout.lower()
    return '"civilizationvi.exe"' in output or '"civilizationvi_dx12.exe"' in output


def require_closed() -> None:
    if game_running():
        raise RuntimeError('Close Civilization VI before changing the installed mod')


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_exclusive(path: Path, data: bytes) -> None:
    # The candidate is not referenced by modinfo until the final atomic swap.
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open('xb')
    try:
        with stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        # Remove only the bytes we could have written; preserve unrelated drift.
        if path.exists() and data.startswith(path.read_bytes()):
            path.unlink()
        raise


def staged_data(out: Path) -> tuple[bytes, bytes, dict[str, bytes]]:
    original = (out / 'original.modinfo').read_bytes()
    candidate = (out / MODINFO).read_bytes()
    # The staged modinfo must contain exactly the one generated change.
    if candidate != build_candidate(original):
        raise ValueError('Staged modinfo differs from the expected overlay')
    root = ET.fromstring(candidate)
    actions = [n for n in root.findall('./InGameActions/AddUserInterfaces')
               if n.get('id') == ACTION]
    files = [(n.text or '').strip() for n in root.findall('./Files/File')]
    if (len(actions) != 1 or actions[0].findtext('./File') != XML
            or files.count(XML) != 1 or files.count(LUA) != 1):
        raise ValueError('Invalid staged probe modinfo')
    originals = ET.fromstring(original)
    if any(n.get('id') == ACTION for n in originals.findall('./InGameActions/*')):
        raise ValueError('Original modinfo unexpectedly contains the input probe')
    data = {p: (out / p).read_bytes() for p in (XML, LUA)}
    # Stage must be an exact copy of the diagnostic scripts we reviewed.
    if data[XML] != (EXPERIMENTS / 'voice_input_probe.xml').read_bytes() or \
       data[LUA] != (EXPERIMENTS / 'voice_input_probe.lua').read_bytes():
        raise ValueError('Staged probe differs from the reviewed source')
    return original, candidate, data


def install(target: Path, out: Path) -> None:
    require_closed()
    original, candidate, data = staged_data(out)
    info, temporary = target / MODINFO, target / TEMP
    if not info.is_file() or digest(info.read_bytes()) != digest(original):
        raise RuntimeError('Installed modinfo differs from staged original; nothing changed')
    if temporary.exists() or any((target / p).exists() for p in data):
        raise RuntimeError('A probe or temporary file already exists; nothing changed')
    created: list[tuple[Path, bytes]] = []
    try:
        for relative, content in data.items():
            path = target / relative
            # 'xb' refuses collisions; retain path for rollback even if writing fails.
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as stream:
                created.append((path, content))
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        write_exclusive(temporary, candidate)
        require_closed()
        if digest(info.read_bytes()) != digest(original):
            raise RuntimeError('Installed modinfo changed during installation')
        if any(digest((target / p).read_bytes()) != digest(content)
               for p, content in data.items()):
            raise RuntimeError('Probe file changed during installation')
        # Atomic commit point: only now can the game discover the new context.
        os.replace(temporary, info)
    except BaseException as error:
        drift = []
        if temporary.exists():
            if candidate.startswith(temporary.read_bytes()):
                temporary.unlink()
            else:
                drift.append(str(temporary))
        for path, content in reversed(created):
            if path.exists():
                if content.startswith(path.read_bytes()):
                    path.unlink()
                else:
                    drift.append(str(path))
        if drift:
            raise RuntimeError('Installation rollback preserved changed files: ' + ', '.join(drift)) from error
        raise


def restore(target: Path, out: Path) -> None:
    require_closed()
    original, candidate, data = staged_data(out)
    info, temporary = target / MODINFO, target / TEMP
    if not info.is_file() or digest(info.read_bytes()) != digest(candidate):
        raise RuntimeError('Installed modinfo differs from the staged probe; nothing changed')
    if temporary.exists() or any(not (target / p).is_file() or
                                  digest((target / p).read_bytes()) != digest(content)
                                  for p, content in data.items()):
        raise RuntimeError('Probe or temporary file differs; nothing changed')
    # Write the exact pre-install bytes, which also preserves the religion probe.
    write_exclusive(temporary, original)
    removed: list[str] = []
    committed = False
    try:
        require_closed()
        if digest(info.read_bytes()) != digest(candidate) or any(
                digest((target / p).read_bytes()) != digest(content)
                for p, content in data.items()):
            raise RuntimeError('Installed files changed during restore')
        os.replace(temporary, info)
        committed = True
        for relative in data:
            (target / relative).unlink()
            removed.append(relative)
    except BaseException:
        if temporary.exists():
            temporary.unlink()
        if committed:
            # Restore our deleted files and the candidate only if no drift has
            # occurred. Never overwrite a user's independently changed file.
            if digest(info.read_bytes()) != digest(original):
                raise RuntimeError('Restore rollback blocked: modinfo changed')
            for relative in removed:
                write_exclusive(target / relative, data[relative])
            if any(not (target / p).is_file() or
                   digest((target / p).read_bytes()) != digest(content)
                   for p, content in data.items()):
                raise RuntimeError('Restore rollback blocked: probe files changed')
            write_exclusive(temporary, candidate)
            os.replace(temporary, info)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path)
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT,
                        help='Staging directory; use the same path for --restore')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--install', action='store_true')
    mode.add_argument('--restore', action='store_true')
    args = parser.parse_args()
    out = args.out.resolve()
    target = Path.home() / "Documents/My Games/Sid Meier's Civilization VI/Mods/RemselysAlexanderII"
    if out == target.resolve() or out.is_relative_to(target.resolve()):
        parser.error('--out must be outside the installed mod directory')
    if args.restore:
        if args.base is not None:
            parser.error('--base is not used with --restore')
        restore(target, out)
        print('Input probe removed; exact original modinfo restored.')
    elif args.install:
        require_closed()
        result = prepare(args.base or target / MODINFO, out)
        install(target, out)
        result['installed'] = True
        result['staging_path'] = str(out)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        result = prepare(args.base or DEFAULT_BASE, out)
        result['staging_path'] = str(out)
        print(json.dumps(result, ensure_ascii=False, indent=2))

"""Stage, install or restore the read-only religious event-stream trace.

The default only stages. Installation requires the game closed and the exact
repository modinfo installed; it refuses any existing probe or changed files.
No saves or repository mod files are changed. Use the same --out for restore.
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
SOURCE = ROOT / 'mod/RemselysAlexanderII.modinfo'
TRACE = ROOT / 'tools/experiments/religion_event_stream_trace.lua'
DEFAULT_OUT = ROOT / 'art/build/religion-event-stream-trace'
MODINFO = 'RemselysAlexanderII.modinfo'
RELATIVE = 'Lua/RemselysAlexanderII_ReligionEventStreamTrace.lua'
ACTION = 'REMSELY_InGame_Scripts'
TEMP = MODINFO + '.religion-stream.tmp'


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_candidate(original: bytes) -> bytes:
    root = ET.fromstring(original)
    action = root.find(f"./InGameActions/AddGameplayScripts[@id='{ACTION}']")
    files = root.find('./Files')
    if action is None or files is None:
        raise ValueError('Expected gameplay action and Files list')
    if any((x.text or '').strip()==RELATIVE for x in root.findall('.//File')):
        raise ValueError('Trace already appears in the base modinfo')
    ET.SubElement(action, 'File').text = RELATIVE
    ET.SubElement(files, 'File').text = RELATIVE
    ET.indent(root, space='  ')
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def prepare(out: Path) -> dict:
    original,trace=SOURCE.read_bytes(),TRACE.read_bytes()
    candidate=build_candidate(original)
    meta={'version':1,'original_sha256':digest(original),
          'candidate_sha256':digest(candidate),'trace_sha256':digest(trace)}
    staged={'original.modinfo':original,MODINFO:candidate,RELATIVE:trace,
            'manifest.json':(json.dumps(meta,sort_keys=True,indent=2)+'\n').encode('utf-8')}
    for path,data in staged.items():
        dest=out/path
        if dest.exists() and (not dest.is_file() or dest.read_bytes()!=data):
            raise FileExistsError(f'Staged file differs: {dest}')
    for path,data in staged.items():
        dest=out/path;dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists(): write_exclusive(dest,data)
    return meta


def staged_data(out: Path) -> tuple[bytes,bytes,bytes]:
    original=(out/'original.modinfo').read_bytes()
    candidate=(out/MODINFO).read_bytes()
    trace=(out/RELATIVE).read_bytes()
    meta=json.loads((out/'manifest.json').read_text(encoding='utf-8'))
    expected={'version':1,'original_sha256':digest(original),
              'candidate_sha256':digest(candidate),'trace_sha256':digest(trace)}
    if meta!=expected or candidate!=build_candidate(original):
        raise ValueError('Staged trace differs from its manifest or expected modinfo')
    return original,candidate,trace


def game_running() -> bool:
    result=subprocess.run(['tasklist','/FO','CSV','/NH'],check=True,capture_output=True,text=True)
    output=result.stdout.lower()
    return '"civilizationvi.exe"' in output or '"civilizationvi_dx12.exe"' in output


def require_closed() -> None:
    if game_running(): raise RuntimeError('Close Civilization VI before changing installed mod')


def write_exclusive(path: Path,data: bytes) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    stream=path.open('xb')  # Existing paths must never be deleted on open failure.
    try:
        with stream:
            stream.write(data);stream.flush();os.fsync(stream.fileno())
    except BaseException:
        if path.exists() and data.startswith(path.read_bytes()): path.unlink()
        raise


def install(target: Path,out: Path) -> None:
    require_closed()
    original,candidate,trace=staged_data(out)
    if SOURCE.read_bytes()!=original or TRACE.read_bytes()!=trace:
        raise RuntimeError('Reviewed source differs from staged files; nothing changed')
    info,temp,probe=target/MODINFO,target/TEMP,target/RELATIVE
    if not info.is_file() or info.read_bytes()!=original:
        raise RuntimeError('Installed modinfo differs from source; nothing changed')
    if probe.exists() or temp.exists():
        raise RuntimeError('Trace or temporary file already exists; nothing changed')
    created=False
    try:
        write_exclusive(probe,trace);created=True
        write_exclusive(temp,candidate)
        require_closed()
        if info.read_bytes()!=original or probe.read_bytes()!=trace:
            raise RuntimeError('Installed files changed during installation')
        os.replace(temp,info)
    except BaseException as error:
        drift=[]
        if temp.exists():
            if candidate.startswith(temp.read_bytes()):temp.unlink()
            else:drift.append(str(temp))
        if created and probe.exists():
            if trace==probe.read_bytes():probe.unlink()
            else:drift.append(str(probe))
        if drift:raise RuntimeError('Rollback preserved changed files: '+', '.join(drift)) from error
        raise


def restore(target: Path,out: Path) -> None:
    require_closed()
    original,candidate,trace=staged_data(out)
    info,temp,probe=target/MODINFO,target/TEMP,target/RELATIVE
    if not info.is_file() or info.read_bytes()!=candidate:
        raise RuntimeError('Installed modinfo differs from staged trace; nothing changed')
    if temp.exists() or not probe.is_file() or probe.read_bytes()!=trace:
        raise RuntimeError('Trace or temporary file differs; nothing changed')
    write_exclusive(temp,original)
    committed=False
    try:
        require_closed()
        if info.read_bytes()!=candidate or probe.read_bytes()!=trace:
            raise RuntimeError('Installed files changed during restore')
        os.replace(temp,info);committed=True
        probe.unlink()
    except BaseException as error:
        if temp.exists() and original.startswith(temp.read_bytes()):temp.unlink()
        if committed:
            if info.read_bytes()!=original or not probe.exists() or probe.read_bytes()!=trace:
                raise RuntimeError('Restore rollback blocked: installed files changed') from error
            write_exclusive(temp,candidate);os.replace(temp,info)
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=DEFAULT_OUT)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--install',action='store_true')
    mode.add_argument('--restore',action='store_true')
    args=parser.parse_args()
    out=args.out.resolve()
    target=Path.home()/"Documents/My Games/Sid Meier's Civilization VI/Mods/RemselysAlexanderII"
    if out==target.resolve() or out.is_relative_to(target.resolve()):
        parser.error('--out must be outside the installed mod')
    if args.restore:
        restore(target,out);print('Restored original installed modinfo.')
    elif args.install:
        require_closed();meta=prepare(out);install(target,out)
        print(json.dumps({'installed':True,**meta},ensure_ascii=False))
    else:
        print(json.dumps({'installed':False,**prepare(out)},ensure_ascii=False))

"""Exercise staging, guarded installation and restore in disposable folders."""
from pathlib import Path
import importlib.util
import json
import xml.etree.ElementTree as ET

import pytest


def fixture(tmp_path,monkeypatch):
    spec=importlib.util.spec_from_file_location('stream_stage','tools/experiments/prepare_religion_stream_trace.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    source=tmp_path/'source.modinfo';trace=tmp_path/'trace.lua'
    source.write_bytes(b'<Mod><InGameActions><AddGameplayScripts id="REMSELY_InGame_Scripts">'
                       b'<File>Lua/Existing.lua</File></AddGameplayScripts></InGameActions>'
                       b'<Files><File>Lua/Existing.lua</File></Files></Mod>')
    trace.write_bytes(b'-- read-only diagnostic\n')
    monkeypatch.setattr(m,'SOURCE',source);monkeypatch.setattr(m,'TRACE',trace)
    monkeypatch.setattr(m,'game_running',lambda:False)
    target=tmp_path/'installed';target.mkdir();(target/m.MODINFO).write_bytes(source.read_bytes())
    out=tmp_path/'staged'
    return m,target,out,source,trace


def test_stage_only_and_exact_atomic_install_restore(tmp_path,monkeypatch):
    m,target,out,source,trace=fixture(tmp_path,monkeypatch)
    original=(target/m.MODINFO).read_bytes();metadata=m.prepare(out)
    assert (target/m.MODINFO).read_bytes()==original and not (target/m.RELATIVE).exists()
    assert json.loads((out/'manifest.json').read_text())==metadata
    root=ET.parse(out/m.MODINFO)
    assert root.find("./InGameActions/AddGameplayScripts/File[2]").text==m.RELATIVE
    assert len([e for e in root.findall('./Files/File') if e.text==m.RELATIVE])==1
    m.install(target,out)
    assert (target/m.MODINFO).read_bytes()==(out/m.MODINFO).read_bytes()
    assert (target/m.RELATIVE).read_bytes()==trace.read_bytes()
    m.restore(target,out)
    assert (target/m.MODINFO).read_bytes()==original and not (target/m.RELATIVE).exists()


def test_running_game_changed_modinfo_or_existing_probe_refuses(tmp_path,monkeypatch):
    m,target,out,source,trace=fixture(tmp_path,monkeypatch);m.prepare(out)
    info=target/m.MODINFO;original=info.read_bytes()
    monkeypatch.setattr(m,'game_running',lambda:True)
    with pytest.raises(RuntimeError,match='Close Civilization'):m.install(target,out)
    assert info.read_bytes()==original
    monkeypatch.setattr(m,'game_running',lambda:False)
    info.write_bytes(b'<old-religion-probe/>')
    with pytest.raises(RuntimeError,match='differs from source'):m.install(target,out)
    assert info.read_bytes()==b'<old-religion-probe/>'
    info.write_bytes(original)
    probe=target/m.RELATIVE;probe.parent.mkdir(parents=True);probe.write_bytes(b'foreign')
    with pytest.raises(RuntimeError,match='already exists'):m.install(target,out)
    assert probe.read_bytes()==b'foreign' and info.read_bytes()==original


def test_staged_or_source_drift_is_not_overwritten(tmp_path,monkeypatch):
    m,target,out,source,trace=fixture(tmp_path,monkeypatch);m.prepare(out)
    staged=out/m.RELATIVE;staged.write_bytes(b'changed')
    with pytest.raises(FileExistsError):m.prepare(out)
    with pytest.raises(ValueError,match='manifest'):m.install(target,out)
    assert not (target/m.RELATIVE).exists()
    staged.write_bytes(trace.read_bytes())
    source.write_bytes(source.read_bytes()+b' ')
    with pytest.raises(RuntimeError,match='Reviewed source'):m.install(target,out)


def test_changed_installed_trace_is_preserved_on_restore(tmp_path,monkeypatch):
    m,target,out,source,trace=fixture(tmp_path,monkeypatch);m.prepare(out);m.install(target,out)
    probe=target/m.RELATIVE;probe.write_bytes(b'changed by user')
    with pytest.raises(RuntimeError,match='Trace or temporary file differs'):m.restore(target,out)
    assert probe.read_bytes()==b'changed by user' and (target/m.MODINFO).read_bytes()==(out/m.MODINFO).read_bytes()


def test_install_atomic_failure_rolls_back_own_files(tmp_path,monkeypatch):
    m,target,out,source,trace=fixture(tmp_path,monkeypatch);m.prepare(out)
    def fail(*args):raise OSError('injected atomic replace failure')
    monkeypatch.setattr(m.os,'replace',fail)
    with pytest.raises(OSError,match='injected'):m.install(target,out)
    assert (target/m.MODINFO).read_bytes()==source.read_bytes()
    assert not (target/m.RELATIVE).exists() and not (target/m.TEMP).exists()


def test_game_start_or_concurrent_probe_edit_is_never_overwritten(tmp_path,monkeypatch):
    m,target,out,source,trace=fixture(tmp_path,monkeypatch);m.prepare(out)
    calls=0
    def started():
        nonlocal calls
        calls+=1
        if calls==2:raise RuntimeError('game started')
    monkeypatch.setattr(m,'require_closed',started)
    with pytest.raises(RuntimeError,match='game started'):m.install(target,out)
    assert (target/m.MODINFO).read_bytes()==source.read_bytes() and not (target/m.RELATIVE).exists()
    calls=0
    def changed():
        nonlocal calls
        calls+=1
        if calls==2:
            (target/m.RELATIVE).write_bytes(b'user changed probe')
            raise RuntimeError('game started')
    monkeypatch.setattr(m,'require_closed',changed)
    with pytest.raises(RuntimeError,match='preserved changed files'):m.install(target,out)
    assert (target/m.RELATIVE).read_bytes()==b'user changed probe'
    assert (target/m.MODINFO).read_bytes()==source.read_bytes()


def test_existing_exclusive_file_never_removed_even_if_prefix_matches(tmp_path,monkeypatch):
    m,target,out,source,trace=fixture(tmp_path,monkeypatch)
    existing=tmp_path/'user-file';existing.write_bytes(b'')
    with pytest.raises(FileExistsError):m.write_exclusive(existing,b'abc')
    assert existing.exists() and existing.read_bytes()==b''


def test_restore_handles_source_change_and_rejects_late_drift(tmp_path,monkeypatch):
    m,target,out,source,trace=fixture(tmp_path,monkeypatch);original=source.read_bytes()
    m.prepare(out);m.install(target,out);source.write_bytes(original+b' ')
    m.restore(target,out)
    assert (target/m.MODINFO).read_bytes()==original


def test_restore_delete_failure_rolls_back_modinfo(tmp_path,monkeypatch):
    m,target,out,source,trace=fixture(tmp_path,monkeypatch);m.prepare(out);m.install(target,out)
    probe=target/m.RELATIVE;original_unlink=Path.unlink
    def fail(path,*args,**kwargs):
        if path==probe:raise OSError('injected unlink failure')
        return original_unlink(path,*args,**kwargs)
    monkeypatch.setattr(Path,'unlink',fail)
    with pytest.raises(OSError,match='injected'):m.restore(target,out)
    assert (target/m.MODINFO).read_bytes()==(out/m.MODINFO).read_bytes() and probe.exists()

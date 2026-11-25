"""Exercise the passive voice-input diagnostic in an isolated Lua runtime."""
from pathlib import Path
import importlib.util
import json
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

from lupa import LuaRuntime


SOURCE = Path('tools/experiments/voice_input_probe.lua')


def runtime():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute('''
      output = {}; printed = 0; hidden = true; dealOpen = false; actionOpen = true;
      hoveredIndex = 0; selectionLookups = 0; removed = 0; gotExtended = false
      print = function(s) printed = printed + 1; output[printed] = s end
      local function event()
        local e = {}; e.handlers = {};
        e.Add = function(f) table.insert(e.handlers, f) end
        e.Remove = function(f)
          for i = #e.handlers, 1, -1 do
            if e.handlers[i] == f then table.remove(e.handlers, i); removed=removed+1 end
          end
        end
        return e
      end
      LuaEvents = {DiploScene_SceneOpened=event(), DiploScene_LeaderSelect=event(),
                   DiploScene_SceneClosed=event()}
      PlayerConfigurations = {
        [1]={GetLeaderTypeName=function() return 'LEADER_REMSELY_ALEXANDER_II' end},
        [2]={GetLeaderTypeName=function() return 'OTHER' end}
      }
      KeyEvents = {KeyUp=1, KeyDown=2}; Keys = {VK_ESCAPE=27}
      MouseEvents = {RButtonUp=3, LButtonUp=4}
      local deal = {IsHidden=function() return not dealOpen end}
      local action = {IsHidden=function() return not actionOpen end}
      local children = {}
      for i=1,3 do children[i]={HasMouseOver=function() return hoveredIndex == i end} end
      local stack = {GetChildren=function() return children end}
      ContextPtr = {
        SetHide=function(_,h) hidden=h end,
        SetInputHandler=function(_,fn,extended) inputHandler=fn;gotExtended=extended end,
        SetShutdown=function(_,fn) shutdown=fn end,
        LookUpControl=function(_,path)
          if path:find('DiplomacyDealView',1,true) then return deal end
          if path:find('ConversationSelectionStack',1,true) then
            selectionLookups=selectionLookups+1;return stack
          end
          if path:find('DiplomacyActionView',1,true) then return action end
        end
      }
      function fire(name,...) for _,f in ipairs(LuaEvents[name].handlers) do f(...) end end
      function input(kind, key)
        return inputHandler({GetMessageType=function() return kind end,
                             GetKey=function() return key end})
      end
    ''')
    lua.execute(SOURCE.read_text(encoding='utf-8'))
    return lua


def test_activation_is_limited_to_alexander_and_scene_lifecycle():
    lua = runtime()
    lua.execute('''
      assert(hidden and gotExtended and printed==0)
      fire('DiploScene_SceneOpened',2); assert(hidden and printed==0)
      fire('DiploScene_SceneOpened',1); assert(not hidden and printed==1)
      fire('DiploScene_LeaderSelect',2); assert(hidden and printed==2)
      assert(input(1,27)==false and printed==2)
      fire('DiploScene_LeaderSelect',1); assert(not hidden and printed==3)
      fire('DiploScene_SceneClosed'); assert(hidden and printed==4)
      assert(input(1,27)==false and printed==4)
      shutdown(); assert(removed==3)
    ''')


def test_input_events_pass_through_and_record_only_relevant_actions():
    lua = runtime()
    lua.execute('''
      fire('DiploScene_SceneOpened',1)
      assert(input(2,27)==false and input(1,13)==false and printed==1)
      assert(input(1,27)==false and output[2]:find('input=escape',1,true))
      assert(input(3,0)==false and output[3]:find('input=right_up',1,true))
      hoveredIndex=2
      assert(input(4,0)==false)
      assert(output[4]:find('surface=action selection=2',1,true))
    ''')


def test_deal_clicks_do_not_inspect_or_modify_conversation_buttons():
    lua = runtime()
    lua.execute('''
      fire('DiploScene_SceneOpened',1); dealOpen=true; hoveredIndex=2
      assert(input(4,0)==false)
      assert(output[2]:find('surface=deal selection=not_checked',1,true))
      assert(selectionLookups==0)
    ''')


def test_lookup_failures_are_safe_and_logging_is_bounded():
    lua = runtime()
    lua.execute('''
      fire('DiploScene_SceneOpened',1)
      ContextPtr.LookUpControl=function() error('missing control') end
      assert(input(4,0)==false)
      assert(output[2]:find('surface=unknown selection=unknown',1,true))
      for i=1,100 do assert(input(1,27)==false) end
      assert(printed==32)
    ''')


def test_stage_preserves_existing_religion_probe_and_never_edits_base(tmp_path):
    spec = importlib.util.spec_from_file_location(
        'voice_input_stage', 'tools/experiments/prepare_voice_input_probe.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    base = tmp_path / 'installed.modinfo'
    original = b'''<Mod><InGameActions><AddGameplayScripts id="religion">
      <File>Lua/ExistingReligionProbe.lua</File></AddGameplayScripts></InGameActions>
      <Files><File>Lua/ExistingReligionProbe.lua</File></Files></Mod>'''
    base.write_bytes(original)
    out = tmp_path / 'staged'
    result = module.prepare(base, out)
    assert base.read_bytes() == original and not result['installed']
    root = ET.parse(out / 'RemselysAlexanderII.modinfo')
    assert root.find('./InGameActions/AddGameplayScripts/File').text == 'Lua/ExistingReligionProbe.lua'
    assert root.find('./InGameActions/AddUserInterfaces/File').text == module.XML
    assert {x.text for x in root.findall('./Files/File')} == {
        'Lua/ExistingReligionProbe.lua', module.XML, module.LUA}
    assert (out / module.XML).is_file() and (out / module.LUA).is_file()
    assert module.prepare(base, out) == result  # identical repeat is safe
    (out / module.LUA).write_text('different experiment', encoding='utf-8')
    with pytest.raises(FileExistsError):
        module.prepare(base, out)
    assert base.read_bytes() == original


def staging(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        'voice_input_stage_install', 'tools/experiments/prepare_voice_input_probe.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'game_running', lambda: False)
    target = tmp_path / 'installed'
    target.mkdir()
    info = target / module.MODINFO
    original = b'''<Mod><InGameActions><AddGameplayScripts id="religion">
      <File>Lua/ExistingReligionProbe.lua</File></AddGameplayScripts></InGameActions>
      <Files><File>Lua/ExistingReligionProbe.lua</File></Files></Mod>'''
    info.write_bytes(original)
    out = tmp_path / 'staged'
    module.prepare(info, out)
    return module, target, out, original


def test_install_and_restore_exact_original_with_religion(tmp_path, monkeypatch):
    m, target, out, original = staging(tmp_path, monkeypatch)
    m.install(target, out)
    info = target / m.MODINFO
    assert info.read_bytes() == (out / m.MODINFO).read_bytes()
    assert (target / m.XML).read_bytes() == (out / m.XML).read_bytes()
    assert (target / m.LUA).read_bytes() == (out / m.LUA).read_bytes()
    with pytest.raises(RuntimeError):
        m.install(target, out)
    m.restore(target, out)
    assert info.read_bytes() == original
    assert not (target / m.XML).exists() and not (target / m.LUA).exists()
    assert b'ExistingReligionProbe' in info.read_bytes()


def test_game_running_and_drift_prevent_all_changes(tmp_path, monkeypatch):
    m, target, out, original = staging(tmp_path, monkeypatch)
    monkeypatch.setattr(m, 'game_running', lambda: True)
    with pytest.raises(RuntimeError, match='Close Civilization'):
        m.install(target, out)
    assert (target / m.MODINFO).read_bytes() == original
    assert not (target / m.XML).exists() and not (target / m.LUA).exists()
    monkeypatch.setattr(m, 'game_running', lambda: False)
    (target / m.MODINFO).write_bytes(b'<changed/>')
    with pytest.raises(RuntimeError, match='differs'):
        m.install(target, out)
    assert not (target / m.XML).exists() and not (target / m.LUA).exists()
    (target / m.MODINFO).write_bytes(original)
    m.install(target, out)
    (target / m.LUA).write_bytes(b'user changed file')
    with pytest.raises(RuntimeError, match='differs'):
        m.restore(target, out)
    assert (target / m.LUA).read_bytes() == b'user changed file'
    assert (target / m.MODINFO).read_bytes() == (out / m.MODINFO).read_bytes()


def test_foreign_probe_files_and_modified_stage_are_refused(tmp_path, monkeypatch):
    m, target, out, original = staging(tmp_path, monkeypatch)
    path = target / m.XML
    path.parent.mkdir()
    path.write_bytes(b'user file')
    with pytest.raises(RuntimeError, match='already exists'):
        m.install(target, out)
    assert path.read_bytes() == b'user file'
    assert (target / m.MODINFO).read_bytes() == original
    path.unlink()
    (out / m.MODINFO).write_bytes(b'<Mod><InGameActions/><Files/></Mod>')
    with pytest.raises(ValueError, match='expected overlay'):
        m.install(target, out)
    assert (target / m.MODINFO).read_bytes() == original


def test_failed_atomic_install_rolls_back_new_files(tmp_path, monkeypatch):
    m, target, out, original = staging(tmp_path, monkeypatch)
    def fail(*args):
        raise OSError('injected rename error')
    monkeypatch.setattr(m.os, 'replace', fail)
    with pytest.raises(OSError, match='injected'):
        m.install(target, out)
    assert (target / m.MODINFO).read_bytes() == original
    assert not (target / m.XML).exists() and not (target / m.LUA).exists()
    assert not (target / m.TEMP).exists()


def test_failed_restore_rolls_back_to_complete_probe(tmp_path, monkeypatch):
    m, target, out, original = staging(tmp_path, monkeypatch)
    m.install(target, out)
    original_unlink = Path.unlink
    failed = False
    def fail_once(path, *args, **kwargs):
        nonlocal failed
        if path == target / m.LUA and not failed:
            failed = True
            raise OSError('injected unlink error')
        return original_unlink(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'unlink', fail_once)
    with pytest.raises(OSError, match='injected'):
        m.restore(target, out)
    assert (target / m.MODINFO).read_bytes() == (out / m.MODINFO).read_bytes()
    assert (target / m.XML).read_bytes() == (out / m.XML).read_bytes()
    assert (target / m.LUA).read_bytes() == (out / m.LUA).read_bytes()
    assert not (target / m.TEMP).exists()


def test_install_rollback_preserves_independently_changed_file(tmp_path, monkeypatch):
    m, target, out, original = staging(tmp_path, monkeypatch)
    calls = 0
    def close_check():
        nonlocal calls
        calls += 1
        if calls == 2:
            (target / m.XML).write_bytes(b'user changed file')
            raise RuntimeError('game started')
    monkeypatch.setattr(m, 'require_closed', close_check)
    with pytest.raises(RuntimeError, match='rollback preserved changed files'):
        m.install(target, out)
    assert (target / m.MODINFO).read_bytes() == original
    assert (target / m.XML).read_bytes() == b'user changed file'
    assert not (target / m.LUA).exists()


def test_cli_separate_out_preserves_earlier_stage_and_rejects_overwrite(tmp_path):
    first_base = tmp_path / 'first.modinfo'
    second_base = tmp_path / 'second.modinfo'
    first_base.write_text('<Mod><InGameActions/><Files/></Mod>', encoding='utf-8')
    second_base.write_text('<Mod><InGameActions><UpdateText id="new"/></InGameActions>'
                           '<Files/></Mod>', encoding='utf-8')
    first_out, second_out = tmp_path / 'first-stage', tmp_path / 'second-stage'
    script = str(Path('tools/experiments/prepare_voice_input_probe.py').resolve())
    def run(base, out):
        return subprocess.run([sys.executable, script, '--base', str(base), '--out', str(out)],
                              capture_output=True, text=True, encoding='utf-8')
    first = run(first_base, first_out)
    assert first.returncode == 0, first.stderr
    first_candidate = (first_out / 'RemselysAlexanderII.modinfo').read_bytes()
    assert json.loads(first.stdout)['staging_path'] == str(first_out.resolve())
    second = run(second_base, second_out)
    assert second.returncode == 0, second.stderr
    assert (second_out / 'RemselysAlexanderII.modinfo').read_bytes() != first_candidate
    assert (first_out / 'RemselysAlexanderII.modinfo').read_bytes() == first_candidate
    conflict = run(second_base, first_out)
    assert conflict.returncode != 0 and 'Staged file differs' in conflict.stderr
    assert (first_out / 'RemselysAlexanderII.modinfo').read_bytes() == first_candidate

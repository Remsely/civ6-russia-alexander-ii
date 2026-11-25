"""Check the generated full-voice routing without claiming in-game playback."""
import json
import sqlite3
from pathlib import Path

from lupa import LuaRuntime
from lxml import etree

from prepare_full_voice import tag_for

ROOT = Path(__file__).resolve().parents[1]


def test_manifest_scopes_each_route_to_our_leader():
    rows = json.loads((ROOT / 'art/voice/full-game-manifest.json').read_text(encoding='utf-8'))
    assert len(rows) == 137
    assert len({r['slot'] for r in rows}) == len({r['tag'] for r in rows}) == 137
    assert all(r['tag'] == tag_for(r) and 'REMSELY' in r['tag'] for r in rows)
    assert sum(r['kind'] == 'deal_ui' for r in rows) == 11
    assert sum(r['kind'] == 'reason' for r in rows) == 75


def test_literal_deal_response_clones_are_leader_only():
    db = sqlite3.connect(':memory:')
    with sqlite3.connect(ROOT / 'reference/game-db/DebugGameplay.sqlite') as disk:
        disk.backup(db)
    db.create_function('Make_Hash', 1, lambda value: 1)
    db.executescript((ROOT / 'mod/Data/FullVoice.sql').read_text(encoding='utf-8'))
    rows = db.execute("SELECT Leader, Mood, StatementText FROM DiplomacyStatements WHERE Type='MAKE_DEAL' AND SubType='HUMAN_REFUSE_DEAL' AND Initiator='AI' AND Leader IN ('ANY','LEADER_REMSELY_ALEXANDER_II')").fetchall()
    assert len(rows) == 6
    assert sum(r[0] == 'ANY' for r in rows) == 3
    assert sum(r[0] == 'LEADER_REMSELY_ALEXANDER_II' and r[2].endswith('_REMSELY_ALEXANDER_II') for r in rows) == 3


def test_reason_animation_allowlist_has_no_speech_triggers():
    scene = etree.parse(str(ROOT / 'mod/Assets/AlexanderII.ast'))
    allowed = {mood + '_' + action for mood in ('NEUTRAL', 'HAPPY', 'UNHAPPY') for action in ('POSITIVE', 'NEGATIVE')}
    found = set()
    for timeline in scene.findall('.//m_Timelines/Element'):
        name = timeline.find('m_Name').get('text')
        for family in allowed:
            if name in (family + '_A', family + '_B'):
                found.add(family)
                effects = [node.get('text') or '' for node in timeline.findall('.//m_FXName')]
                assert not any(fx.startswith(('Play_REMSELY_AlexanderII_', 'Play_RUSS_PA_', 'RUSS_PA_')) for fx in effects), name
    assert found == allowed


def test_scene_has_no_peter_voice_or_breath_events():
    scene = etree.parse(str(ROOT / 'mod/Assets/AlexanderII.ast'))
    effects = [node.get('text') or '' for node in scene.findall('.//m_FXName')]
    assert not [fx for fx in effects if fx.startswith(('RUSS_PA_', 'Play_RUSS_PA_'))]


def test_statement_reason_and_deal_handlers_route_separately():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute('''
        calls = {}
        function include() end
        function event()
            local e={handlers={}}; e.Add=function(f) table.insert(e.handlers,f) end; e.Remove=function() end; return e
        end
        Events=setmetatable({}, {__index=function(t,k) local e=event(); rawset(t,k,e); return e end})
        LuaEvents=setmetatable({}, {__index=function(t,k) local e=event(); rawset(t,k,e); return e end})
        UI={PlaySound=function(n) table.insert(calls,n) end, SetSoundSwitchValue=function() end}
        Game={GetLocalPlayer=function() return 0 end}
        PlayerConfigurations={[1]={GetLeaderTypeName=function() return 'LEADER_REMSELY_ALEXANDER_II' end}, [2]={GetLeaderTypeName=function() return 'LEADER_OTHER' end}}
        Players={}; DiplomacyMoodTypes={UNDEFINED=-1}; DealProposalAction={INSPECT=10,EQUALIZE=11}
        DiplomacyManager={GetKeyName=function(x) return x end, FindTextKey=function(x) return x end,
          FindReasonTextKey=function() return reasonKey end}
        DiplomacySupport_ExtractStatement=function() return {StatementText=currentText, ReasonText=currentReason, LeaderAnimation=currentAnimation} end
        ContextPtr={SetShutdown=function() end}
        REMSELY_FullVoice_statement={CUSTOM_STATEMENT='FULL_016'}
        REMSELY_FullVoice_reason={CUSTOM_REASON='FULL_082'}
        REMSELY_FullVoice_deal_ui={CUSTOM_DEAL='FULL_132'}
    ''')
    source = (ROOT / 'mod/UI/RemselysAlexanderII_Voice.lua').read_text(encoding='utf-8')
    lua.execute(source.split('-- ===========================================================================\n-- Dawn-of-man fallback')[0])
    lua.execute('''
        local statement=Events.DiplomacyStatement.handlers[1]
        local variant={StatementType='X',StatementSubType='Y',FromPlayer=1,FromPlayerMood=0}
        currentText='CUSTOM_STATEMENT'; statement(1,0,variant)
        assert(calls[2]=='Play_REMSELY_AlexanderII_FULL_016')
        currentText='EMPTY'; currentReason='template'; currentAnimation='NEUTRAL_POSITIVE'; reasonKey='CUSTOM_REASON'; statement(1,0,variant)
        assert(calls[4]=='Play_REMSELY_AlexanderII_FULL_082')
        -- A spoken KUDOS scene is never layered with the reason event.
        currentAnimation='KUDOS'; statement(1,0,variant); assert(#calls==4)
        currentAnimation='NEUTRAL_POSITIVE'
        reasonKey='UNSCOPED_REASON'; statement(1,0,variant); assert(#calls==4)
        LuaEvents.REMSELY_DealLine.handlers[1](1,'CUSTOM_DEAL')
        assert(calls[6]=='Play_REMSELY_AlexanderII_FULL_132')
        LuaEvents.REMSELY_DealLine.handlers[1](1,'CUSTOM_DEAL')
        assert(#calls==6, 'duplicate opening notification must not restart the same line')
        LuaEvents.REMSELY_DealLine.handlers[1](1,'')
        assert(calls[7]=='Stop_REMSELY_AlexanderII_Speech')
        LuaEvents.REMSELY_DealLine.handlers[1](2,'CUSTOM_DEAL'); assert(#calls==7)
    ''')

"""Exercise the real statement handler with minimal Civ UI event stubs."""
from pathlib import Path
import json
import re

from lupa import LuaRuntime


def test_every_recorded_noncinematic_line_has_the_correct_text_route():
    root = Path(__file__).parents[1]
    source = (root / 'mod/UI/RemselysAlexanderII_Voice.lua').read_text(encoding='utf-8')
    routes = dict(re.findall(
        r'LOC_DIPLO_([A-Z0-9_]+)_LEADER_REMSELY_ALEXANDER_II_ANY\s*=\s*"([A-Z0-9_]+)"', source))
    recordings = json.loads((root / 'art/voice/game-trial-manifest.json').read_text(encoding='utf-8'))
    for entry in recordings:
        key = entry['key']
        if key == 'DEFEAT_FROM_HUMAN':  # Cinematic switch, not an independent play event.
            continue
        assert routes.get(key) == key, key


def test_only_local_statements_interrupt_and_open_does_not_stop():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute('''
        calls = {}
        function include() end
        function event()
            local e = { handlers = {} }
            e.Add = function(f) table.insert(e.handlers, f) end
            e.Remove = function() end
            return e
        end
        Events = setmetatable({}, {__index=function(t,k) local e=event(); rawset(t,k,e); return e end})
        LuaEvents = setmetatable({}, {__index=function(t,k) local e=event(); rawset(t,k,e); return e end})
        UI = { PlaySound=function(name) table.insert(calls,name) end,
            SetSoundSwitchValue=function() end }
        Game = { GetLocalPlayer=function() return 0 end }
        PlayerConfigurations = { [1]={GetLeaderTypeName=function() return 'LEADER_REMSELY_ALEXANDER_II' end} }
        Players = {}
        DiplomacyMoodTypes = { UNDEFINED=-1 }
        DealProposalAction = { INSPECT=10, EQUALIZE=11 }
        DiplomacyManager = { GetKeyName=function(x) return x end,
            FindTextKey=function(x) return x end }
        currentText = 'LOC_DIPLO_DELEGATION_FROM_AI_LEADER_REMSELY_ALEXANDER_II_ANY'
        DiplomacySupport_ExtractStatement = function() return {StatementText=currentText} end
        ContextPtr = { SetShutdown=function() end }
    ''')
    source = (Path(__file__).parents[1] / 'mod/UI/RemselysAlexanderII_Voice.lua').read_text(encoding='utf-8')
    lua.execute(source.split('-- ===========================================================================\n-- Dawn-of-man fallback')[0])
    lua.execute('''
        statement = Events.DiplomacyStatement.handlers[1]
        variant = {StatementType='X', StatementSubType='Y', FromPlayer=1, FromPlayerMood=0, SessionID=42}
        statement(1, 0, variant)
        assert(calls[1] == 'Stop_REMSELY_AlexanderII_Speech')
        assert(calls[2] == 'Play_REMSELY_AlexanderII_DELEGATION_FROM_AI')
        statement(2, 3, variant)
        assert(#calls == 2)
        Events.ShowLeaderScreen.handlers[1]('LEADER_REMSELY_ALEXANDER_II')
        assert(#calls == 2)
        Events.UserRequestClose.handlers[1]()
        assert(calls[3] == 'Stop_REMSELY_AlexanderII_Speech')
        Events.HideLeaderScreen.handlers[1]()
        assert(calls[4] == 'Stop_REMSELY_AlexanderII_Speech')

        -- The first-meeting invitation closes the view automatically. The
        -- two close events must not stop the tail; explicit Escape still does.
        currentText = 'LOC_DIPLO_FIRST_MEET_VISIT_RECIPIENT_LEADER_REMSELY_ALEXANDER_II_ANY'
        statement(1, 0, variant)
        assert(calls[6] == 'Play_REMSELY_AlexanderII_FIRST_MEET_VISIT_RECIPIENT')
        Events.HideLeaderScreen.handlers[1]()
        LuaEvents.DiploScene_SceneClosed.handlers[1]()
        assert(#calls == 6)
        Events.UserRequestClose.handlers[1]()
        assert(calls[7] == 'Stop_REMSELY_AlexanderII_Speech')

        LuaEvents.DiploScene_SceneOpened.handlers[1](1)
        currentText = 'LOC_DIPLO_ACCEPT_MAKE_DEAL_FROM_AI_LEADER_REMSELY_ALEXANDER_II_ANY'
        variant.StatementType='MAKE_DEAL'
        statement(1, 0, variant)
        assert(calls[9] == 'Play_REMSELY_AlexanderII_ACCEPT_MAKE_DEAL_FROM_AI', 'speech begins with the response')
        Events.HideLeaderScreen.handlers[1]()
        LuaEvents.DiploScene_SceneClosed.handlers[1]()
        assert(calls[10] == 'Stop_REMSELY_AlexanderII_Speech')
        local baseline = #calls
        -- Background deal checks from other leaders or an unvoiced Alexander
        -- statement must not interrupt a line which is already playing.
        for i = 1, 1000 do statement(2, 0, variant) end
        currentText = 'LOC_DIPLO_MAKE_DEAL_AI_ACCEPT_DEAL_ANY_ANY'
        statement(1, 0, variant)
        statement(0, 1, variant)
        assert(#calls == baseline)

        -- Background evaluations must not interrupt audible diplomacy,
        -- regardless of which interface initiated them.
        currentText = 'LOC_DIPLO_ACCEPT_MAKE_DEAL_FROM_AI_LEADER_REMSELY_ALEXANDER_II_ANY'
        variant.RespondingToDealAction=DealProposalAction.INSPECT
        statement(1, 0, variant)
        variant.RespondingToDealAction=DealProposalAction.EQUALIZE
        statement(1, 0, variant)
        assert(#calls == baseline)
        variant.RespondingToDealAction=nil

        LuaEvents.DiploScene_SceneOpened.handlers[1](1)
        statement(1, 0, variant)
        assert(calls[baseline+2] == 'Play_REMSELY_AlexanderII_ACCEPT_MAKE_DEAL_FROM_AI')
        LuaEvents.DiploScene_SceneClosed.handlers[1]()
        LuaEvents.DiploScene_SceneOpened.handlers[1](1)
        local beforeVisible = #calls
        variant.RespondingToDealAction=DealProposalAction.INSPECT
        statement(1, 0, variant)
        assert(calls[beforeVisible+2] == 'Play_REMSELY_AlexanderII_ACCEPT_MAKE_DEAL_FROM_AI')
        LuaEvents.DiploScene_LeaderSelect.handlers[1](2)
        local beforeOther = #calls
        statement(1, 0, variant)
        assert(#calls == beforeOther, 'other leader selected; background trade must not play')
    ''')

"""Execute the InGame dawn-of-man driver from the voice UI context.

A pause-menu restart recreates the FrontEnd LoadScreen context from the vanilla
file, so the InGame driver in RemselysAlexanderII_Voice is what plays the era
narration and our Alexander speech there. The driver runs when the module loads,
so all scenario state is prepared before the module executes.
"""
from pathlib import Path

import pytest
from lupa import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'mod/UI/RemselysAlexanderII_Voice.lua'


def runtime(leader='LEADER_REMSELY_ALEXANDER_II', marker=None, is_resync=False, is_saved=False):
    lua = LuaRuntime(unpack_returned_tuples=True)
    g = lua.globals()
    g.moduleSource = MODULE.read_text(encoding='utf-8')
    g.currentLeader = leader
    g.dawnMarker = marker
    g.isResync = is_resync
    g.isSavedGame = is_saved
    lua.execute(r"""
        function Event()
            local e = {handlers={}}
            function e.Add(f) e.handlers[f] = true end
            function e.Remove(f) e.handlers[f] = nil end
            function e.Fire()
                local pending={}; for f in pairs(e.handlers) do pending[#pending+1]=f end
                for _,f in ipairs(pending) do f() end
            end
            return e
        end
        Events = {HideLeaderScreen=Event(), ShowLeaderScreen=Event(), DiplomacyStatement=Event(),
            UserRequestClose=Event(), LeaderAnimationComplete=Event(),
            GameCoreEventPublishComplete=Event(), LoadScreenClose=Event()}
        LuaEvents = {DiploScene_SceneOpened=Event(), DiploScene_SceneClosed=Event()}
        now=0; sounds={}; switchLog={}
        language='Russian'
        function print(...) end
        UI = {
            PlaySound=function(name) sounds[#sounds+1]=name end,
            GetElapsedTime=function() return now end,
            IsResyncLoadInProgress=function() return isResync end,
            GetEraSoundSwitchValue=function() return 1 end,
            SetSoundSwitchValue=function(group, value) switchLog[#switchLog+1]=group..'='..value end,
            GetSaveGameMetaData=function() return {{HostEra='ERA_RENAISSANCE'}} end
        }
        ContextPtr={}
        function ContextPtr:ClearUpdate() self.update=nil end
        function ContextPtr:SetUpdate(f) self.update=f end
        function ContextPtr:SetShutdown(f) self.shutdown=f end
        function advance(seconds) now=now+seconds; if ContextPtr.update then ContextPtr.update() end end
        function countSound(name) local n=0; for _,v in ipairs(sounds) do if v==name then n=n+1 end end; return n end
        Options={GetAppOption=function() return language end}
        GameConfiguration={GetStartEra=function() return 'ERA_ANCIENT' end,
            IsSavedGame=function() return isSavedGame end, IsHotseat=function() return false end,
            IsWorldBuilderEditor=function() return false end, IsAnyMultiplayer=function() return false end,
            GetValue=function(_, key) return dawnMarker end,
            SetValue=function(_, key, value) dawnMarker=value end}
        Network={GetLocalPlayerID=function() return 0 end}
        MapConfiguration={GetMaxMajorPlayers=function() return 2 end}
        SlotStatus={SS_TAKEN=1}
        PlayerConfigurations={[0]={GetLeaderTypeName=function() return currentLeader end,
            GetSlotStatus=function() return 1 end}}
        GameInfo={Eras={ERA_ANCIENT={EraType='ERA_ANCIENT',Hash=1},
                        ERA_RENAISSANCE={EraType='ERA_RENAISSANCE',Hash=2}},
            LoadingInfo={LEADER_REMSELY_ALEXANDER_II={PlayDawnOfManAudio=false}}}
        Players={}
        Game={GetLocalPlayer=function() return 0 end}
        Challenges={IsChallengeActive=function() return false end}
        DB={MakeHash=function(name) return #name end}
        DiplomacySupport_ParseStatement=function() return {} end
        DiplomacySupport_ParseStatementSelection=function() return {} end
        DiplomacyManager={GetKeyName=function() return nil end}
        DiplomacyMoodTypes={UNDEFINED=0}
        function include(name)
            assert(name == 'DiplomacyStatementSupport' or name == 'RemselysAlexanderII_LoadingEraDurations',
                'unexpected include '..name)
            if name == 'RemselysAlexanderII_LoadingEraDurations' then
                REMSELY_LoadingEraSeconds={Russian={ERA_ANCIENT=15, ERA_RENAISSANCE=26},
                    ['English(US)']={ERA_ANCIENT=19, ERA_RENAISSANCE=26}}
            end
        end
    """)
    lua.execute('assert(load(moduleSource))()')
    return lua


def switch_log(g):
    return list(g.switchLog.values())


def test_unhandled_game_drives_dawn_sequence():
    # The restart case: no load screen extension ran, no marker - the InGame
    # context posts the full sequence itself. The mute is immediate (this context
    # gets no per-frame update) and the narration is polled from engine events.
    g = runtime().globals()
    assert g.countSound('STOP_SPEECH_DAWNOFMAN') == 1      # kill any vanilla post first
    assert g.countSound('Play_DawnOfMan_Speech') == 1       # era posted from InGame
    assert 'Leader_Screen_Civilization=25' in switch_log(g)  # mute applied at once
    assert g.countSound('Play_REMSELY_AlexanderII_LOADING_RU') == 0
    g.now = 18.2  # past the era duration + 3s margin (15s from the post), no update ticked
    g.Events.GameCoreEventPublishComplete.Fire()
    assert g.countSound('Play_REMSELY_AlexanderII_LOADING_RU') == 1
    assert g.countSound('STOP_SPEECH_DAWNOFMAN') == 2
    assert g.ContextPtr.update is None


def test_narration_waits_for_era_on_early_publish():
    # A publish before the era narration has ended must not cut the era short.
    g = runtime().globals()
    g.now = 5.0
    g.Events.GameCoreEventPublishComplete.Fire()
    assert g.countSound('Play_REMSELY_AlexanderII_LOADING_RU') == 0
    assert g.countSound('STOP_SPEECH_DAWNOFMAN') == 1  # only the initial kill
    g.now = 18.2
    g.Events.GameCoreEventPublishComplete.Fire()
    assert g.countSound('Play_REMSELY_AlexanderII_LOADING_RU') == 1


def test_begin_button_cancels_pending_narration():
    # "Begin" pressed while the era narration is still playing: the intro is
    # skipped entirely - no orphan Alexander speech afterwards.
    g = runtime().globals()
    g.now = 8.0  # the era (15s) is still playing
    g.Events.LoadScreenClose.Fire()
    assert g.countSound('Play_REMSELY_AlexanderII_LOADING_RU') == 0
    g.now = 40.0
    g.Events.GameCoreEventPublishComplete.Fire()
    g.ContextPtr.update and g.ContextPtr.update()
    assert g.countSound('Play_REMSELY_AlexanderII_LOADING_RU') == 0
    assert g.countSound('STOP_SPEECH_DAWNOFMAN') == 2  # initial kill + the cancel


def test_begin_button_stops_playing_narration():
    # "Begin" pressed after our speech has started stops it, like on normal loads.
    g = runtime().globals()
    g.now = 18.2
    g.Events.GameCoreEventPublishComplete.Fire()
    assert g.countSound('Play_REMSELY_AlexanderII_LOADING_RU') == 1
    g.Events.LoadScreenClose.Fire()
    assert g.countSound('Stop_REMSELY_AlexanderII_Loading') == 1
    assert g.countSound('Play_REMSELY_AlexanderII_LOADING_RU') == 1  # not replayed


def test_handled_game_skips_dawn():
    # Normal load: the load screen extension played everything and left the marker.
    g = runtime(marker=True).globals()
    assert g.countSound('Play_DawnOfMan_Speech') == 0
    assert g.countSound('STOP_SPEECH_DAWNOFMAN') == 0
    assert g.ContextPtr.update is None


def test_genuine_peter_game_is_untouched():
    g = runtime(leader='LEADER_PETER_GREAT').globals()
    assert g.countSound('Play_DawnOfMan_Speech') == 0
    assert g.countSound('STOP_SPEECH_DAWNOFMAN') == 0


def test_resync_load_skips_dawn():
    g = runtime(is_resync=True).globals()
    assert g.countSound('Play_DawnOfMan_Speech') == 0


def test_saved_game_uses_host_era_duration():
    g = runtime(is_saved=True).globals()
    assert g.countSound('Play_DawnOfMan_Speech') == 1
    g.advance(0.8)
    g.advance(29.0)  # Renaissance duration 26s from the post plus the 3s margin
    assert g.countSound('Play_REMSELY_AlexanderII_LOADING_RU') == 1

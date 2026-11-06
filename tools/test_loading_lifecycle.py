"""Execute the real Lua extension across repeated native screen loads.

Test both reused contexts with cached includes and completely fresh Lua
contexts where custom module imports cannot be resolved.
"""
from pathlib import Path

import pytest
from lupa import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'mod/UI/RemselysAlexanderII_LoadScreen.lua'
NATIVE = ROOT / 'mod/UI/LoadScreen.lua'


def runtime(module_source=None, tail=None):
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.globals().moduleSource = module_source or MODULE.read_text(encoding='utf-8')
    lua.execute(r"""
        function Event()
            local e = {handlers={}}
            function e.Add(f) e.handlers[f] = true end
            function e.Remove(f) e.handlers[f] = nil end
            function e.Fire()
                local pending={}; for f in pairs(e.handlers) do pending[#pending+1]=f end
                for _,f in ipairs(pending) do f() end
            end
            function e.Count() local n=0; for _ in pairs(e.handlers) do n=n+1 end; return n end
            return e
        end
        Events = {LoadScreenContentReady=Event(), LoadScreenClose=Event()}
        now=0; sounds={}; currentLeader='LEADER_REMSELY_ALEXANDER_II'; currentCiv='CIVILIZATION_RUSSIA'
        language='English(US)'; switchLog={}; resyncFlag=false
        function print(...) end
        UI = {
            PlaySound=function(name) sounds[#sounds+1]=name end,
            GetElapsedTime=function() return now end,
            IsResyncLoadInProgress=function() return resyncFlag end,
            GetEraSoundSwitchValue=function() return 1 end,
            GetCivilizationSoundSwitchValueByLeader=function() return 1816587302 end,
            SetSoundSwitchValue=function(group, value) switchLog[#switchLog+1]=group..'='..value end
        }
        ContextPtr={}
        function ContextPtr:ClearUpdate() self.update=nil end
        function ContextPtr:SetUpdate(f) self.update=f end
        function ContextPtr:SetShowHandler(f) self.show=f end
        function ContextPtr:SetHideHandler(f) self.hide=f end
        function advance(seconds) now=now+seconds; if ContextPtr.update then ContextPtr.update() end end
        function countSound(name) local n=0; for _,v in ipairs(sounds) do if v==name then n=n+1 end end; return n end
        Options={GetAppOption=function() return language end}
        configValues={}
        GameConfiguration={GetStartEra=function() return 'ERA_ANCIENT' end,
            IsSavedGame=function() return false end, IsHotseat=function() return false end,
            IsWorldBuilderEditor=function() return false end, IsAnyMultiplayer=function() return false end,
            GetValue=function(_, key) return configValues[key] end,
            SetValue=function(_, key, value) configValues[key]=value end}
        Network={GetLocalPlayerID=function() return 0 end}
        PlayerConfigurations={[0]={GetLeaderTypeName=function() return currentLeader end,
            GetLeaderTypeID=function() return 1 end,
            GetCivilizationTypeName=function() return currentCiv end}}
        GameInfo={Eras={ERA_ANCIENT={EraType='ERA_ANCIENT',Hash=1}},
            LoadingInfo={LEADER_REMSELY_ALEXANDER_II={PlayDawnOfManAudio=true}},
            Leaders={LEADER_PETER_GREAT={Index=22}}}
        Challenges={IsChallengeActive=function() return false end}
        DB={MakeHash=function(name) return #name end}
        local included={}
        function include(name)
            if included[name] then return end
            included[name]=true
            if name=='RemselysAlexanderII_LoadScreen' then assert(load(moduleSource))()
            elseif name=='RemselysAlexanderII_LoadingEraDurations' then
                REMSELY_LoadingEraSeconds={['English(US)']={ERA_ANCIENT=15},Russian={ERA_ANCIENT=16}}
            else error('unexpected include '..name) end
        end
        function reloadNative(resetEvents)
            if resetEvents then
                Events.LoadScreenContentReady=Event(); Events.LoadScreenClose=Event()
            end
            function OnShow() end
            function OnHide() end
            function OnLoadScreenContentReady()
                if currentLeader~='LEADER_REMSELY_ALEXANDER_II' then
                    UI.PlaySound('native_'..currentLeader)
                end
            end
            Events.LoadScreenContentReady.Add(OnLoadScreenContentReady)
            ContextPtr:SetShowHandler(OnShow); ContextPtr:SetHideHandler(OnHide)
        end
    """)
    lua.globals().nativeTail = tail or NATIVE.read_text(encoding='utf-8').rsplit('Initialize();', 1)[1]
    lua.execute('function loadScreen(resetEvents) reloadNative(resetEvents); assert(load(nativeTail))(); ContextPtr.show() end')
    return lua


@pytest.mark.parametrize('language,event', [('English(US)','Play_REMSELY_AlexanderII_LOADING_EN'),
                                           ('Russian','Play_REMSELY_AlexanderII_LOADING_RU')])
@pytest.mark.parametrize('reset_events', [False, True])
def test_repeated_games_keep_voice_and_do_not_accumulate_callbacks(language, event, reset_events):
    lua = runtime(); g = lua.globals(); g.language = language
    expected = 0
    for leader in ['LEADER_REMSELY_ALEXANDER_II', 'LEADER_REMSELY_ALEXANDER_II',
                   'LEADER_ABRAHAM_LINCOLN', 'LEADER_ABRAHAM_LINCOLN', 'LEADER_REMSELY_ALEXANDER_II']:
        g.currentLeader = leader; g.loadScreen(reset_events)
        g.Events.LoadScreenContentReady.Fire()
        # Reinitializing the same instance must not cancel its active queue.
        g.REMSELY_InitializeLoadingVoice()
        g.Events.LoadScreenContentReady.Fire()
        g.advance(g.REMSELY_LoadingEraSeconds[g.language]['ERA_ANCIENT'] + 1)
        if leader=='LEADER_REMSELY_ALEXANDER_II': expected += 1
        assert g.countSound(event) == expected
        assert g.Events.LoadScreenContentReady.Count() == 1
        assert g.Events.LoadScreenClose.Count() == 1
        g.Events.LoadScreenClose.Fire(); g.ContextPtr.hide(); g.advance(60)
        assert g.countSound(event) == expected
        assert g.ContextPtr.update is None
    assert g.countSound('native_LEADER_ABRAHAM_LINCOLN') == 4
    assert g.countSound('Stop_REMSELY_AlexanderII_Loading') == 3


def test_close_before_narration_cancels_queue_and_next_game_works():
    g=runtime().globals()
    g.loadScreen(False); g.Events.LoadScreenContentReady.Fire()
    g.Events.LoadScreenClose.Fire(); g.ContextPtr.hide(); g.advance(60)
    assert g.countSound('Play_REMSELY_AlexanderII_LOADING_EN') == 0
    g.loadScreen(False); g.Events.LoadScreenContentReady.Fire(); g.advance(g.REMSELY_LoadingEraSeconds[g.language]['ERA_ANCIENT'] + 1)
    assert g.countSound('Play_REMSELY_AlexanderII_LOADING_EN') == 1


@pytest.mark.parametrize('language,event', [('English(US)','Play_REMSELY_AlexanderII_LOADING_EN'),
                                           ('Russian','Play_REMSELY_AlexanderII_LOADING_RU')])
def test_each_load_in_fresh_lua_context_without_module_imports(language, event):
    for leader in ['LEADER_REMSELY_ALEXANDER_II', 'LEADER_REMSELY_ALEXANDER_II',
                   'LEADER_ABRAHAM_LINCOLN', 'LEADER_REMSELY_ALEXANDER_II']:
        g = runtime().globals()
        # No custom imports can be resolved in a later FrontEnd context.
        # The real generated native script must be self-contained after Initialize().
        g.include = lambda name: None
        g.language = language; g.currentLeader = leader
        g.loadScreen(True); g.Events.LoadScreenContentReady.Fire(); g.advance(120)
        assert g.countSound(event) == (1 if leader == 'LEADER_REMSELY_ALEXANDER_II' else 0)
        g.Events.LoadScreenClose.Fire(); g.ContextPtr.hide()
        assert g.ContextPtr.update is None


def switch_log(g):
    return list(g.switchLog.values())


def ancient_seconds(g):
    # The embedded native script carries the real era durations; read them from the
    # runtime instead of assuming the include mock's shorter table.
    return float(g.REMSELY_LoadingEraSeconds['English(US)']['ERA_ANCIENT'])


def test_pause_menu_restart_transient_peter_resolves_to_alexander():
    # Restarting from the pause menu leaves the local player on Russia's default leader
    # (Peter) when the loading content becomes ready; the vanilla pass posts the native
    # dawn event with Peter's voice. Our code mutes it and queues our narration as soon
    # as the chosen leader (Alexander) is re-applied.
    g = runtime().globals()
    g.currentLeader = 'LEADER_PETER_GREAT'
    g.loadScreen(True); era = ancient_seconds(g); g.Events.LoadScreenContentReady.Fire()
    assert g.countSound('native_LEADER_PETER_GREAT') == 1
    assert 'Leader_Screen_Civilization=25' in switch_log(g)  # mute value right away
    g.advance(1.0)
    g.currentLeader = 'LEADER_REMSELY_ALEXANDER_II'
    g.advance(0.2)   # flip detected: narration queued after the era intro
    assert g.countSound('Play_REMSELY_AlexanderII_LOADING_EN') == 0
    g.advance(era)   # past the era duration: native event stopped, our narration starts
    assert g.countSound('Play_REMSELY_AlexanderII_LOADING_EN') == 1
    assert g.countSound('STOP_SPEECH_DAWNOFMAN') == 1
    assert g.countSound('native_LEADER_PETER_GREAT') == 1


def test_genuine_peter_restart_restores_native_speech():
    # A real Peter game restarted the same way must keep its vanilla speech: the mute is
    # undone before the leader segment starts and nothing of ours ever plays.
    g = runtime().globals()
    g.currentLeader = 'LEADER_PETER_GREAT'
    g.loadScreen(True); era = ancient_seconds(g); g.Events.LoadScreenContentReady.Fire()
    g.advance(era + 5)  # leader stays Peter past the whole era narration
    assert g.countSound('Play_REMSELY_AlexanderII_LOADING_EN') == 0
    assert g.countSound('STOP_SPEECH_DAWNOFMAN') == 0
    assert 'Leader_Screen_Civilization=25' in switch_log(g)   # muted during the watch
    assert switch_log(g)[-1] == 'Leader_Screen_Civilization=6'  # restored to Russia
    assert g.ContextPtr.update is None


def test_restart_flip_in_final_window_remutes_and_queues():
    # The leader resolves between the restore deadline and the end of the era narration:
    # the mute is re-asserted and our narration still waits for the era intro to finish.
    g = runtime().globals()
    g.currentLeader = 'LEADER_PETER_GREAT'
    g.loadScreen(True); era = ancient_seconds(g); g.Events.LoadScreenContentReady.Fire()
    g.advance(era - 1.0)  # past decideBy (era - 1.5): vanilla speech restored, watch alive
    assert switch_log(g)[-1] == 'Leader_Screen_Civilization=6'
    g.currentLeader = 'LEADER_REMSELY_ALEXANDER_II'
    g.advance(0.2)    # flip before the era narration ends: re-mute + queue
    assert switch_log(g)[-1] == 'Leader_Screen_Civilization=25'
    assert g.countSound('Play_REMSELY_AlexanderII_LOADING_EN') == 0
    g.advance(2.0)
    assert g.countSound('Play_REMSELY_AlexanderII_LOADING_EN') == 1
    assert g.countSound('STOP_SPEECH_DAWNOFMAN') == 1


def test_close_during_restart_watch_cancels_everything():
    g = runtime().globals()
    g.currentLeader = 'LEADER_PETER_GREAT'
    g.loadScreen(True); g.Events.LoadScreenContentReady.Fire()
    g.Events.LoadScreenClose.Fire(); g.ContextPtr.hide()
    assert g.ContextPtr.update is None
    g.currentLeader = 'LEADER_REMSELY_ALEXANDER_II'
    g.advance(30)
    assert g.countSound('Play_REMSELY_AlexanderII_LOADING_EN') == 0


def test_resync_flag_flipping_after_show_still_takes_over_transient():
    # The pause-menu restart raises the resync flag after the screen is shown; the
    # vanilla dawn block posts with its show-time capture, so our pass must not bail on
    # a live check either - the transient watch has to start regardless.
    g = runtime().globals()
    g.currentLeader = 'LEADER_PETER_GREAT'
    g.loadScreen(True); era = ancient_seconds(g)
    g.resyncFlag = True  # flips between OnShow and content-ready
    g.Events.LoadScreenContentReady.Fire()
    assert 'Leader_Screen_Civilization=25' in switch_log(g)  # watch started despite flag
    g.currentLeader = 'LEADER_REMSELY_ALEXANDER_II'
    g.advance(0.2)
    g.advance(era + 1)
    assert g.countSound('Play_REMSELY_AlexanderII_LOADING_EN') == 1
    assert g.countSound('STOP_SPEECH_DAWNOFMAN') == 1


def test_resync_at_show_still_skips_takeover():
    # A genuine resync load is skipped exactly like the vanilla block does.
    g = runtime().globals()
    g.resyncFlag = True
    g.loadScreen(True)  # OnShow captures the flag while it is raised
    g.resyncFlag = False
    g.Events.LoadScreenContentReady.Fire()
    assert g.countSound('Play_DawnOfMan_Speech') == 0
    assert g.countSound('Play_REMSELY_AlexanderII_LOADING_EN') == 0
    assert g.ContextPtr.update is None

-- Stop only our branch on diplomacy transitions. Native Escape/RMB also stops
-- it through the shared vanilla LeaderSpeech parent.
include("DiplomacyStatementSupport");
local statementHandler = { ParseStatement = DiplomacySupport_ParseStatement,
    ParseStatementSelection = DiplomacySupport_ParseStatementSelection };
local observingAlexander = false;

local function StopVoice()
    UI.PlaySound("Stop_REMSELY_AlexanderII_Speech");
end

-- Defined with the dawn-of-man driver below; declared early because Shutdown uses it.
local StopLoadingDawn;

-- Additional trial recordings are selected by the same text key that the
-- diplomacy UI resolves. The six cinematic lines remain scene-triggered.
local trialTextEvents = {
    LOC_DIPLO_ACCEPT_DECLARE_FRIEND_FROM_AI_LEADER_REMSELY_ALEXANDER_II_ANY = "ACCEPT_DECLARE_FRIEND_FROM_AI",
    LOC_DIPLO_ACCEPT_DECLARE_FRIEND_FROM_HUMAN_LEADER_REMSELY_ALEXANDER_II_ANY = "ACCEPT_DECLARE_FRIEND_FROM_HUMAN",
    LOC_DIPLO_ACCEPT_DELEGATION_FROM_HUMAN_LEADER_REMSELY_ALEXANDER_II_ANY = "ACCEPT_DELEGATION_FROM_HUMAN",
    LOC_DIPLO_ACCEPT_MAKE_DEAL_FROM_AI_LEADER_REMSELY_ALEXANDER_II_ANY = "ACCEPT_MAKE_DEAL_FROM_AI",
    LOC_DIPLO_ACCEPT_OPEN_BORDERS_FROM_HUMAN_LEADER_REMSELY_ALEXANDER_II_ANY = "ACCEPT_OPEN_BORDERS_FROM_HUMAN",
    LOC_DIPLO_DECLARE_FRIEND_FROM_AI_LEADER_REMSELY_ALEXANDER_II_ANY = "DECLARE_FRIEND_FROM_AI",
    LOC_DIPLO_DELEGATION_FROM_AI_LEADER_REMSELY_ALEXANDER_II_ANY = "DELEGATION_FROM_AI",
    LOC_DIPLO_DENOUNCE_FROM_AI_LEADER_REMSELY_ALEXANDER_II_ANY = "DENOUNCE_FROM_AI",
    LOC_DIPLO_DENOUNCE_FROM_HUMAN_LEADER_REMSELY_ALEXANDER_II_ANY = "DENOUNCE_FROM_HUMAN",
    LOC_DIPLO_FIRST_MEET_NEAR_INITIATOR_POSITIVE_LEADER_REMSELY_ALEXANDER_II_ANY = "FIRST_MEET_NEAR_INITIATOR_POSITIVE",
    LOC_DIPLO_FIRST_MEET_NO_MANS_INFO_EXCHANGE_LEADER_REMSELY_ALEXANDER_II_ANY = "FIRST_MEET_NO_MANS_INFO_EXCHANGE",
    LOC_DIPLO_FIRST_MEET_VISIT_RECIPIENT_LEADER_REMSELY_ALEXANDER_II_ANY = "FIRST_MEET_VISIT_RECIPIENT",
    LOC_DIPLO_GREETING_LEADER_REMSELY_ALEXANDER_II_ANY = "GREETING",
    LOC_DIPLO_MAKE_ALLIANCE_FROM_AI_LEADER_REMSELY_ALEXANDER_II_ANY = "MAKE_ALLIANCE_FROM_AI",
    LOC_DIPLO_MAKE_PEACE_AI_ACCEPT_DEAL_LEADER_REMSELY_ALEXANDER_II_ANY = "MAKE_PEACE_AI_ACCEPT_DEAL",
    LOC_DIPLO_MAKE_PEACE_AI_REFUSE_DEAL_LEADER_REMSELY_ALEXANDER_II_ANY = "MAKE_PEACE_AI_REFUSE_DEAL",
    LOC_DIPLO_MAKE_PEACE_FROM_AI_LEADER_REMSELY_ALEXANDER_II_ANY = "MAKE_PEACE_FROM_AI",
    LOC_DIPLO_OPEN_BORDERS_FROM_AI_LEADER_REMSELY_ALEXANDER_II_ANY = "OPEN_BORDERS_FROM_AI",
    LOC_DIPLO_REJECT_DECLARE_FRIEND_FROM_AI_LEADER_REMSELY_ALEXANDER_II_ANY = "REJECT_DECLARE_FRIEND_FROM_AI",
    LOC_DIPLO_REJECT_DECLARE_FRIEND_FROM_HUMAN_LEADER_REMSELY_ALEXANDER_II_ANY = "REJECT_DECLARE_FRIEND_FROM_HUMAN",
    LOC_DIPLO_REJECT_DELEGATION_FROM_HUMAN_LEADER_REMSELY_ALEXANDER_II_ANY = "REJECT_DELEGATION_FROM_HUMAN",
    LOC_DIPLO_REJECT_MAKE_DEAL_FROM_AI_LEADER_REMSELY_ALEXANDER_II_ANY = "REJECT_MAKE_DEAL_FROM_AI",
    LOC_DIPLO_REJECT_OPEN_BORDERS_FROM_HUMAN_LEADER_REMSELY_ALEXANDER_II_ANY = "REJECT_OPEN_BORDERS_FROM_HUMAN",
    LOC_DIPLO_WARNING_TOO_MANY_TROOPS_NEAR_ME_LEADER_REMSELY_ALEXANDER_II_ANY = "WARNING_TOO_MANY_TROOPS_NEAR_ME",
};
-- Set before the asynchronous cinematic trigger, never play a second UI sound.
local defeatTextSwitches = {
    LOC_DIPLO_DEFEAT_FROM_AI_LEADER_REMSELY_ALEXANDER_II_ANY = "FROM_AI",
    LOC_DIPLO_DEFEAT_FROM_HUMAN_LEADER_REMSELY_ALEXANDER_II_ANY = "FROM_HUMAN",
};
local function SetDefeatVariant(value)
    UI.SetSoundSwitchValue("REMSELY_AlexanderII_DefeatVariant", value);
end
local function OnSceneOpened(playerID)
    local config = PlayerConfigurations[playerID];
    observingAlexander = config ~= nil and config:GetLeaderTypeName() == "LEADER_REMSELY_ALEXANDER_II";
    if observingAlexander then
        print("REMSELY voice: Alexander scene opened");
    end
end

local function OnAnimationComplete(name)
    if observingAlexander then
        print("REMSELY voice: animation complete " .. tostring(name));
    end
end

local function OnStatement(fromPlayer, toPlayer, variants)
    StopVoice();
    local config = PlayerConfigurations[fromPlayer];
    if config == nil or config:GetLeaderTypeName() ~= "LEADER_REMSELY_ALEXANDER_II" or variants == nil then return; end
    if toPlayer ~= Game.GetLocalPlayer() then return; end
    SetDefeatVariant("FROM_AI");
    local kind = DiplomacyManager.GetKeyName(variants.StatementType);
    local subtype = DiplomacyManager.GetKeyName(variants.StatementSubType) or "NONE";
    if kind == nil then return; end
    -- Match DiplomacyActionView.GetStatementMood, including reaction-time mood.
    local speaker = variants.FromPlayer or fromPlayer;
    local mood = variants.FromPlayerMood;
    if mood == DiplomacyMoodTypes.UNDEFINED then
        mood = DiplomacySupport_GetPlayerMood(Players[speaker], toPlayer);
    end
    local parsed = DiplomacySupport_ExtractStatement(statementHandler, kind, subtype,
        speaker, mood, variants.Initiator);
    if parsed.StatementText ~= nil then
        local textKey = DiplomacyManager.FindTextKey(parsed.StatementText, speaker, variants.FromMood, toPlayer);
        local defeatVariant = defeatTextSwitches[textKey];
        if defeatVariant ~= nil then
            SetDefeatVariant(defeatVariant);
            print("REMSELY voice: defeat variant " .. defeatVariant);
            return;
        end
        local slot = trialTextEvents[textKey];
        if slot ~= nil then
            UI.PlaySound("Play_REMSELY_AlexanderII_" .. slot);
            print("REMSELY voice: trial statement " .. slot);
        end
    end
end

local function OnSceneClosed()
    StopVoice();
    observingAlexander = false;
end

local function Shutdown()
    StopVoice();
    StopLoadingDawn();
    Events.HideLeaderScreen.Remove(StopVoice);
    Events.ShowLeaderScreen.Remove(StopVoice);
    Events.DiplomacyStatement.Remove(OnStatement);
    Events.UserRequestClose.Remove(StopVoice);
    Events.LeaderAnimationComplete.Remove(OnAnimationComplete);
    LuaEvents.DiploScene_SceneOpened.Remove(OnSceneOpened);
    LuaEvents.DiploScene_SceneClosed.Remove(OnSceneClosed);
end

Events.HideLeaderScreen.Add(StopVoice);
Events.ShowLeaderScreen.Add(StopVoice);
Events.DiplomacyStatement.Add(OnStatement);
Events.UserRequestClose.Add(StopVoice);
Events.LeaderAnimationComplete.Add(OnAnimationComplete);
LuaEvents.DiploScene_SceneOpened.Add(OnSceneOpened);
LuaEvents.DiploScene_SceneClosed.Add(OnSceneClosed);
ContextPtr:SetShutdown(Shutdown);
print("REMSELY Alexander II: voice prototype UI loaded");

-- ===========================================================================
-- Dawn-of-man fallback. The loading screen is imported in FrontEnd and InGame;
-- when it posts the narration it sets a GameConfiguration marker. If the marker
-- is absent, this InGame context posts the era and queues Alexander's speech.
-- It may initialize late and its duration-based timing is approximate.
-- ContextPtr:SetUpdate may not tick in this hidden context, so engine events poll it.
-- ===========================================================================
local dawnNarrationDeadline = nil;
local dawnNarrationStarted = false;
local OnDawnTick;
local OnDawnCancel;

local function DetachDawnTick()
    Events.GameCoreEventPublishComplete.Remove(OnDawnTick);
    ContextPtr:ClearUpdate();
end

function StopLoadingDawn()
    dawnNarrationDeadline = nil;
    DetachDawnTick();
    Events.LoadScreenClose.Remove(OnDawnCancel);
    if dawnNarrationStarted then
        dawnNarrationStarted = false;
        UI.PlaySound("Stop_REMSELY_AlexanderII_Loading");
    end
    UI.PlaySound("STOP_SPEECH_DAWNOFMAN");
end

-- The player pressed "begin" on the loading screen: the vanilla handler already
-- stops the era event; we cancel a pending narration and stop a playing one, the
-- same way the load screen extension behaves on normal loads.
OnDawnCancel = function()
    if dawnNarrationDeadline == nil and not dawnNarrationStarted then return; end
    print("REMSELY voice: InGame dawn cancelled at load screen close");
    dawnNarrationDeadline = nil;
    DetachDawnTick();
    Events.LoadScreenClose.Remove(OnDawnCancel);
    if dawnNarrationStarted then
        dawnNarrationStarted = false;
        UI.PlaySound("Stop_REMSELY_AlexanderII_Loading");
    end
    UI.PlaySound("STOP_SPEECH_DAWNOFMAN");
end

local function FinishDawnNarration()
    local now = UI.GetElapsedTime();
    dawnNarrationDeadline = nil;
    -- Detach only the deadline polling: the cancel handler must stay armed while
    -- our speech is playing, so "begin" can still stop it.
    DetachDawnTick();
    dawnNarrationStarted = true;
    -- The era narration has ended by now; this can only cut the muted Peter
    -- segment if it survived, never the era narration.
    UI.PlaySound("STOP_SPEECH_DAWNOFMAN");
    local language = Options.GetAppOption("Language", "AudioLanguage") or "";
    if string.sub(language, 1, 7) == "English" then
        UI.PlaySound("Play_REMSELY_AlexanderII_LOADING_EN");
    else
        UI.PlaySound("Play_REMSELY_AlexanderII_LOADING_RU");
    end
    print("REMSELY voice: InGame dawn started our narration after era intro (clock " .. tostring(now) .. ")");
end

OnDawnTick = function()
    if dawnNarrationDeadline == nil then
        ContextPtr:ClearUpdate();
        return;
    end
    if UI.GetElapsedTime() >= dawnNarrationDeadline then
        FinishDawnNarration();
    end
end

local function DriveLoadingDawn()
    if REMSELY_InGameDawnDriven then return; end
    REMSELY_InGameDawnDriven = true;
    if UI.IsResyncLoadInProgress() or GameConfiguration:IsWorldBuilderEditor() then return; end
    if Challenges.IsChallengeActive() then return; end
    local ok, handled = pcall(GameConfiguration.GetValue, "REMSELY_LoadingVoiceHandled");
    if ok and handled == true then
        print("REMSELY voice: InGame dawn skipped (load screen handled this game)");
        return;
    end
    local playerID = Network.GetLocalPlayerID();
    if GameConfiguration.IsHotseat() then
        for id = 0, MapConfiguration.GetMaxMajorPlayers() - 1 do
            local p = PlayerConfigurations[id];
            if p ~= nil and p:GetSlotStatus() == SlotStatus.SS_TAKEN then playerID = id; break; end
        end
    end
    local player = PlayerConfigurations[playerID];
    if player == nil or player:GetLeaderTypeName() ~= "LEADER_REMSELY_ALEXANDER_II" then return; end
    include("RemselysAlexanderII_LoadingEraDurations");
    if REMSELY_LoadingEraSeconds == nil then
        print("REMSELY voice: InGame dawn skipped (era durations unavailable)");
        return;
    end
    local era = GameInfo.Eras[GameConfiguration.GetStartEra()];
    if GameConfiguration.IsSavedGame() then
        local metadata = UI.GetSaveGameMetaData();
        if metadata and #metadata == 1 then era = GameInfo.Eras[metadata[1].HostEra] or era; end
    end
    local info = GameInfo.LoadingInfo["LEADER_REMSELY_ALEXANDER_II"];
    if info and info.DawnOfManEraId then era = GameInfo.Eras[info.DawnOfManEraId] or era; end
    if era == nil then
        print("REMSELY voice: InGame dawn skipped (unknown era)");
        return;
    end
    local language = Options.GetAppOption("Language", "AudioLanguage");
    local times = REMSELY_LoadingEraSeconds[language] or REMSELY_LoadingEraSeconds["English(US)"];
    local seconds = times[era.EraType];
    if seconds == nil then
        local value = UI.GetEraSoundSwitchValue(era.Hash);
        for eraType, duration in pairs(times) do
            local candidate = GameInfo.Eras[eraType];
            if candidate and UI.GetEraSoundSwitchValue(candidate.Hash) == value then seconds = duration; break; end
        end
    end
    if seconds == nil then
        print("REMSELY voice: InGame dawn skipped (no measured duration for " .. tostring(era.EraType) .. ")");
        return;
    end
    -- Stop anything a vanilla load-screen context may have posted (a restart can
    -- briefly expose the default leader, making the vanilla block post with Peter),
    -- then run the full sequence ourselves. The leader segment reads its switch
    -- only when the era narration has ended, so the mute is applied right away.
    UI.PlaySound("STOP_SPEECH_DAWNOFMAN");
    local russiaValue = DB.MakeHash("Russia");
    UI.SetSoundSwitchValue("Leader_Screen_Civilization", DB.MakeHash("REMSELY_ALEXANDER_II_MUTE"));
    UI.SetSoundSwitchValue("Civilization", russiaValue);
    UI.SetSoundSwitchValue("Era_DawnOfMan", UI.GetEraSoundSwitchValue(era.Hash));
    UI.PlaySound("Play_DawnOfMan_Speech");
    print("REMSELY voice: InGame dawn driving " .. tostring(era.EraType)
        .. ", narration in " .. tostring(seconds + 3.0) .. "s (clock "
        .. tostring(UI.GetElapsedTime()) .. ")");
    -- The era post happens under heavy load (the InGame UI is still initializing),
    -- and its audible start lags the post by a second or two: with a 0.5s buffer our
    -- speech cut the tail of the era narration in game (4.11.2026). Give the era a
    -- wide margin; FinishDawnNarration stops whatever is left before our speech.
    dawnNarrationDeadline = UI.GetElapsedTime() + seconds + 3.0;
    -- Hidden control-less contexts get no per-frame update: poll the deadline from
    -- engine events (frequent during load and gameplay). The load screen close (the
    -- "begin" button) cancels the whole intro instead - pressing it must never leave
    -- our speech playing untethered.
    Events.GameCoreEventPublishComplete.Add(OnDawnTick);
    Events.LoadScreenClose.Add(OnDawnCancel);
    ContextPtr:SetUpdate(OnDawnTick);
end

DriveLoadingDawn();

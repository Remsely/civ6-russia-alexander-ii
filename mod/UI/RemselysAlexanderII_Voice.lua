-- Stop our speech branches on diplomacy transitions. Cinematic speech shares
-- vanilla LeaderSpeech and is reached by native Escape/RMB. Standalone lines
-- use a private parent and rely on our transition/close handlers; their exact
-- Escape/RMB behavior must be checked in game.
include("DiplomacyStatementSupport");
include("RemselysAlexanderII_FullVoice");
local fullStatementEvents = REMSELY_FullVoice_statement or {};
local fullReasonEvents = REMSELY_FullVoice_reason or {};
local fullDealEvents = REMSELY_FullVoice_deal_ui or {};
-- Only these non-speaking vanilla animations may accompany reason speech.
-- KUDOS/WARNING and other speech cinematics fire their own audio in the AST.
local silentReasonAnimations = {
    NEUTRAL_POSITIVE = true, HAPPY_POSITIVE = true, UNHAPPY_POSITIVE = true,
    NEUTRAL_NEGATIVE = true, HAPPY_NEGATIVE = true, UNHAPPY_NEGATIVE = true,
};
local statementHandler = { ParseStatement = DiplomacySupport_ParseStatement,
    ParseStatementSelection = DiplomacySupport_ParseStatementSelection };
local observingAlexander = false;
local speechPosted = false;
-- Non-cinematic replies can themselves close the conversation automatically.
-- Let them finish across that transition, but still stop on explicit close,
-- the next local statement, or shutdown.
local finishAfterSceneClose = false;
local tailSceneClosed = false;
local currentDealVoice = false;

local function StopVoice(reason)
    finishAfterSceneClose = false;
    tailSceneClosed = false;
    if observingAlexander or speechPosted then
        print("REMSELY voice: stop " .. tostring(type(reason) == "string" and reason or "event"));
    end
    speechPosted = false;
    currentDealVoice = false;
    UI.PlaySound("Stop_REMSELY_AlexanderII_Speech");
end
local function OnHideLeaderScreen()
    if not finishAfterSceneClose then StopVoice("hide leader screen");
    elseif speechPosted then print("REMSELY voice: hide leader screen, standalone speech retained"); end
end
local function OnUserRequestClose() StopVoice("user request close"); end
local function OnShowLeaderScreen(leaderName)
    print("REMSELY voice: show leader screen " .. tostring(leaderName));
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
    if finishAfterSceneClose and tailSceneClosed then
        StopVoice("another scene opened");
    end
    local config = PlayerConfigurations[playerID];
    observingAlexander = config ~= nil and config:GetLeaderTypeName() == "LEADER_REMSELY_ALEXANDER_II";
    if observingAlexander then
        print("REMSELY voice: Alexander scene opened");
    end
end

local function OnLeaderSelected(playerID)
    local config = PlayerConfigurations[playerID];
    observingAlexander = config ~= nil and config:GetLeaderTypeName() == "LEADER_REMSELY_ALEXANDER_II";
end

local function OnAnimationComplete(name)
    if observingAlexander then
        print("REMSELY voice: animation complete " .. tostring(name));
    end
end

local function OnStatement(fromPlayer, toPlayer, variants)
    -- Ignore statements between other players: they must not interrupt speech
    -- currently playing for the local player.
    local localPlayer = Game.GetLocalPlayer();
    if fromPlayer ~= localPlayer and toPlayer ~= localPlayer then return; end
    local config = PlayerConfigurations[fromPlayer];
    if config == nil or config:GetLeaderTypeName() ~= "LEADER_REMSELY_ALEXANDER_II" or variants == nil then return; end
    if toPlayer ~= localPlayer then return; end
    local kind = DiplomacyManager.GetKeyName(variants.StatementType);
    local subtype = DiplomacyManager.GetKeyName(variants.StatementSubType) or "NONE";
    if kind == nil then return; end
    -- Vanilla distinguishes evaluations from final answers. Suppress these
    -- only while Alexander's scene is not displayed; visible evaluations keep
    -- the same text-selection route regardless of which UI initiated them.
    if not observingAlexander and kind == "MAKE_DEAL" and DealProposalAction ~= nil
        and (variants.RespondingToDealAction == DealProposalAction.INSPECT
            or variants.RespondingToDealAction == DealProposalAction.EQUALIZE) then
        return;
    end
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
            StopVoice("defeat statement");
            SetDefeatVariant(defeatVariant);
            print("REMSELY voice: defeat variant " .. defeatVariant);
            return;
        end
        local slot = trialTextEvents[textKey] or fullStatementEvents[textKey];
        -- Hidden agendas display their reason separately from StatementText.
        -- Only play a reason when the very same leader-scoped key was resolved
        -- for display, preserving subtitle/audio agreement.
        if slot == nil and parsed.ReasonText ~= nil and silentReasonAnimations[parsed.LeaderAnimation]
            and DiplomacyManager.FindReasonTextKey ~= nil then
            local reasonKey = DiplomacyManager.FindReasonTextKey(parsed.ReasonText, speaker,
                variants.AiReason, variants.AiModifier);
            if reasonKey ~= nil then slot = fullReasonEvents[reasonKey]; end
        end
        if slot ~= nil then
            -- A completed trade outside Alexander's visible diplomatic scene
            -- has no leader speech surface. This applies to any interface.
            if kind == "MAKE_DEAL" and not observingAlexander then
                print("REMSELY voice: skipped off-screen trade " .. slot);
                return;
            end
            StopVoice("new voiced statement");
            -- A trade response is displayed before CHOICE_EXIT closes its
            -- session. It must start with the statement, not after that exit.
            finishAfterSceneClose = kind ~= "MAKE_DEAL";
            UI.PlaySound("Play_REMSELY_AlexanderII_" .. slot);
            speechPosted = true;
            print("REMSELY voice: trial statement " .. slot);
        end
    end
end

-- The deal view hook sends its final displayed vanilla key, scoped to the
-- visible leader. Its custom subtitle and this audio lookup share one manifest.
local function OnDealLine(playerID, textKey)
    local config = PlayerConfigurations[playerID];
    if config == nil or config:GetLeaderTypeName() ~= "LEADER_REMSELY_ALEXANDER_II" then return; end
    local slot = fullDealEvents[textKey];
    if slot == nil then
        if currentDealVoice then StopVoice("deal text changed"); end
        return;
    end
    StopVoice("new deal line");
    UI.PlaySound("Play_REMSELY_AlexanderII_" .. slot);
    speechPosted = true;
    currentDealVoice = true;
    print("REMSELY voice: deal line " .. slot);
end

local function OnDealClosed(playerID)
    if currentDealVoice then StopVoice("deal view closed"); end
end

local function OnSceneClosed()
    if not finishAfterSceneClose then StopVoice("scene closed");
    else
        tailSceneClosed = true;
        if speechPosted then print("REMSELY voice: scene closed, standalone speech retained"); end
    end
    observingAlexander = false;
end

local function Shutdown()
    StopVoice();
    StopLoadingDawn();
    Events.HideLeaderScreen.Remove(OnHideLeaderScreen);
    Events.ShowLeaderScreen.Remove(OnShowLeaderScreen);
    Events.DiplomacyStatement.Remove(OnStatement);
    Events.UserRequestClose.Remove(OnUserRequestClose);
    Events.LeaderAnimationComplete.Remove(OnAnimationComplete);
    LuaEvents.DiploScene_SceneOpened.Remove(OnSceneOpened);
    LuaEvents.DiploScene_LeaderSelect.Remove(OnLeaderSelected);
    LuaEvents.DiploScene_SceneClosed.Remove(OnSceneClosed);
    LuaEvents.REMSELY_DealLine.Remove(OnDealLine);
    LuaEvents.REMSELY_DealClosed.Remove(OnDealClosed);
end

Events.HideLeaderScreen.Add(OnHideLeaderScreen);
Events.ShowLeaderScreen.Add(OnShowLeaderScreen);
Events.DiplomacyStatement.Add(OnStatement);
Events.UserRequestClose.Add(OnUserRequestClose);
Events.LeaderAnimationComplete.Add(OnAnimationComplete);
LuaEvents.DiploScene_SceneOpened.Add(OnSceneOpened);
LuaEvents.DiploScene_LeaderSelect.Add(OnLeaderSelected);
LuaEvents.DiploScene_SceneClosed.Add(OnSceneClosed);
LuaEvents.REMSELY_DealLine.Add(OnDealLine);
LuaEvents.REMSELY_DealClosed.Add(OnDealClosed);
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

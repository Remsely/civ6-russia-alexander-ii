-- Stop only our branch on diplomacy transitions. Native Escape/RMB also stops
-- it through the shared vanilla LeaderSpeech parent.
include("DiplomacyStatementSupport");
local statementHandler = { ParseStatement = DiplomacySupport_ParseStatement,
    ParseStatementSelection = DiplomacySupport_ParseStatementSelection };
local observingAlexander = false;

local function StopVoice()
    UI.PlaySound("Stop_REMSELY_AlexanderII_Speech");
end

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
local loadingStarted = false;

local function OnLoadingContentReady()
    if loadingStarted or UI.IsResyncLoadInProgress() or GameConfiguration:IsWorldBuilderEditor() then return; end
    local playerID = Network.GetLocalPlayerID();
    if GameConfiguration.IsHotseat() then
        for id = 0, MapConfiguration.GetMaxMajorPlayers() - 1 do
            local p = PlayerConfigurations[id];
            if p ~= nil and p:GetSlotStatus() == SlotStatus.SS_TAKEN then playerID = id; break; end
        end
    end
    local p = PlayerConfigurations[playerID];
    if p ~= nil and p:GetLeaderTypeName() == "LEADER_REMSELY_ALEXANDER_II" then
        loadingStarted = true;
        UI.PlaySound("Play_REMSELY_AlexanderII_LOADING_RU");
        print("REMSELY voice: loading narration started");
    end
end

local function OnLoadingClosed()
    if loadingStarted then StopVoice(); loadingStarted = false; end
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
    Events.LoadScreenContentReady.Remove(OnLoadingContentReady);
    Events.LoadScreenClose.Remove(OnLoadingClosed);
    Events.HideLeaderScreen.Remove(StopVoice);
    Events.ShowLeaderScreen.Remove(StopVoice);
    Events.DiplomacyStatement.Remove(OnStatement);
    Events.UserRequestClose.Remove(StopVoice);
    Events.LeaderAnimationComplete.Remove(OnAnimationComplete);
    LuaEvents.DiploScene_SceneOpened.Remove(OnSceneOpened);
    LuaEvents.DiploScene_SceneClosed.Remove(OnSceneClosed);
end

Events.LoadScreenContentReady.Add(OnLoadingContentReady);
Events.LoadScreenClose.Add(OnLoadingClosed);
Events.HideLeaderScreen.Add(StopVoice);
Events.ShowLeaderScreen.Add(StopVoice);
Events.DiplomacyStatement.Add(OnStatement);
Events.UserRequestClose.Add(StopVoice);
Events.LeaderAnimationComplete.Add(OnAnimationComplete);
LuaEvents.DiploScene_SceneOpened.Add(OnSceneOpened);
LuaEvents.DiploScene_SceneClosed.Add(OnSceneClosed);
ContextPtr:SetShutdown(Shutdown);
print("REMSELY Alexander II: voice prototype UI loaded");

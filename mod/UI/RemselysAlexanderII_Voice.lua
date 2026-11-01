-- Stop only our branch on diplomacy transitions. Native Escape/RMB also stops
-- it through the shared vanilla LeaderSpeech parent.
local observingAlexander = false;

local function StopVoice()
    UI.PlaySound("Stop_REMSELY_AlexanderII_Speech");
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

local function OnStatement(fromPlayer, toPlayer)
    StopVoice();
    local config = PlayerConfigurations[fromPlayer];
    if config ~= nil and config:GetLeaderTypeName() == "LEADER_REMSELY_ALEXANDER_II" then
        print("REMSELY voice: Alexander statement to " .. tostring(toPlayer));
    end
end

local function OnSceneClosed()
    StopVoice();
    observingAlexander = false;
end

local function Shutdown()
    StopVoice();
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

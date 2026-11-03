-- Runs inside the vanilla FrontEnd LoadScreen context after its initialization.
include("RemselysAlexanderII_LoadingEraDurations");
local baseContentReady = OnLoadScreenContentReady;
local baseShow = OnShow;
local baseHide = OnHide;
local narrationStarted = false;
local narrationDeadline = nil;

local function StopNarration()
    narrationDeadline = nil;
    ContextPtr:ClearUpdate();
    if narrationStarted then
        UI.PlaySound("Stop_REMSELY_AlexanderII_Loading");
        narrationStarted = false;
        print("REMSELY voice: loading narration stopped");
    end
end

function OnShow()
    StopNarration();
    baseShow();
end

function OnHide()
    StopNarration();
    baseHide();
end

local function GetEraDelay()
    local era = GameInfo.Eras[GameConfiguration.GetStartEra()];
    if GameConfiguration.IsSavedGame() then
        local metadata = UI.GetSaveGameMetaData();
        if metadata and #metadata == 1 then era = GameInfo.Eras[metadata[1].HostEra] or era; end
    end
    local info = GameInfo.LoadingInfo["LEADER_REMSELY_ALEXANDER_II"];
    if info then
        if info.PlayDawnOfManAudio == false then return 0; end
        if info.DawnOfManEraId then era = GameInfo.Eras[info.DawnOfManEraId] or era; end
    end
    if era == nil then return nil; end
    local language = Options.GetAppOption("Language", "AudioLanguage");
    local times = REMSELY_LoadingEraSeconds[language] or REMSELY_LoadingEraSeconds["English(US)"];
    local seconds = times[era.EraType];
    if seconds == nil then
        -- Ask the native mapping for later/custom eras instead of inventing a default.
        local value = UI.GetEraSoundSwitchValue(era.Hash);
        for eraType, duration in pairs(times) do
            local candidate = GameInfo.Eras[eraType];
            if candidate and UI.GetEraSoundSwitchValue(candidate.Hash) == value then seconds = duration; break; end
        end
    end
    return seconds;
end

local function OnNarrationUpdate()
    if narrationDeadline ~= nil and UI.GetElapsedTime() >= narrationDeadline then
        narrationDeadline = nil;
        ContextPtr:ClearUpdate();
        narrationStarted = true;
        UI.PlaySound("Play_REMSELY_AlexanderII_LOADING_RU");
        print("REMSELY voice: FrontEnd loading narration started after era intro");
    end
end

function OnLoadScreenContentReady()
    if narrationStarted or narrationDeadline ~= nil then return; end
    baseContentReady();
    if UI.IsResyncLoadInProgress() or GameConfiguration:IsWorldBuilderEditor() then return; end
    local playerID = Network.GetLocalPlayerID();
    if GameConfiguration.IsHotseat() then
        for id = 0, MapConfiguration.GetMaxMajorPlayers() - 1 do
            local p = PlayerConfigurations[id];
            if p ~= nil and p:GetSlotStatus() == SlotStatus.SS_TAKEN then playerID = id; break; end
        end
    end
    local player = PlayerConfigurations[playerID];
    if player == nil or player:GetLeaderTypeName() ~= "LEADER_REMSELY_ALEXANDER_II" then return; end
    if Challenges.IsChallengeActive() then return; end
    local seconds = GetEraDelay();
    if seconds == nil then
        print("REMSELY voice: unknown era narration duration; custom narration not queued");
        return;
    end
    -- Preserve Play_DawnOfMan_Speech. Only the native leader branch is muted
    -- in LoadScreen.lua; its era introduction plays in the selected audio language.
    narrationDeadline = UI.GetElapsedTime() + seconds + 0.5;
    ContextPtr:SetUpdate(OnNarrationUpdate);
    print("REMSELY voice: loading narration queued after era intro, delay " .. tostring(seconds + 0.5));
end

Events.LoadScreenContentReady.Remove(baseContentReady);
Events.LoadScreenContentReady.Add(OnLoadScreenContentReady);
Events.LoadScreenClose.Add(StopNarration);
ContextPtr:SetShowHandler(OnShow);
ContextPtr:SetHideHandler(OnHide);
print("REMSELY voice: FrontEnd loading hook ready");

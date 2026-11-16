-- Loaded by the vanilla DiplomacyDealView_ wildcard, in the deal view's own
-- context. Keep the original view and other leaders' localization untouched.
local previousSetLeaderDialog = SetLeaderDialog;
local previousUpdateDealStatus = UpdateDealStatus;
local previousOnShow = OnShow;
local previousOnHide = OnHide;
local previousOnShutdown = OnShutdown;

local ourDealKeys = {
    LOC_DIPLOMACY_DEAL_INVALID = true,
    LOC_DIPLO_DEAL_INTRO = true,
    LOC_DIPLO_DEAL_INTRO_AI = true,
    LOC_DIPLO_DEAL_LEADER_DEMAND = true,
    LOC_DIPLO_DEAL_LEADER_EQUALIZE_FAILED = true,
    LOC_DIPLO_DEAL_LEADER_EQUALIZE_SUCCEEDED = true,
    LOC_DIPLO_DEAL_LEADER_GIFT = true,
    LOC_DIPLO_DEAL_LEADER_GIFT_EQUALIZE_FAILED = true,
    LOC_DIPLO_DEAL_UNACCEPTABLE_DEAL = true,
    LOC_DIPLO_DEAL_UNFAIR = true,
    LOC_DIPLO_DEMAND_INTRO = true,
};

local pendingKey = nil;
local publishedKey = nil;
local publishedPlayer = nil;
local batchDepth = 0;

local function IsAlexander()
    local config = PlayerConfigurations[ms_OtherPlayerID];
    local player = Players[ms_OtherPlayerID];
    return config ~= nil and player ~= nil and not player:IsHuman()
        and config:GetLeaderTypeName() == "LEADER_REMSELY_ALEXANDER_II";
end

local function PublishDisplayedLine()
    if batchDepth ~= 0 or ContextPtr:IsHidden() or not IsAlexander() then return; end
    local key = pendingKey or "";
    if publishedPlayer == ms_OtherPlayerID and publishedKey == key then return; end
    publishedPlayer = ms_OtherPlayerID;
    publishedKey = key;
    LuaEvents.REMSELY_DealLine(ms_OtherPlayerID, key);
end

function SetLeaderDialog(leaderDialog, leaderEffect)
    if IsAlexander() and ourDealKeys[leaderDialog] then
        pendingKey = leaderDialog;
        return previousSetLeaderDialog(leaderDialog .. "_REMSELY_ALEXANDER_II", leaderEffect);
    end
    pendingKey = nil;
    return previousSetLeaderDialog(leaderDialog, leaderEffect);
end

-- The view can set a temporary string and overwrite it during one status
-- update. Publish only the final displayed string and suppress unchanged keys.
function UpdateDealStatus(...)
    batchDepth = batchDepth + 1;
    previousUpdateDealStatus(...);
    batchDepth = batchDepth - 1;
    PublishDisplayedLine();
end

function OnShow(...)
    pendingKey = nil;
    publishedKey = nil;
    publishedPlayer = nil;
    batchDepth = batchDepth + 1;
    previousOnShow(...);
    batchDepth = batchDepth - 1;
    PublishDisplayedLine();
end

function OnHide(...)
    if publishedPlayer ~= nil then LuaEvents.REMSELY_DealClosed(publishedPlayer); end
    pendingKey = nil;
    publishedKey = nil;
    publishedPlayer = nil;
    previousOnHide(...);
end

-- OnDealUpdated is registered by vanilla before wildcard includes. Usually
-- its final UpdateDealStatus publishes the line; if there is no incoming deal,
-- the already-localized szText can replace it without a status update. Observe
-- the same event after the vanilla handler to publish that change as well.
local function OnDealUpdatedComplete()
    PublishDisplayedLine();
end
LuaEvents.DiploPopup_DealUpdated.Add(OnDealUpdatedComplete);

function OnShutdown(...)
    LuaEvents.DiploPopup_DealUpdated.Remove(OnDealUpdatedComplete);
    previousOnShutdown(...);
end

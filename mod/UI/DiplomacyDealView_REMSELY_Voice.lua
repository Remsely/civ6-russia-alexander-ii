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
local subtitlePlayer = nil;
local subtitleText = nil;
local subtitleRightEdge = nil;

local function IsAlexander()
    local config = PlayerConfigurations[ms_OtherPlayerID];
    local player = Players[ms_OtherPlayerID];
    return config ~= nil and player ~= nil and not player:IsHuman()
        and config:GetLeaderTypeName() == "LEADER_REMSELY_ALEXANDER_II";
end

local function ClearSubtitle()
    if subtitlePlayer ~= nil then
        LuaEvents.REMSELY_DealSubtitle(subtitlePlayer, "", nil, false);
    end
    subtitlePlayer, subtitleText, subtitleRightEdge = nil, nil, nil;
end

-- Some UI layouts deliberately hide the native leader speech bubble. Supply
-- its actual resolved text to our optional non-interactive overlay only in
-- that case. Any missing or unusual controls disable the overlay safely.
local function PublishSubtitle()
    if ContextPtr:IsHidden() or not IsAlexander() then ClearSubtitle(); return; end
    local ok, text, rightEdge, hidden = pcall(function()
        local bubble = Controls.LeaderDialogFade:GetParent();
        local tradeArea = Controls.DealContentStack:GetParent();
        local x = tradeArea:GetScreenOffset();
        return Controls.LeaderDialog:GetText(), x + tradeArea:GetSizeX(), bubble:IsHidden();
    end);
    if not ok or hidden ~= true or type(text) ~= "string" or text == ""
        or type(rightEdge) ~= "number" then
        ClearSubtitle(); return;
    end
    if subtitlePlayer == ms_OtherPlayerID and subtitleText == text and subtitleRightEdge == rightEdge then return; end
    if subtitlePlayer ~= nil and subtitlePlayer ~= ms_OtherPlayerID then ClearSubtitle(); end
    subtitlePlayer, subtitleText, subtitleRightEdge = ms_OtherPlayerID, text, rightEdge;
    LuaEvents.REMSELY_DealSubtitle(subtitlePlayer, subtitleText, subtitleRightEdge, true);
end

local function PublishDisplayedLine(allowSpeech)
    if batchDepth ~= 0 then return; end
    PublishSubtitle();
    if ContextPtr:IsHidden() or not IsAlexander() then return; end
    local key = pendingKey or "";
    if publishedPlayer == ms_OtherPlayerID and publishedKey == key then return; end
    publishedPlayer = ms_OtherPlayerID;
    publishedKey = key;
    -- Status refreshes are automatic while the player edits quantities; they
    -- update subtitles but should not start a new spoken sentence per click.
    -- An empty notification stops a previously spoken line if its text changed.
    LuaEvents.REMSELY_DealLine(ms_OtherPlayerID, allowSpeech and key or "");
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
    PublishDisplayedLine(false);
end

function OnShow(...)
    pendingKey = nil;
    publishedKey = nil;
    publishedPlayer = nil;
    batchDepth = batchDepth + 1;
    previousOnShow(...);
    batchDepth = batchDepth - 1;
    PublishDisplayedLine(true);
end

function OnHide(...)
    if publishedPlayer ~= nil then LuaEvents.REMSELY_DealClosed(publishedPlayer); end
    ClearSubtitle();
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
    PublishDisplayedLine(false);
end
LuaEvents.DiploPopup_DealUpdated.Add(OnDealUpdatedComplete);

function OnShutdown(...)
    ClearSubtitle();
    LuaEvents.DiploPopup_DealUpdated.Remove(OnDealUpdatedComplete);
    previousOnShutdown(...);
end

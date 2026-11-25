-- Optional subtitle fallback for interfaces hiding the standard deal bubble.
-- The deal view supplies the already-localized text and its trade panel's
-- right edge. Do not cover that panel, consume input, or assume another mod.
local ENABLE_FALLBACK = true; -- Set false to disable the optional overlay.
local MARGIN = 16;
local MIN_WIDTH = 320;
local MAX_WIDTH = 560;
local MAX_TEXT_HEIGHT = 144;

local function Hide()
    pcall(function() Controls.SubtitleBox:SetHide(true); end);
    pcall(function() ContextPtr:SetHide(true); end);
end

local function IsFiniteNumber(value)
    return type(value) == "number" and value == value and value > -math.huge and value < math.huge;
end

local function OnDealSubtitle(playerID, text, rightEdge, hidden)
    if not ENABLE_FALLBACK or hidden ~= true or type(text) ~= "string" or text == "" or not IsFiniteNumber(rightEdge) then
        Hide(); return;
    end
    if type(playerID) ~= "number" or PlayerConfigurations == nil then Hide(); return; end
    local config = PlayerConfigurations[playerID];
    if config == nil or config:GetLeaderTypeName() ~= "LEADER_REMSELY_ALEXANDER_II" then
        Hide(); return;
    end

    local ok, width, height = pcall(function() return UIManager:GetScreenSizeVal(); end);
    if not ok or not IsFiniteNumber(width) or not IsFiniteNumber(height)
        or rightEdge < 0 or rightEdge >= width then
        Hide(); return;
    end
    local available = math.floor(width - rightEdge - 2 * MARGIN);
    if available < MIN_WIDTH then Hide(); return; end
    local boxWidth = math.min(MAX_WIDTH, available);
    local measured, textHeight = pcall(function()
        Controls.SubtitleText:SetWrapWidth(boxWidth - 2 * MARGIN);
        Controls.SubtitleText:SetText(text);
        return Controls.SubtitleText:GetSizeY();
    end);
    if not measured or not IsFiniteNumber(textHeight) or textHeight <= 0 or textHeight > MAX_TEXT_HEIGHT then
        Hide(); return;
    end
    local boxHeight = math.max(72, math.ceil(textHeight) + 2 * MARGIN);
    if height < boxHeight + 2 * MARGIN then Hide(); return; end
    local displayed = pcall(function()
        Controls.SubtitleBox:SetSizeVal(boxWidth, boxHeight);
        Controls.SubtitleBox:SetOffsetVal(rightEdge + MARGIN, height - boxHeight - MARGIN);
        Controls.SubtitleBox:SetHide(false);
        ContextPtr:SetHide(false);
    end);
    if not displayed then Hide(); end
end

local function Shutdown()
    LuaEvents.REMSELY_DealSubtitle.Remove(OnDealSubtitle);
end

LuaEvents.REMSELY_DealSubtitle.Add(OnDealSubtitle);
ContextPtr:SetShutdown(Shutdown);
Hide();

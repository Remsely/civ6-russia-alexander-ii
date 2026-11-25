-- Temporary input observation only. This context never consumes input and
-- never posts or stops sound. It is visible only for Alexander's scene.
local LIMIT = 32;
local emitted = 0;
local active = false;
local ACTION = "/InGame/Diplomacy/DiplomacyActionView";
local DEAL = "/InGame/Diplomacy/DiplomacyDealView";
local CHOICES = ACTION .. "/ConversationContainer/ConversationSelection_Alpha/ConversationSelection_Slide/ConversationSelectionGrid/ConversationSelectionStack";

local function Log(message)
    if emitted < LIMIT then
        emitted = emitted + 1;
        print("REMSELY_VOICE_INPUT_PROBE " .. tostring(emitted) .. " " .. message);
    end
end

local function Lookup(path)
    local ok, control = pcall(function() return ContextPtr:LookUpControl(path); end);
    if ok then return control; end
    return nil;
end

local function Visible(control)
    if control == nil then return nil; end
    local ok, hidden = pcall(function() return control:IsHidden(); end);
    if not ok then return nil; end
    return not hidden;
end

-- GetChildren and HasMouseOver are documented Forge UI methods. This reports
-- only a visual button index; the real selection key lives in another Lua
-- context's callback closure and is not inferred from the translated label.
local function InputSurface()
    local deal = Visible(Lookup(DEAL));
    if deal == true then return "deal", "not_checked"; end
    local action = Visible(Lookup(ACTION));
    if deal == nil or action == nil then return "unknown", "unknown"; end
    if not action then return "none", "not_checked"; end
    local stack = Lookup(CHOICES);
    if stack == nil then return "action", "unknown"; end
    local ok, children = pcall(function() return stack:GetChildren(); end);
    if not ok or type(children) ~= "table" then return "action", "unknown"; end
    for index, child in pairs(children) do
        local valid, hovered = pcall(function() return child:HasMouseOver(); end);
        if not valid then return "action", "unknown"; end
        if hovered then
            if type(index) == "number" then return "action", tostring(index); end
            return "action", "unknown";
        end
    end
    return "action", "none";
end

local function IsAlexander(playerID)
    local config = PlayerConfigurations[playerID];
    return config ~= nil and config:GetLeaderTypeName() == "LEADER_REMSELY_ALEXANDER_II";
end

local function OnLeader(playerID)
    local nextActive = IsAlexander(playerID);
    if nextActive == active then return; end
    active = nextActive;
    ContextPtr:SetHide(not active);
    Log(active and "scene=open" or "scene=other");
end

local function OnSceneClosed()
    if active then
        active = false;
        ContextPtr:SetHide(true);
        Log("scene=closed");
    end
end

local function OnInput(input)
    if not active then return false; end
    local message = input:GetMessageType();
    if message == KeyEvents.KeyUp and input:GetKey() == Keys.VK_ESCAPE then
        Log("input=escape");
    elseif message == MouseEvents.RButtonUp then
        Log("input=right_up");
    elseif message == MouseEvents.LButtonUp then
        local surface, selection = InputSurface();
        Log("input=left_up surface=" .. surface .. " selection=" .. selection);
    end
    return false;
end

local function Shutdown()
    LuaEvents.DiploScene_SceneOpened.Remove(OnLeader);
    LuaEvents.DiploScene_LeaderSelect.Remove(OnLeader);
    LuaEvents.DiploScene_SceneClosed.Remove(OnSceneClosed);
end

LuaEvents.DiploScene_SceneOpened.Add(OnLeader);
LuaEvents.DiploScene_LeaderSelect.Add(OnLeader);
LuaEvents.DiploScene_SceneClosed.Add(OnSceneClosed);
ContextPtr:SetInputHandler(OnInput, true);
ContextPtr:SetShutdown(Shutdown);

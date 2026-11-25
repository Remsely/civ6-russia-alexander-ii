-- Observe explicit user actions without replacing the game's diplomacy UI.
-- The separate speech bus must survive automatic session closure, but not a
-- player's choice to dismiss or advance the currently displayed response.
local ACTION = "/InGame/Diplomacy/DiplomacyActionView";
local DEAL = "/InGame/Diplomacy/DiplomacyDealView";
local POPUP = ACTION .. "/PopupRoot";
-- MakeInstance may expose its controls under the instance namespace. This
-- candidate follows that documented syntax; runtime access is unverified.
local INSTANCE_POPUP = ACTION .. "/PopupDialog/PopupRoot";
local CONVERSATION = ACTION .. "/ConversationContainer";
local CHOICES = CONVERSATION .. "/ConversationSelection_Alpha/ConversationSelection_Slide/ConversationSelectionGrid/ConversationSelectionStack";
local CHOICE_ALPHA = CONVERSATION .. "/ConversationSelection_Alpha";
local CHOICE_SLIDE = CHOICE_ALPHA .. "/ConversationSelection_Slide";
local CHOICE_GRID = CHOICE_SLIDE .. "/ConversationSelectionGrid";
local CINEMA = ACTION .. "/VoiceoverTextContainer";
local FADE = ACTION .. "/BlackFade/BlackFadeAnim";
local CLOSE = ACTION .. "/OverviewContainer/CloseButton";
local active = false;
-- Bounded diagnostics distinguish missing input, a blocked surface and a
-- detected button. No text, player data or per-frame events are recorded.
local traceCount = 0;
local function Trace(message)
    if traceCount >= 40 then return; end
    traceCount = traceCount + 1;
    print("REMSELY voice input: " .. message);
end

local function Lookup(path)
    local ok, result = pcall(function() return ContextPtr:LookUpControl(path); end);
    if ok then return result; end
    return nil;
end

-- Check the actual diplomacy surface, not parents above the action context.
-- The input observer is a different InGame context; traversing beyond the
-- action view made unverified assumptions about that shared ancestor chain.
local function Visibility(control)
    if control == nil then return false, "missing"; end
    local ok, hidden = pcall(function() return control:IsHidden(); end);
    if not ok then return false, "error"; end
    if hidden then return false, "hidden"; end
    return true, "visible";
end
local function Visible(control)
    return Visibility(control);
end

-- Explain what the previous implementation would have done, without letting
-- an unrelated ancestor veto the actual button. Only called on hovered items.
local function PreviousVisibility(control)
    for i = 1, 32 do
        if control == nil then return "missing-" .. i; end
        local ok, hidden = pcall(function() return control:IsHidden(); end);
        if not ok then return "hidden-error-" .. i; end
        if hidden then return "hidden-" .. i; end
        ok, control = pcall(function() return control:GetParent(); end);
        if not ok then return "parent-error-" .. i; end
        if control == nil then return "visible"; end
    end
    return "depth-limit";
end

local function HoveredEnabled(control)
    if not Visible(control) then return false; end
    local ok, hovered, disabled = pcall(function()
        return control:HasMouseOver(), control:IsDisabled();
    end);
    return ok and hovered and not disabled;
end

local function CanObserveAction()
    local root, deal = Lookup(ACTION), Lookup(DEAL);
    local popup = Lookup(POPUP);
    if popup == nil then popup = Lookup(INSTANCE_POPUP); end
    if root == nil or deal == nil then
        return nil, "missing action=" .. tostring(root ~= nil) .. " deal=" .. tostring(deal ~= nil)
            .. " popup=" .. tostring(popup ~= nil);
    end
    local rootOK, rootHidden = pcall(function() return root:IsHidden(); end);
    local dealOK, dealHidden = pcall(function() return deal:IsHidden(); end);
    -- PopupDialog is an instanced control and its absolute path is not
    -- accessible in at least one real game UI. Its absence must not disable
    -- every conversation click. When available, still protect open popups.
    local popupOK, popupVisible = true, false;
    if popup ~= nil then
        popupOK, popupVisible = pcall(function() return popup:IsVisible(); end);
    else
        Trace("popup lookup unavailable; continuing without popup guard");
    end
    if not rootOK or not dealOK or not popupOK then
        return nil, "error action=" .. tostring(rootOK) .. " deal=" .. tostring(dealOK)
            .. " popup=" .. tostring(popupOK);
    end
    if rootHidden then return nil, "action-hidden"; end
    if not dealHidden then return nil, "deal-visible"; end
    if popupVisible then return nil, "popup-visible"; end
    return root, "ok";
end

local function FadeStopped()
    local fade = Lookup(FADE);
    if fade == nil then return false; end
    local ok, stopped = pcall(function() return fade:IsStopped(); end);
    return ok and stopped;
end

local function OnInput(input)
    if not active then return false; end
    local message = input:GetMessageType();
    if message ~= MouseEvents.LButtonUp and message ~= MouseEvents.RButtonUp
        and not (message == KeyEvents.KeyUp and input:GetKey() == Keys.VK_ESCAPE) then return false; end
    local root, surface = CanObserveAction();
    if root == nil then
        Trace("blocked " .. surface .. " message=" .. tostring(message));
        return false;
    end
    local shouldStop = false;
    if message == KeyEvents.KeyUp and input:GetKey() == Keys.VK_ESCAPE then
        -- Vanilla always stops cinematic speech and closes the overview.
        -- An active conversation instead waits for its fade to finish.
        local conversation = Lookup(CONVERSATION);
        local cinema = Lookup(CINEMA);
        if conversation ~= nil and cinema ~= nil then
            if Visible(cinema) or not Visible(conversation) then
                shouldStop = true;
            else
                shouldStop = FadeStopped();
            end
        end
    elseif message == MouseEvents.RButtonUp then
        -- Vanilla only handles RMB to skip cinematics.
        local cinema = Lookup(CINEMA);
        shouldStop = cinema ~= nil and Visible(cinema) and FadeStopped();
    elseif message == MouseEvents.LButtonUp then
        local stack = Lookup(CHOICES);
        local conversation = Lookup(CONVERSATION);
        local detail = "not-checked";
        local surfaces = {conversation, Lookup(CHOICE_ALPHA), Lookup(CHOICE_SLIDE), Lookup(CHOICE_GRID), stack};
        local names = {"conversation", "alpha", "slide", "grid", "stack"};
        local choicesVisible = true;
        for i = 1, 5 do
            local visible, reason = Visibility(surfaces[i]);
            if not visible then detail = names[i] .. "-" .. reason; choicesVisible = false; break; end
        end
        if choicesVisible then
            local ok, children = pcall(function() return stack:GetChildren(); end);
            if ok and type(children) == "table" then
                detail = "none-hovered";
                for index, child in pairs(children) do
                    local hoverOK, hovered = pcall(function() return child:HasMouseOver(); end);
                    if not hoverOK then detail = "hover-error";
                    elseif hovered then
                        local disabledOK, disabled = pcall(function() return child:IsDisabled(); end);
                        local hiddenOK, hidden = pcall(function() return child:IsHidden(); end);
                        detail = "hovered=" .. tostring(index) .. ",hidden=" .. tostring(hiddenOK and hidden)
                            .. ",hiddenOK=" .. tostring(hiddenOK) .. ",disabled=" .. tostring(disabledOK and disabled)
                            .. ",disabledOK=" .. tostring(disabledOK) .. ",previous=" .. PreviousVisibility(child);
                        if hiddenOK and disabledOK and not hidden and not disabled then shouldStop = true; break; end
                    end
                end
            else detail = "children-error"; end
        end
        if not shouldStop then
            local close = Lookup(CLOSE);
            shouldStop = Visible(Lookup(ACTION .. "/OverviewContainer"))
                and close ~= nil and HoveredEnabled(close);
        end
        Trace("left_up conversation=" .. tostring(Visible(conversation))
            .. " stack=" .. tostring(Visible(stack)) .. " " .. detail .. " stop=" .. tostring(shouldStop));
    end
    if shouldStop then LuaEvents.REMSELY_VoiceUserSkip(); end
    return false; -- always let the original control handle the input
end

local function OnLeader(playerID)
    local config = PlayerConfigurations[playerID];
    local wasActive = active;
    active = config ~= nil and config:GetLeaderTypeName() == "LEADER_REMSELY_ALEXANDER_II";
    ContextPtr:SetHide(not active);
    if active and not wasActive then traceCount = 0; end
    if active then Trace("scene open"); end
end

local function OnSceneClosed()
    if active then Trace("scene closed"); end
    active = false;
    ContextPtr:SetHide(true);
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

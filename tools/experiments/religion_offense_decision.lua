-- Experimental pure classification; NOT a game event handler and NOT loaded
-- by the mod. The caller must independently establish all evidence, including
-- actor, successful spread, pre-operation majority and a durable action ID.
-- No boolean in this module proves that the engine actually supplies evidence.
local M = {}
local MAX_ID = 2147483647

local function integer(value, minimum, maximum)
    return type(value) == "number" and value == value and value % 1 == 0
        and value >= minimum and value <= maximum
end

-- Do not assign a numeric value here: the host chooses the diplomatic effect
-- and handles recording, expiry, persistence, and de-duplication. Returning a
-- kind is not itself an offense committed to the save.
--
-- action comes from an independently verified spread and must contain a city
-- majority taken before that action. The optional change is a separately
-- verified majority transition explicitly linked to this *same* action;
-- adjacency in an event log is not an association.
function M.classify(action, change)
    if type(action) ~= "table" then return nil, "invalid_action" end
    local actor, leader, owner = action.actor, action.leader, action.cityOwner
    if not integer(actor, 0, 63) or not integer(leader, 0, 63)
        or not integer(owner, 0, 63) or actor == leader
        or not integer(action.cityID, 0, MAX_ID)
        or not integer(action.beforeReligion, -1, MAX_ID)
        or not integer(action.leaderReligion, 0, MAX_ID)
        or not integer(action.unitReligion, 0, MAX_ID)
        or not integer(action.turn, 0, MAX_ID)
        or not integer(action.sequence, 1, MAX_ID) then
        return nil, "invalid_action"
    end
    if action.known ~= true or action.alexanderAI ~= true
        or action.success ~= true or action.candidateCount ~= 1
        or action.verifiedPrestate ~= true or action.verifiedActor ~= true
        or action.durableSequence ~= true then
        return nil, "unverified_action"
    end
    if action.unitReligion == action.leaderReligion then return nil, "same_religion" end

    local kind = owner == leader and "home" or "abroad"
    if kind == "abroad" and action.beforeReligion ~= action.leaderReligion then
        return nil, "unprotected_city"
    end

    -- nil means no verified majority result was supplied; it must never be
    -- misreported as a confirmed absence of conversion.
    local changed = nil
    if change ~= nil then
        if type(change) ~= "table" or change.verifiedLink ~= true
            or change.owner ~= owner or change.cityID ~= action.cityID
            or change.turn ~= action.turn or change.sequence ~= action.sequence
            or change.beforeReligion ~= action.beforeReligion
            or not integer(change.afterReligion, -1, MAX_ID) then
            return nil, "unverified_city_change"
        end
        changed = change.beforeReligion ~= change.afterReligion
        -- A foreign religion cannot be credited with a majority change to a
        -- third faith merely because events happened near each other.
        if changed and change.afterReligion ~= action.unitReligion then
            return nil, "unrelated_majority"
        end
    end
    return {kind = kind, actor = actor, leader = leader, cityOwner = owner,
        cityID = action.cityID, turn = action.turn, sequence = action.sequence,
        beforeReligion = action.beforeReligion, unitReligion = action.unitReligion,
        majorityChanged = changed}, nil
end

return M

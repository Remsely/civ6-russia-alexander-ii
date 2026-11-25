-- EXPERIMENT ONLY. Not connected to the mod and not an action attribution.
-- It models rivalry with the founder of a religion after it becomes dominant
-- in a foreign city that previously followed Alexander's founded religion.
-- The founder can be different from the unit owner. Only an independently
-- attributed unit action may create a rivalry. The module cannot determine
-- the cause or order of an event by itself.
local M = {}
local MAX_ID = 2147483647

local function integer(value, low, high)
    return type(value) == "number" and value == value and value % 1 == 0
        and value >= low and value <= high
end

-- previous is nil on the initial snapshot, otherwise {majority, sequence}.
-- event describes a single city-identity (owner + cityID) and a single
-- Alexander; the caller must keep their states separate, supply a reliable
-- ordered sequence, and reset state on city removal or ID reuse. The caller
-- must construct the founder lookup from authoritative religion data.
-- unitCauseVerified is true only if the caller has independent evidence that
-- this specific transition was caused by a unit. Passive and unknown causes
-- update majority without creating a rivalry.
-- The returned state is immutable input for the next call, not persisted here.
function M.observe(previous, event)
    if type(event) ~= "table" or not integer(event.leader, 0, 63)
        or not integer(event.cityOwner, 0, 63)
        or not integer(event.cityID, 0, MAX_ID)
        or not integer(event.leaderReligion, 0, MAX_ID)
        or not integer(event.majority, -1, MAX_ID)
        or not integer(event.sequence, 1, MAX_ID) then
        return nil, nil, "invalid_event"
    end
    if previous ~= nil and (type(previous) ~= "table"
        or not integer(previous.majority, -1, MAX_ID)
        or not integer(previous.sequence, 1, MAX_ID)
        or previous.leader ~= event.leader or previous.cityOwner ~= event.cityOwner
        or previous.cityID ~= event.cityID) then
        return nil, nil, "invalid_previous"
    end
    if previous ~= nil and event.sequence <= previous.sequence then
        return previous, nil, "duplicate_or_stale"
    end
    local nextState = {leader=event.leader, cityOwner=event.cityOwner, cityID=event.cityID,
        majority=event.majority, sequence=event.sequence}
    if previous == nil then return nextState, nil, "baseline" end
    if event.cityOwner == event.leader then return nextState, nil, "home_skipped" end
    if previous.majority ~= event.leaderReligion then return nextState, nil, "unprotected_before" end
    if event.majority == event.leaderReligion then return nextState, nil, "unchanged" end
    if event.majority == -1 then return nextState, nil, "no_new_religion" end
    if event.unitCauseVerified ~= true then return nextState, nil, "unit_cause_unverified" end
    if not integer(event.founder, 0, 63) or event.founderReligion ~= event.majority then
        return nextState, nil, "founder_unknown"
    end
    if event.founder == event.leader then return nextState, nil, "self_founder" end
    if event.founderEligible ~= true then return nextState, nil, "founder_ineligible" end
    return nextState, {leader=event.leader, rival=event.founder, cityOwner=event.cityOwner,
        cityID=event.cityID, previousReligion=previous.majority,
        newReligion=event.majority, sequence=event.sequence, basis="religion_founder"}, "rivalry"
end

return M

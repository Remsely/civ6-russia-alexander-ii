-- Experimental decision core: no Civ VI APIs and no game-state writes.
-- The host must only report a successful spread after unambiguously matching
-- an operation and city update. Until game-event order is verified this module
-- is deliberately not loaded by the shipping mod.
local M = {}
local TURNS, MAX_COMBINED = 30, 75
local RULES = {
    home = { first = 12, next = 3, limit = 60 },
    abroad = { first = 6, next = 2, limit = 30 },
}

-- The host must also check that the offender is a living major civilization.
function M.qualifies(action)
    return action.actor ~= nil and action.leader ~= nil and action.cityOwner ~= nil
        and action.actor ~= action.leader and action.cityOwner ~= action.actor
        and action.known == true and action.alexanderAI == true
        and action.success == true and action.candidateCount == 1
        and action.beforeReligion ~= nil and action.beforeReligion >= 0
        and action.beforeReligion == action.leaderReligion
        and action.unitReligion ~= nil and action.unitReligion >= 0
        and action.unitReligion ~= action.leaderReligion
end

local function total(home, abroad)
    return math.min(MAX_COMBINED, home + abroad)
end

-- One state per (leader, offender). Store both buckets and their expiry in the
-- save, not just the aggregate. A host must ensure the vanilla -12 is not also
-- counted: the prototype is deliberately not wired to the existing modifier.
function M.offense(state, action, turn, change)
    if not M.qualifies(action) then return false end
    local kind = action.cityOwner == action.leader and "home" or "abroad"
    local rule = RULES[kind]
    local oldHome, oldAbroad = state.home or 0, state.abroad or 0
    local previous = state[kind] or 0
    local nextValue = math.min(rule.limit, previous + (previous == 0 and rule.first or rule.next))
    local newHome = kind == "home" and nextValue or oldHome
    local newAbroad = kind == "abroad" and nextValue or oldAbroad
    local delta = total(oldHome, oldAbroad) - total(newHome, newAbroad)
    if delta ~= 0 and not change(delta) then return false end
    state[kind] = nextValue
    state[kind .. "Expires"] = turn + TURNS
    return true
end

function M.expire(state, turn, change)
    local oldHome, oldAbroad = state.home or 0, state.abroad or 0
    local expireHome = state.homeExpires ~= nil and turn >= state.homeExpires
    local expireAbroad = state.abroadExpires ~= nil and turn >= state.abroadExpires
    if not expireHome and not expireAbroad then return false end
    local newHome = expireHome and 0 or oldHome
    local newAbroad = expireAbroad and 0 or oldAbroad
    local delta = total(oldHome, oldAbroad) - total(newHome, newAbroad)
    if delta ~= 0 and not change(delta) then return false end
    if expireHome then state.home = nil; state.homeExpires = nil end
    if expireAbroad then state.abroad = nil; state.abroadExpires = nil end
    return true
end
-- Candidate matching is intentionally strict: a token is consumed by the
-- first observed update and cannot be reused or carried into another turn.
function M.start(action, candidateCityIds, turn)
    if #candidateCityIds ~= 1 then return nil end
    return { action = action, city = candidateCityIds[1], turn = turn, used = false }
end

function M.cityChanged(token, cityId, turn, beforeFollowers, afterFollowers)
    if token == nil or token.used or token.turn ~= turn or token.city ~= cityId then
        return nil
    end
    token.used = true
    if type(beforeFollowers) ~= "number" or type(afterFollowers) ~= "number"
        or afterFollowers <= beforeFollowers then return nil end
    token.action.success = true
    token.action.candidateCount = 1
    return token.action
end
return M

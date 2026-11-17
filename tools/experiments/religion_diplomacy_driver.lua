-- NOT connected to the mod. This prototype does not subscribe to game events.
--
-- One instance owns operations on a (leader, offender) pair. The injected
-- validatePair must check that both IDs designate live, eligible major players,
-- the leader is an AI Alexander, and the pair is usable by the native API.
-- confirmBaseline must return true ONLY when the shipped -9 and -12 bounds and
-- conditions have been checked. Other mods' penalties are outside this bound.
-- The caller must supply a durable, strictly increasing action sequence per
-- pair, stable across duplicate callbacks and saves. No Civ event currently
-- known to this project provides that sequence; this is an open integration
-- requirement, not a claim about the real event API.
--
-- set/get use one string property per pair. adjust is a void native operation;
-- normal return including nil means success, but a throw or explicit false may
-- happen after mutation. Journal such uncertain outcomes and never retry them
-- automatically. The journal does not make game saves or two engine writes
-- atomic; pending records require reconciliation by a separate trusted tool.
local M = {}
local OWN_CAP = 54 -- reserve 9 + 12 from requested combined maximum of 75
local MAX_INT = 2147483647
-- Native player-indexed score arrays are 64 slots in the inspected XP2 build.
-- This upper bound must be re-established before using another game build.
local NATIVE_PLAYER_SLOTS = 64
local PREFIX = "REMSELY_RELIGION_TEST_V1_"

local function integer(x, min, max)
    return type(x) == "number" and x == x and x >= min and x <= max and x % 1 == 0
end

local function clamp(sum)
    return math.min(OWN_CAP, sum)
end

local function empty()
    return { home = 0, abroad = 0, homeExpires = -1, abroadExpires = -1, seq = 0 }
end

local function valid(s)
    if not (integer(s.home, 0, 60) and integer(s.abroad, 0, 30)
        and integer(s.homeExpires, -1, MAX_INT) and integer(s.abroadExpires, -1, MAX_INT)
        and integer(s.seq, 0, MAX_INT)) then return false end
    if (s.home == 0) ~= (s.homeExpires == -1) then return false end
    if (s.abroad == 0) ~= (s.abroadExpires == -1) then return false end
    return true
end

local function encode(status, s)
    return table.concat({ "1", status, s.home, s.abroad, s.homeExpires, s.abroadExpires, s.seq }, ":")
end

local function encodePending(before, after, delta)
    return "1:P:" .. encode("C", before) .. "|" .. encode("C", after) .. "|" .. delta
end

local function decode(value)
    if value == nil then return empty(), "C" end
    if type(value) ~= "string" then return nil, "invalid_record" end
    if value:sub(1, 4) == "1:P:" then
        local oldString, newString, deltaString = value:match("^1:P:(1:C:[^|]+)|(1:C:[^|]+)|([%-]?%d+)$")
        if not oldString then return nil, "invalid_record" end
        local before, beforeStatus = decode(oldString)
        local after, afterStatus = decode(newString)
        local delta = tonumber(deltaString)
        if not before or not after or beforeStatus ~= "C" or afterStatus ~= "C"
            or not integer(delta, -OWN_CAP, OWN_CAP)
            or delta ~= clamp(before.home + before.abroad) - clamp(after.home + after.abroad)
            or delta == 0 or after.seq < before.seq then return nil, "invalid_record" end
        return after, "P"
    end
    local status, home, abroad, homeExpires, abroadExpires, seq =
        value:match("^1:(C):(%d+):(%d+):([%-]?%d+):([%-]?%d+):(%d+)$")
    if status == nil then return nil, "invalid_record" end
    local s = { home = tonumber(home), abroad = tonumber(abroad),
        homeExpires = tonumber(homeExpires), abroadExpires = tonumber(abroadExpires), seq = tonumber(seq) }
    if not valid(s) then return nil, "invalid_record" end
    return s, status
end

-- Driver supplied functions intentionally have no implicit self parameter.
function M.new(api)
    assert(type(api) == "table" and type(api.core) == "table")
    assert(type(api.get) == "function" and type(api.set) == "function")
    assert(type(api.adjust) == "function" and type(api.validatePair) == "function")
    assert(type(api.confirmBaseline) == "function" and integer(api.maxPlayers, 1, NATIVE_PLAYER_SLOTS))
    local busy, fault = {}, {}
    local driver = {}

    local function keyFor(leader, offender)
        if not integer(leader, 0, api.maxPlayers - 1)
            or not integer(offender, 0, api.maxPlayers - 1) or leader == offender then
            return nil, "invalid_pair"
        end
        local ok, eligible = pcall(api.validatePair, leader, offender)
        if not ok or eligible ~= true then return nil, "invalid_pair" end
        local okBaseline, confirmed = pcall(api.confirmBaseline)
        if not okBaseline or confirmed ~= true then return nil, "unconfirmed_baseline" end
        return PREFIX .. leader .. "_" .. offender
    end

    local function read(key)
        local ok, value = pcall(api.get, key)
        if not ok then return nil, "read_failed" end
        local s, status = decode(value)
        if not s then return nil, status end
        if status == "P" then return nil, "pending_reconciliation" end
        return s
    end

    -- Always read back: SetProperty may return nil on success, or an injected
    -- failure may occur before or after the write. No native call on mismatch.
    local function write(key, value)
        local okSet, result = pcall(api.set, key, value)
        local okGet, current = pcall(api.get, key)
        if not okGet then return false end
        if current == value then return true end
        if not okSet or result == false then return false end
        return false
    end

    local function mutate(leader, offender, mutator)
        local key, why = keyFor(leader, offender)
        if not key then return false, why end
        if fault[key] then return false, "pending_reconciliation" end
        if busy[key] then return false, "pair_busy" end
        busy[key] = true
        local ok, result, reason = pcall(function()
            local previous, err = read(key)
            if not previous then return false, err end
            local candidate = { home = previous.home, abroad = previous.abroad,
                homeExpires = previous.homeExpires, abroadExpires = previous.abroadExpires,
                seq = previous.seq }
            -- The core uses nil for unexpired empty buckets on expiry.
            if candidate.homeExpires == -1 then candidate.homeExpires = nil end
            if candidate.abroadExpires == -1 then candidate.abroadExpires = nil end
            local changed, changeReason = mutator(candidate, previous)
            if not changed then return false, changeReason end
            candidate.home = candidate.home or 0
            candidate.abroad = candidate.abroad or 0
            candidate.homeExpires = candidate.homeExpires or -1
            candidate.abroadExpires = candidate.abroadExpires or -1
            if not valid(candidate) then return false, "invalid_candidate" end
            local delta = clamp(previous.home + previous.abroad) - clamp(candidate.home + candidate.abroad)
            local final = encode("C", candidate)
            if delta == 0 then
                if not write(key, final) then
                    fault[key] = true
                    return false, "storage_uncertain"
                end
                return true, "recorded"
            end
            -- This is an intent marker, not proof that adjust subsequently ran.
            if not write(key, encodePending(previous, candidate, delta)) then
                fault[key] = true
                return false, "storage_uncertain"
            end
            local okAdjust, adjustment = pcall(api.adjust, leader, offender, delta)
            if not okAdjust or adjustment == false then
                fault[key] = true
                return false, "adjustment_uncertain"
            end
            if not write(key, final) then
                fault[key] = true
                return false, "commit_uncertain"
            end
            return true, "applied"
        end)
        busy[key] = nil
        if not ok then
            -- Exceptions after entering the transaction can be ambiguous.
            fault[key] = true
            return false, "unexpected_error"
        end
        return result, reason
    end

    function driver.offense(leader, offender, action, turn, seq)
        if type(action) ~= "table" or not integer(turn, 0, MAX_INT - 30)
            or not integer(seq, 1, MAX_INT) or action.leader ~= leader or action.actor ~= offender
            or not integer(action.cityOwner, 0, api.maxPlayers - 1)
            or not integer(action.leaderReligion, 0, MAX_INT)
            or not integer(action.unitReligion, 0, MAX_INT) then
            return false, "invalid_action"
        end
        return mutate(leader, offender, function(candidate, previous)
            if seq <= previous.seq then return false, "stale_or_duplicate" end
            if not api.core.qualifies(action) then return false, "ineligible" end
            -- One transaction also settles overdue buckets before a new action.
            api.core.expire(candidate, turn, function() return true end)
            local result = api.core.offense(candidate, action, turn, function() return true end)
            if not result then return false, "ineligible" end
            candidate.seq = seq
            return true
        end)
    end

    function driver.expire(leader, offender, turn)
        if not integer(turn, 0, MAX_INT) then return false, "invalid_turn" end
        return mutate(leader, offender, function(candidate)
            local result = api.core.expire(candidate, turn, function() return true end)
            if not result then return false, "not_due" end
            return true
        end)
    end

    function driver.inspect(leader, offender)
        local key, why = keyFor(leader, offender)
        if not key then return nil, why end
        if fault[key] then return nil, "pending_reconciliation" end
        return read(key)
    end

    return driver
end

-- Concrete adapter shape for future gameplay use; never registered here.
-- maxPlayers must be established by the host from the game, not guessed; the
-- 64-slot upper bound is specific to the investigated XP2 build.
-- confirmBaseline must establish the -9/-12 precondition independently; a
-- constant true would turn the numeric cap into an unverified assumption.
function M.newGameDriver(core, game, players, configurations, maxPlayers, confirmBaseline)
    return M.new({
        core = core,
        maxPlayers = maxPlayers,
        confirmBaseline = confirmBaseline,
        get = function(key) return game:GetProperty(key) end,
        set = function(key, value) return game:SetProperty(key, value) end,
        validatePair = function(leader, offender)
            local a, b, config = players[leader], players[offender], configurations[leader]
            if a == nil or b == nil or config == nil then return false end
            if not a:IsAlive() or not a:IsMajor() or a:IsHuman()
                or not b:IsAlive() or not b:IsMajor() then return false end
            if config:GetLeaderTypeName() ~= "LEADER_REMSELY_ALEXANDER_II" then return false end
            local diplomacy = a:GetDiplomacy()
            if diplomacy == nil or not diplomacy:HasMet(offender) then return false end
            local ai = a:GetAi_Diplomacy()
            return ai ~= nil and ai.AdjustBaseDiplomacy ~= nil
        end,
        adjust = function(leader, offender, delta)
            local ai = players[leader]:GetAi_Diplomacy()
            if ai == nil then error("AI diplomacy became unavailable") end
            return ai:AdjustBaseDiplomacy(offender, delta)
        end,
    })
end

return M

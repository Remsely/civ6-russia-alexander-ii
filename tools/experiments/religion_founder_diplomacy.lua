-- EXPERIMENT ONLY. The caller supplies a verified founder-rivalry event and a
-- durable sequence; this module does not observe conversion or attach effects.
-- The pair record is authoritative; capital-plot bits are a projection only.
local M = {}
local MAX_INT, CAP, DURATION = 2147483647, 30, 30
local PREFIX = "REMSELY_REL_RIVALRY_"
local WEIGHTS = {2, 4, 8, 16}

local function integer(n, lo, hi)
    return type(n) == "number" and n == n and n % 1 == 0 and n >= lo and n <= hi
end

local function decode(raw)
    if raw == nil then return {score=0, expires=-1, seq=0, plot=-1} end
    if type(raw) ~= "string" then return nil end
    local score, expires, seq, plot = raw:match("^1:(%d+):([%-]?%d+):(%d+):([%-]?%d+)$")
    local s = {score=tonumber(score), expires=tonumber(expires), seq=tonumber(seq), plot=tonumber(plot)}
    if not integer(s.score, 0, CAP) or s.score % 2 ~= 0
        or not integer(s.expires, -1, MAX_INT) or not integer(s.seq, 0, MAX_INT)
        or not integer(s.plot, -1, MAX_INT) or (s.score == 0) ~= (s.expires == -1) then return nil end
    return s
end

local function encode(s)
    return table.concat({"1", s.score, s.expires, s.seq, s.plot}, ":")
end

function M.new(api)
    assert(type(api) == "table" and integer(api.maxPlayers, 1, 64))
    for _,name in ipairs({"get", "set", "getBit", "setBit", "capital", "owner"}) do
        assert(type(api[name]) == "function", "missing " .. name)
    end
    local driver, busy = {}, {}
    local function key(leader, founder)
        assert(integer(leader, 0, api.maxPlayers-1) and integer(founder, 0, api.maxPlayers-1) and leader ~= founder)
        return PREFIX .. leader .. "_PAIR_" .. founder
    end
    local function bitKey(leader, weight) return PREFIX .. leader .. "_BIT_" .. weight end
    local function read(leader, founder)
        local s = decode(api.get(key(leader, founder)))
        assert(s, "invalid saved rivalry record")
        return s
    end
    local function write(leader, founder, state)
        local k, value = key(leader, founder), encode(state)
        api.set(k, value)
        assert(api.get(k) == value, "record write failed")
    end
    local function expectedAt(leader, plot)
        local owner = api.owner(plot)
        if not integer(owner, 0, api.maxPlayers-1) or owner == leader or api.capital(owner) ~= plot then return 0 end
        return read(leader, owner).score
    end
    local function project(leader, plot, score)
        -- Clear bits first so intermediate values never exceed either endpoint.
        for _,desired in ipairs({0, 1}) do
            for _,weight in ipairs(WEIGHTS) do
                local bit = math.floor(score / weight) % 2
                local k = bitKey(leader, weight)
                local old = api.getBit(plot, k) or 0
                assert(old == 0 or old == 1, "invalid projection")
                if bit == desired and old ~= bit then
                    api.setBit(plot, k, bit)
                    assert((api.getBit(plot, k) or 0) == bit, "projection write failed")
                end
            end
        end
    end
    local function reconcile(leader, founder, s)
        local target = api.capital(founder) or -1
        assert(integer(target, -1, MAX_INT), "invalid capital")
        if s.plot >= 0 and s.plot ~= target then project(leader, s.plot, expectedAt(leader, s.plot)) end
        if target >= 0 then
            assert(api.owner(target) == founder, "capital owner mismatch")
            project(leader, target, s.score)
        end
        if s.plot ~= target then s.plot = target; write(leader, founder, s) end
    end
    local function run(leader, founder, callback)
        local k = key(leader, founder)
        assert(not busy[k], "reentrant pair update")
        busy[k] = true
        local ok, a, b = pcall(function() return callback(read(leader, founder)) end)
        busy[k] = nil
        if not ok then return false, a end
        return a, b
    end
    local function expireIfDue(s, turn)
        if s.expires >= 0 and turn >= s.expires then s.score, s.expires = 0, -1 end
    end
    function driver.record(leader, founder, turn, sequence)
        assert(integer(turn, 0, MAX_INT-DURATION) and integer(sequence, 1, MAX_INT))
        return run(leader, founder, function(s)
            if sequence <= s.seq then reconcile(leader, founder, s); return false, "duplicate" end
            expireIfDue(s, turn)
            s.score = math.min(CAP, s.score + (s.score == 0 and 6 or 2))
            s.expires, s.seq = turn + DURATION, sequence
            write(leader, founder, s) -- durable source before recoverable projection
            reconcile(leader, founder, s)
            return true, s.score
        end)
    end
    function driver.expire(leader, founder, turn)
        assert(integer(turn, 0, MAX_INT))
        return run(leader, founder, function(s)
            local before = s.score
            expireIfDue(s, turn)
            if before ~= s.score then write(leader, founder, s) end
            reconcile(leader, founder, s)
            return true, s.score
        end)
    end
    function driver.reconcile(leader, founder)
        return run(leader, founder, function(s) reconcile(leader, founder, s); return true, s.score end)
    end
    function driver.inspect(leader, founder) return read(leader, founder) end
    return driver
end
return M

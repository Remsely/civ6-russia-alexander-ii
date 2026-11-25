-- EXPERIMENT: independent -75 component variant; not imported by the mod. Caller must independently prove that
-- an action occurred, its actor/target/before-faith, and its durable sequence.
-- The saved pair record is authoritative; seven plot properties are only a
-- reconstructible projection for candidate City diplomacy modifiers.
local M = {}
local MAX_INT, CAP, LIFETIME = 2147483647, 75, 30
local PREFIX = "REMSELY_REL_COMPONENT75_"
local WEIGHTS = {1, 2, 4, 8, 16, 32, 64}

local function integer(n, lo, hi)
    return type(n) == "number" and n == n and n % 1 == 0 and n >= lo and n <= hi
end

local function empty()
    return {home=0, abroad=0, homeExpires=-1, abroadExpires=-1, seq=0, projected=-1}
end

local function encode(s)
    return table.concat({"1",s.home,s.abroad,s.homeExpires,s.abroadExpires,s.seq,s.projected}, ":")
end

local function decode(raw)
    if raw == nil then return empty() end
    if type(raw) ~= "string" then return nil end
    local h,a,he,ae,seq,plot = raw:match("^1:(%d+):(%d+):([%-]?%d+):([%-]?%d+):(%d+):([%-]?%d+)$")
    local s = {home=tonumber(h), abroad=tonumber(a), homeExpires=tonumber(he),
        abroadExpires=tonumber(ae), seq=tonumber(seq), projected=tonumber(plot)}
    if not integer(s.home,0,75) or not integer(s.abroad,0,75)
        or not integer(s.homeExpires,-1,MAX_INT) or not integer(s.abroadExpires,-1,MAX_INT)
        or not integer(s.seq,0,MAX_INT) or not integer(s.projected,-1,MAX_INT)
        or (s.home == 0) ~= (s.homeExpires == -1)
        or (s.abroad == 0) ~= (s.abroadExpires == -1) then return nil end
    return s
end

function M.new(api)
    assert(type(api)=="table" and type(api.get)=="function" and type(api.set)=="function")
    assert(type(api.getBit)=="function" and type(api.setBit)=="function")
    assert(type(api.capital)=="function" and type(api.owner)=="function")
    assert(integer(api.maxPlayers,1,64))
    local busy = {}
    local driver = {}

    local function pairKey(leader, actor)
        assert(integer(leader,0,api.maxPlayers-1) and integer(actor,0,api.maxPlayers-1) and leader ~= actor)
        return PREFIX .. leader .. "_" .. actor
    end
    local function bitKey(leader, weight) return PREFIX .. leader .. "_BIT_" .. weight end
    local function score(s) return math.min(CAP,s.home+s.abroad) end
    local function read(leader,actor)
        local raw=api.get(pairKey(leader,actor))
        local s=decode(raw)
        assert(s ~= nil,"invalid saved religion record")
        return s
    end
    local function write(leader,actor,s)
        local key,value=pairKey(leader,actor),encode(s)
        api.set(key,value)
        assert(api.get(key)==value,"record write did not persist")
    end
    -- A captured former capital may now be another offender's capital. Restore
    -- its current owner's projection rather than blindly clearing their bits.
    local function expectedAt(leader,plot)
        local owner=api.owner(plot)
        if not integer(owner,0,api.maxPlayers-1) or owner==leader or api.capital(owner)~=plot then return 0 end
        return score(read(leader,owner))
    end
    local function bits(leader,plot,value)
        local desired={}
        for _,w in ipairs(WEIGHTS) do desired[w]=math.floor(value/w)%2 end
        -- Remove obsolete bits first, so a transition never briefly exceeds
        -- both the old and new values if callbacks execute synchronously.
        for _,wanted in ipairs({0,1}) do
            for _,w in ipairs(WEIGHTS) do
                local key=bitKey(leader,w)
                local current=api.getBit(plot,key) or 0
                assert(current==0 or current==1,"invalid projected bit")
                if desired[w]==wanted and current~=wanted then
                    api.setBit(plot,key,wanted)
                    assert((api.getBit(plot,key) or 0)==wanted,"plot write did not persist")
                end
            end
        end
    end
    local function reconcile(leader,actor,s)
        local target=api.capital(actor)
        if target==nil then target=-1 end
        assert(integer(target,-1,MAX_INT),"invalid capital plot")
        if s.projected>=0 and s.projected~=target then
            bits(leader,s.projected,expectedAt(leader,s.projected))
        end
        if target>=0 then
            assert(api.owner(target)==actor,"capital ownership mismatch")
            bits(leader,target,score(s))
        end
        if s.projected~=target then s.projected=target; write(leader,actor,s) end
    end
    local function withPair(leader,actor,f)
        local key=pairKey(leader,actor)
        assert(not busy[key],"reentrant update")
        busy[key]=true
        local ok,a,b=pcall(function() return f(read(leader,actor)) end)
        busy[key]=nil
        if not ok then return false,a end
        return a,b
    end
    local function expire(s,turn)
        if s.homeExpires>=0 and turn>=s.homeExpires then s.home=0;s.homeExpires=-1 end
        if s.abroadExpires>=0 and turn>=s.abroadExpires then s.abroad=0;s.abroadExpires=-1 end
    end
    function driver.offense(leader,actor,kind,turn,seq)
        assert((kind=="home" or kind=="abroad") and integer(turn,0,MAX_INT-LIFETIME) and integer(seq,1,MAX_INT))
        return withPair(leader,actor,function(s)
            if seq<=s.seq then reconcile(leader,actor,s);return false,"duplicate" end
            expire(s,turn)
            local was=s[kind]
            if kind=="home" then s.home=math.min(CAP,was+(was==0 and 12 or 3));s.homeExpires=turn+LIFETIME
            else s.abroad=math.min(CAP,was+(was==0 and 6 or 2));s.abroadExpires=turn+LIFETIME end
            s.seq=seq
            write(leader,actor,s) -- authoritative before any projected bits
            reconcile(leader,actor,s)
            return true,score(s)
        end)
    end
    function driver.expire(leader,actor,turn)
        assert(integer(turn,0,MAX_INT))
        return withPair(leader,actor,function(s)
            local before=encode(s)
            expire(s,turn)
            if before~=encode(s) then write(leader,actor,s) end
            reconcile(leader,actor,s)
            return true,score(s)
        end)
    end
    function driver.reconcile(leader,actor)
        return withPair(leader,actor,function(s) reconcile(leader,actor,s);return true,score(s) end)
    end
    function driver.inspect(leader,actor) return read(leader,actor) end
    return driver
end
return M

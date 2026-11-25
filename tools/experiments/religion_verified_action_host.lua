-- EXPERIMENT: this file has no subscriptions and is not imported by the mod.
-- The caller must provide independently verified actions and stable per-pair
-- sequence numbers; this host cannot obtain or prove either from game events.
-- No direct AdjustBaseDiplomacy call is used.
local M = {}
local MAX_INT=2147483647
local function integer(n,lo,hi)
    return type(n)=="number" and n==n and n%1==0 and n>=lo and n<=hi
end

function M.new(modules,env)
    assert(type(modules)=="table" and type(env)=="table")
    assert(type(modules.core)=="table" and type(modules.core.qualifies)=="function")
    assert(type(modules.projection)=="table" and type(modules.projection.new)=="function")
    assert(type(modules.attach)=="table" and type(modules.attach.ensure)=="function")
    assert(type(modules.gameeffects)=="table" and type(modules.gameeffects.new)=="function")
    assert(type(env.projection)=="table" and integer(env.projection.maxPlayers,1,64))
    assert(type(env.eligibleLeader)=="function" and type(env.eligibleOffense)=="function")
    assert(type(env.validateVerifiedAction)=="function" and type(env.confirmBaseline)=="function")
    assert(type(env.definitions)=="function" and type(env.confirmDefinitions)=="function")
    local maxPlayers=env.projection.maxPlayers
    local projection=modules.projection.new(env.projection)
    local modifierApi=modules.gameeffects.new(env.effects,env.players)
    local attached={}
    local host={}

    local function affirmative(fn,...)
        local ok,value=pcall(fn,...)
        return ok and value==true
    end
    local function validLeader(id) return integer(id,0,maxPlayers-1) end
    local function validPair(leader,actor)
        return validLeader(leader) and validLeader(actor) and leader~=actor
    end
    local function checkLeader(leader)
        if not validLeader(leader) or not affirmative(env.eligibleLeader,leader) then
            return false,"ineligible_leader"
        end
        if not affirmative(env.confirmBaseline,leader) then return false,"baseline_unverified" end
        return true
    end
    local function definitions(leader)
        local ok,value=pcall(env.definitions,leader)
        if not ok or type(value)~="table" or #value~=6 then return nil end
        local seen={}
        for _,name in ipairs(value) do
            if type(name)~="string" or name=="" or seen[name] then return nil end
            seen[name]=true
        end
        -- The adapter must establish that each native definition actually
        -- binds the corresponding leader-specific plot bit and -weight.
        if not affirmative(env.confirmDefinitions,leader,value) then return nil end
        return value,seen
    end
    local function validHandles(leader,known)
        if known==nil then return false end
        for i,id in ipairs(known.ids) do
            local ok,name,owner=pcall(modifierApi.describe,id,known.names)
            if not ok or name~=known.definitions[i] or owner~=leader then return false end
        end
        return #known.ids==6
    end
    local function ensure(leader,force)
        local ok,reason=checkLeader(leader)
        if not ok then attached[leader]=nil;return false,reason end
        if not force and validHandles(leader,attached[leader]) then
            if affirmative(env.confirmDefinitions,leader,attached[leader].definitions) then return true end
            attached[leader]=nil
            return false,"definitions_unavailable"
        end
        attached[leader]=nil
        local names,target=definitions(leader)
        if names==nil then return false,"definitions_unavailable" end
        local success,ids=modules.attach.ensure(modifierApi,leader,names)
        if not success then return false,"attachment_" .. tostring(ids) end
        attached[leader]={definitions=names,names=target,ids=ids}
        return true
    end
    local function checkedAction(action,turn,seq)
        if type(action)~="table" or not validPair(action.leader,action.actor)
            or not validLeader(action.cityOwner) or not integer(action.cityID,0,MAX_INT)
            or not integer(action.leaderReligion,0,MAX_INT)
            or not integer(action.unitReligion,0,MAX_INT)
            or not integer(action.beforeReligion,-1,MAX_INT)
            or not integer(turn,0,MAX_INT-30) or not integer(seq,1,MAX_INT) then return false end
        if not affirmative(modules.core.qualifies,action) then return false end
        if not affirmative(env.eligibleOffense,action.leader,action.actor) then return false end
        return affirmative(env.validateVerifiedAction,action,turn,seq)
    end
    -- Explicit full rescan for startup or owner/definition lifecycle changes.
    function host.initialize(leader) return ensure(leader,true) end
    function host.invalidate(leader) attached[leader]=nil end
    function host.offense(action,turn,seq)
        if not checkedAction(action,turn,seq) then return false,"action_unverified" end
        local ok,reason=ensure(action.leader,false)
        if not ok then return false,reason end
        local kind=action.cityOwner==action.leader and "home" or "abroad"
        return projection.offense(action.leader,action.actor,kind,turn,seq)
    end
    -- Maintenance is allowed for an eliminated offender, to remove/move stale
    -- plot bits. It still requires an eligible live leader and verified native
    -- attachments. Actual lifecycle event discovery is outside this module.
    function host.reconcile(leader,actor)
        if not validPair(leader,actor) then return false,"invalid_pair" end
        local ok,reason=ensure(leader,false)
        if not ok then return false,reason end
        return projection.reconcile(leader,actor)
    end
    function host.expire(leader,actor,turn)
        if not validPair(leader,actor) or not integer(turn,0,MAX_INT) then return false,"invalid_pair" end
        local ok,reason=ensure(leader,false)
        if not ok then return false,reason end
        return projection.expire(leader,actor,turn)
    end
    function host.inspect(leader,actor)
        if not validPair(leader,actor) then return nil,"invalid_pair" end
        local ok,value=pcall(projection.inspect,leader,actor)
        if not ok then return nil,"invalid_record" end
        return value
    end
    return host
end
return M

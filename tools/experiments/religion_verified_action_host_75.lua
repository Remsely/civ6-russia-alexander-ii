-- EXPERIMENT ONLY: no subscriptions, game integration, or evidence producer.
-- The caller must establish actor, city, pre-operation religion, a durable
-- unique sequence, baseline effects and all seven native definitions.
-- The -75 bound applies only to the projection's own component, not the total
-- of this component and other diplomatic effects.
local M = {}
local MAX_INT = 2147483647
local WEIGHTS = {1, 2, 4, 8, 16, 32, 64}

local function integer(n, lo, hi)
    return type(n)=="number" and n==n and n%1==0 and n>=lo and n<=hi
end

function M.new(modules, env)
    assert(type(modules)=="table" and type(env)=="table")
    assert(type(modules.core)=="table" and type(modules.core.qualifies)=="function")
    assert(type(modules.projection)=="table" and type(modules.projection.new)=="function")
    assert(type(modules.attach)=="table" and type(modules.attach.ensure)=="function")
    assert(type(modules.gameeffects)=="table" and type(modules.gameeffects.new)=="function")
    assert(type(env.projection)=="table" and integer(env.projection.maxPlayers,1,64))
    assert(type(env.eligibleLeader)=="function" and type(env.eligibleOffense)=="function")
    assert(type(env.validateVerifiedAction)=="function" and type(env.confirmBaseline)=="function")
    assert(type(env.confirmDefinitions)=="function")
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
    local function nameFor(leader,weight)
        return "REMSELY_REL_COMPONENT75_" .. leader .. "_MOD_" .. weight
    end
    local function canonical(leader,names)
        if type(names)~="table" or #names~=#WEIGHTS then return false end
        for i,weight in ipairs(WEIGHTS) do
            if names[i]~=nameFor(leader,weight) then return false end
        end
        return true
    end
    local function definitions(leader)
        local names,seen={},{}
        for _,weight in ipairs(WEIGHTS) do
            local name=nameFor(leader,weight)
            names[#names+1]=name
            seen[name]=true
        end
        -- A correct name alone cannot establish the native definition's actual
        -- collection, subject requirement, property name, value or activation.
        if not affirmative(env.confirmDefinitions,leader,names) or not canonical(leader,names) then return nil end
        return names,seen
    end
    local function validHandles(leader,known)
        if known==nil or not canonical(leader,known.definitions) or #known.ids~=#WEIGHTS then return false end
        for i,id in ipairs(known.ids) do
            local ok,name,owner=pcall(modifierApi.describe,id,known.names)
            if not ok or name~=known.definitions[i] or owner~=leader then return false end
        end
        return true
    end
    local function ensure(leader,force)
        local ok,reason=checkLeader(leader)
        if not ok then attached[leader]=nil;return false,reason end
        if not force and validHandles(leader,attached[leader]) then
            if affirmative(env.confirmDefinitions,leader,attached[leader].definitions)
                and canonical(leader,attached[leader].definitions) then return true end
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
    -- A lifecycle adapter must enumerate all saved pairs and call reconcile;
    -- constructing or initializing this host does not do that automatically.
    function host.initialize(leader) return ensure(leader,true) end
    function host.invalidate(leader) attached[leader]=nil end
    function host.offense(action,turn,seq)
        if not checkedAction(action,turn,seq) then return false,"action_unverified" end
        local ok,reason=ensure(action.leader,false)
        if not ok then return false,reason end
        local kind=action.cityOwner==action.leader and "home" or "abroad"
        return projection.offense(action.leader,action.actor,kind,turn,seq)
    end
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

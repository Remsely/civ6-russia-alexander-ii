-- Experimental gameplay adapter only; not imported into the mod.
-- Native modifier instances, not a marker, are the source of truth. A single
-- complete scan on initialization/retry permits recovery if a previous attach
-- succeeded but the caller crashed before recording its returned handle.
local M = {}

local function integer(x,lo,hi)
    return type(x)=="number" and x==x and x%1==0 and x>=lo and x<=hi
end

function M.ensure(api,leader,expected)
    assert(type(api)=="table" and type(api.instances)=="function"
        and type(api.describe)=="function" and type(api.attach)=="function")
    assert(integer(leader,0,63) and type(expected)=="table" and #expected==6)
    local target,found,ids = {},{},{}
    for _,name in ipairs(expected) do
        assert(type(name)=="string" and name~="" and not target[name],"invalid expected definitions")
        target[name]=true
    end

    -- A stale marker is never trusted: duplicate live instances are unsafe
    -- even if the six recorded handles individually still exist.
    local ok,values=pcall(api.instances)
    if not ok or type(values)~="table" then return false,"instances_unavailable" end
    local seen={}
    for _,id in pairs(values) do
        if not integer(id,0,2147483647) or seen[id] then return false,"invalid_snapshot" end
        seen[id]=true
        local valid,definition,owner=pcall(api.describe,id,target)
        -- Incomplete native snapshot is ambiguous, not proof of absence.
        if not valid or type(definition)~="string" or not integer(owner,-1,63) then
            return false,"describe_failed"
        end
        if target[definition] and owner==leader then
            if found[definition]~=nil then return false,"duplicate_instance" end
            found[definition]=id
        end
    end
    for _,name in ipairs(expected) do
        if found[name]==nil then
            local success,id=pcall(api.attach,leader,name)
            -- A thrown/invalid return may occur after the native attach. Stop;
            -- the next ensure() will rescan instead of creating a duplicate.
            if not success or not integer(id,0,2147483647) then return false,"attach_uncertain" end
            local verified,definition,owner=pcall(api.describe,id,target)
            if not verified or definition~=name or owner~=leader or seen[id] then
                return false,"attach_uncertain"
            end
            seen[id]=true;found[name]=id
        end
        ids[#ids+1]=found[name]
    end
    -- Advisory only. Missing, failed, or stale serialization cannot cause
    -- duplicate attaches because every later attempt scans the real instances.
    if type(api.marker)=="function" then pcall(api.marker,leader,ids) end
    return true,ids
end
return M

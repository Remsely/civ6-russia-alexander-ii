-- EXPERIMENT ONLY: attach exactly four rivalry definitions to one leader.
-- This module scans live instances only on initialization/recovery, not every
-- conversion. It never trusts a persisted marker to establish attachment.
local M = {}
local WEIGHTS = {2, 4, 8, 16}
local function integer(n, lo, hi)
    return type(n) == "number" and n == n and n % 1 == 0 and n >= lo and n <= hi
end
function M.ensure(api, leader)
    assert(integer(leader, 0, 63) and type(api) == "table")
    for _, name in ipairs({"instances", "describe", "attach", "validate"}) do
        assert(type(api[name]) == "function", "missing " .. name)
    end
    local names, target, found, ids, seen = {}, {}, {}, {}, {}
    for _,weight in ipairs(WEIGHTS) do
        local name = "REMSELY_REL_RIVALRY_" .. leader .. "_MOD_" .. weight
        local valid, result = pcall(api.validate, leader, weight, name)
        if not valid or result ~= true then return false, "invalid_definition" end
        names[#names+1] = name; target[name] = true
    end
    local ok, instances = pcall(api.instances)
    if not ok or type(instances) ~= "table" then return false, "instances_unavailable" end
    for _,id in pairs(instances) do
        if not integer(id, 0, 2147483647) or seen[id] then return false, "invalid_snapshot" end
        seen[id] = true
        local known, name, owner = pcall(api.describe, id, target)
        if not known or type(name) ~= "string" or not integer(owner, -1, 63) then
            return false, "describe_failed"
        end
        if target[name] and owner == leader then
            if found[name] ~= nil then return false, "duplicate_instance" end
            found[name] = id
        end
    end
    for _,name in ipairs(names) do
        if found[name] == nil then
            local attached, id = pcall(api.attach, leader, name)
            if not attached or not integer(id, 0, 2147483647) then return false, "attach_uncertain" end
            local described, actual, owner = pcall(api.describe, id, target)
            if not described or actual ~= name or owner ~= leader or seen[id] then
                return false, "attach_uncertain"
            end
            seen[id], found[name] = true, id
        end
        ids[#ids+1] = found[name]
    end
    return true, ids
end
return M

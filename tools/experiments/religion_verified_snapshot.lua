-- Experimental pure adapter; NOT imported by the mod and not a game-event
-- subscription. A caller must establish every evidence flag for each action.
-- These assertions are a contract, not a way to prove game-event timing.
local M = {}
local function integer(n, min, max)
    return type(n)=="number" and n==n and n%1==0 and n>=min and n<=max
end
local LIMIT = 2147483647
local function sameCity(a,b)
    if a==nil or b==nil then return a==nil and b==nil end
    return a.owner==b.owner and a.id==b.id and a.beforeReligion==b.beforeReligion
end
local function key(x,y) return tostring(x) .. "," .. tostring(y) end

-- `target` must be the separately audited religion_spread_target.lua module.
-- `cells[0]` is the unit's plot; cells[1..6] are adjacent plots in native
-- direction 0..5 order. An off-map cell must be {exists=false}; nil is
-- unknown, not evidence of an empty/off-map plot. Present cells must contain
-- cityKnown=true and either city=nil (empty) or {owner,id,beforeReligion}.
-- Every field describes the SAME instant just before the successful operation.
-- `evidence` is an external attestation of provenance, not verified here.
function M.attribute(target, snapshot)
    if type(target)~="table" or type(target.find)~="function" or type(snapshot)~="table" then
        return nil,"invalid_input"
    end
    local proof=snapshot.evidence
    if type(proof)~="table" or proof.successfulOperation~=true or proof.exactBeforeState~=true
        or proof.orderedEvents~=true or proof.completeMap~=true or proof.unitIdentity~=true
        or proof.lifecycleHandled~=true or proof.uniquePersistentSequence~=true then
        return nil,"unverified_evidence"
    end
    local actor,leader=snapshot.actor,snapshot.leader
    if not integer(actor,0,63) or not integer(leader,0,63) or actor==leader
        or snapshot.actorAliveMajor~=true or snapshot.leaderAliveAI~=true
        or snapshot.known~=true or not integer(snapshot.turn,0,LIMIT-30)
        or not integer(snapshot.sequence,1,LIMIT) then return nil,"invalid_participants" end
    local x,y=snapshot.x,snapshot.y
    if not integer(x,0,LIMIT) or not integer(y,0,LIMIT)
        or type(snapshot.noForeignSpread)~="boolean"
        or not integer(snapshot.unitReligion,0,LIMIT)
        or not integer(snapshot.leaderReligion,0,LIMIT) then return nil,"invalid_unit" end
    if snapshot.unitReligion==snapshot.leaderReligion then return nil,"same_faith" end
    local cells=snapshot.cells
    if type(cells)~="table" then return nil,"incomplete_map" end
    local cities,seen={},{}
    for i=0,6 do
        local cell=cells[i]
        if type(cell)~="table" or type(cell.exists)~="boolean" then return nil,"incomplete_map" end
        if i==0 and not cell.exists then return nil,"invalid_unit_plot" end
        if cell.exists then
            if not integer(cell.x,0,LIMIT) or not integer(cell.y,0,LIMIT)
                or cell.cityKnown~=true then return nil,"incomplete_map" end
            if i==0 and (cell.x~=x or cell.y~=y) then return nil,"invalid_unit_plot" end
            local city=cell.city
            if city~=nil and (type(city)~="table" or not integer(city.owner,0,63)
                or not integer(city.id,0,LIMIT) or not integer(city.beforeReligion,-1,LIMIT)) then
                return nil,"invalid_city"
            end
            local k=key(cell.x,cell.y)
            if seen[k] and not sameCity(cities[k],city) then return nil,"inconsistent_map" end
            seen[k]=true;cities[k]=city
        end
    end
    local function getAdjacent(_,_,direction)
        local cell=cells[direction+1]
        if not cell.exists then return nil end
        return {GetX=function() return cell.x end,GetY=function() return cell.y end}
    end
    local function getCity(cx,cy)
        local city=cities[key(cx,cy)]
        if city==nil then return nil end
        return {GetOwner=function() return city.owner end, data=city}
    end
    local ok,selected=pcall(target.find,x,y,actor,snapshot.noForeignSpread,getAdjacent,getCity)
    if not ok then return nil,"target_error" end
    if selected==nil or type(selected)~="table" or type(selected.data)~="table" then
        return nil,"no_eligible_target"
    end
    local city=selected.data
    if city.owner~=leader and city.beforeReligion~=snapshot.leaderReligion then
        return nil,"unprotected_city"
    end
    return {actor=actor,leader=leader,cityOwner=city.owner,cityID=city.id,
        beforeReligion=city.beforeReligion,leaderReligion=snapshot.leaderReligion,
        unitReligion=snapshot.unitReligion,known=true,alexanderAI=true,success=true,
        candidateCount=1},nil
end
return M

-- READ-ONLY DIAGNOSTIC, not part of the mod. Never changes game state.
-- Records bounded raw city/operation observations for every actor, plus a
-- bounded in-memory local ring printed around local spread operations. Raw
-- events are independent observations, not proof of conversion or causation.
-- Actual callback ordering, delivery and thread behavior remain empirical.
local RING_LIMIT, PRINT_LIMIT, WINDOW_LIMIT, POST_LIMIT = 64, 240, 3, 32
local ring, nextIndex, ringCount, serial, batch = {}, 1, 0, 0, 0
local printed, windows, active, postCount, completions = 0, 0, false, 0, 0
local rawLimits={city=512,local_spread=64,other_spread=512,unknown_spread=16}
local rawCounts={city=0,local_spread=0,other_spread=0,unknown_spread=0}
local operation=nil

local function emit(line)
    if printed >= PRINT_LIMIT then return end
    printed=printed+1
    if printed==PRINT_LIMIT then
        print("REMSELY_RELIGION_TRACE output_limit reached; further events omitted")
        return
    end
    print("REMSELY_RELIGION_TRACE " .. line)
end

local function finished()
    return windows>=WINDOW_LIMIT and not active
end

local function atom(value)
    local kind=type(value)
    if kind=="nil" then return "nil" end
    if kind=="number" or kind=="boolean" then return tostring(value) end
    if kind=="string" then
        return '"' .. value:sub(1,80):gsub('[\r\n"\\]', '?') .. '"'
    end
    -- Never traverse engine-owned objects or print user data through tostring.
    return "<" .. kind .. ">"
end

local function payload(...)
    local n=select("#",...)
    local parts={"argc=" .. tostring(n)}
    for i=1,math.min(n,10) do parts[#parts+1]="a" .. i .. "=" .. atom(select(i,...)) end
    if n>10 then parts[#parts+1]="truncated=true" end
    return table.concat(parts," ")
end

local function localPlayer()
    local ok,id=pcall(function() return Game.GetLocalPlayer() end)
    if ok and type(id)=="number" and id>=0 and id%1==0 then return id end
    return nil
end

local function turn()
    local ok,value=pcall(function() return Game.GetCurrentGameTurn() end)
    return ok and atom(value) or "unavailable"
end

-- One lookup only for a logged non-local spread operation, never a map scan.
-- It reflects state at delivery: no claim that this is the original position,
-- the pre-operation religion/charges, or the target city.
local function deliveryUnitSnapshot(owner,unit)
    local ok,present,x,y,faith,charges=pcall(function()
        local player=Players[owner]
        local unitObject=player and player:GetUnits():FindID(unit)
        if unitObject==nil then return false end
        local religion=unitObject:GetReligion()
        return true,unitObject:GetX(),unitObject:GetY(),
            religion and religion:GetReligionType(),religion and religion:GetSpreadCharges()
    end)
    if not ok or not present then return "delivery_snapshot=unavailable" end
    return "delivery_x=" .. atom(x) .. " delivery_y=" .. atom(y)
        .. " delivery_faith=" .. atom(faith) .. " delivery_charges=" .. atom(charges)
end

-- Separate budgets mean numerous city events or AI actions cannot consume the
-- local player's trace. Once exhausted, avoid formatting and further output.
local function raw(kind,...)
    local count,limit=rawCounts[kind],rawLimits[kind]
    if count>=limit then return end
    count=count+1;rawCounts[kind]=count
    local extra=""
    if kind=="other_spread" then
        local owner,unit=...
        extra=" " .. deliveryUnitSnapshot(owner,unit)
    end
    print("REMSELY_RELIGION_TRACE raw=" .. kind .. " n=" .. count
        .. " batch=" .. batch .. " turn=" .. turn() .. " " .. payload(...) .. extra)
    if count==limit then
        print("REMSELY_RELIGION_TRACE raw=" .. kind .. " limit=" .. limit
            .. " reached; further events omitted")
    end
end

local function rawFinished()
    return rawCounts.city>=rawLimits.city and rawCounts.local_spread>=rawLimits.local_spread
        and rawCounts.other_spread>=rawLimits.other_spread
        and rawCounts.unknown_spread>=rawLimits.unknown_spread
end

local function append(kind,...)
    serial=serial+1
    local line="seq=" .. serial .. " batch=" .. batch .. " turn=" .. turn()
        .. " event=" .. kind .. " " .. payload(...)
    ring[nextIndex]=line
    nextIndex=nextIndex%RING_LIMIT+1
    ringCount=math.min(RING_LIMIT,ringCount+1)
    if active and postCount<POST_LIMIT then
        postCount=postCount+1
        emit("window=" .. windows .. " phase=after " .. line)
        if postCount==POST_LIMIT then
            emit("window=" .. windows .. " end reason=post_limit")
            active=false
        end
    end
end

local function beginWindow(owner)
    if active or windows>=WINDOW_LIMIT then return end
    windows=windows+1;active=true;postCount=0;completions=0
    emit("window=" .. windows .. " begin local=" .. owner .. " ring=" .. ringCount)
    local start=(nextIndex-ringCount-1)%RING_LIMIT+1
    for offset=0,ringCount-1 do
        local index=(start+offset-1)%RING_LIMIT+1
        emit("window=" .. windows .. " phase=before " .. ring[index])
    end
end

local function onMoved(kind,owner,...)
    if finished() then return end
    local localID=localPlayer()
    if localID~=nil and owner==localID then append(kind,owner,...) end
end
local function onSyncMove(owner,...) onMoved("sync_move",owner,...) end
local function onMove(owner,...) onMoved("unit_moved",owner,...) end
local function onTeleport(owner,...) onMoved("unit_teleported",owner,...) end
-- UnitChargesChanged is not specific to religion. Keep its unmodified payload
-- solely for the local player; do not infer the operation or access the unit.
local function onCharges(owner,...) onMoved("unit_charges_changed",owner,...) end
local function onCityReligion(...)
    raw("city",...)
    if operation==nil or finished() then return end
    append("city_religion_changed",...)
end
local function onPublish(...)
    if (finished() and rawFinished()) or (operation==nil and rawCounts.city>=rawLimits.city) then return end
    batch=batch+1
    -- No output on unrelated publication; preserve a marker only when a
    -- tracked event happened in the immediately preceding packet.
    if active then
        append("publish_complete",...)
        completions=completions+1
        if active and completions>=2 then
            emit("window=" .. windows .. " end reason=publish_limit")
            active=false
        end
    end
end

do
    local ok,value=pcall(function()
        local entry=GameInfo.UnitOperations["UNITOPERATION_SPREAD_RELIGION"]
        return entry and entry.Hash
    end)
    if ok and type(value)=="number" then operation=value end
end
local function onOperation(owner,unit,op,...)
    if operation==nil or op~=operation then return end
    if finished() and rawCounts.local_spread>=rawLimits.local_spread
        and rawCounts.other_spread>=rawLimits.other_spread
        and rawCounts.unknown_spread>=rawLimits.unknown_spread then return end
    local localID=localPlayer()
    local category=localID==nil and "unknown_spread"
        or (owner==localID and "local_spread" or "other_spread")
    raw(category,owner,unit,op,...)
    if finished() or localID==nil or owner~=localID then return end
    beginWindow(localID)
    append("spread_operation",owner,unit,op,...)
    if not active then return end
    -- Read once per relevant operation, never on movement or for AI units.
    -- These are values *at callback delivery*, not pre-operation state or a
    -- claim about the target city; the last charge can already be removed.
    local ok,x,y,faith,charges=pcall(function()
        local player=Players[owner]
        local unitObject=player and player:GetUnits():FindID(unit)
        if unitObject==nil then return nil,nil,nil,nil end
        local religion=unitObject:GetReligion()
        return unitObject:GetX(),unitObject:GetY(),
            religion and religion:GetReligionType(),religion and religion:GetSpreadCharges()
    end)
    if ok then append("spread_snapshot_delivery",owner,unit,x,y,faith,charges)
    else append("spread_snapshot_delivery",owner,unit,"unavailable") end
end

local registrations={}
local function add(namespace,name,handler)
    local ok,event=pcall(function() return namespace and namespace[name] end)
    if not ok or event==nil then registrations[#registrations+1]=name .. ":missing";return end
    local attached=pcall(function() event.Add(handler) end)
    registrations[#registrations+1]=name .. (attached and ":registered" or ":failed")
end
if operation~=nil then
    add(GameEvents,"OnUnitMoved",onSyncMove)
    add(Events,"UnitMoved",onMove)
    add(Events,"UnitTeleported",onTeleport)
    add(Events,"UnitChargesChanged",onCharges)
    add(Events,"UnitOperationStarted",onOperation)
end
-- A missing operation hash must not disable independent city observations.
add(Events,"CityReligionChanged",onCityReligion)
add(Events,"GameCoreEventPublishComplete",onPublish)
emit("ready operation=" .. atom(operation) .. " local=" .. atom(localPlayer())
    .. " registrations=" .. table.concat(registrations,",")
    .. " ring_limit=" .. RING_LIMIT .. " window_line_limit=" .. PRINT_LIMIT
    .. " raw_limits=city:512,local_spread:64,other_spread:512,unknown_spread:16")

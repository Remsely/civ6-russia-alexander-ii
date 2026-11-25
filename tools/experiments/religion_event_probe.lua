-- Temporary read-only probe for the native UnitOperationStarted delivery.
-- This file is not included in the release mod and never writes game state.
-- Output is bounded and only emitted for actual spread-operation events.
local remaining = 8
-- UnitOperationTypes.SPREAD_RELIGION was nil in gameplay Lua in an actual
-- session. UnitOperationStarted carries the operation hash, not the row index.
-- This row's Hash matches the examined GameCore build's registered operation;
-- event delivery and availability of this field in gameplay remain unproven.
local operations = GameInfo and GameInfo.UnitOperations
local definition = operations and operations["UNITOPERATION_SPREAD_RELIGION"]
local operation = definition and definition.Hash
if type(operation) ~= "number" then operation = nil end

local function atom(value)
    if value == nil then return "nil" end
    return tostring(value)
end

local function cityAt(x, y)
    return CityManager.GetCityAt(x, y)
end

local function targetAt(x, y, owner, noForeignSpread)
    local city = cityAt(x, y)
    if city and city:GetOwner() == owner then return city end
    for direction = 0, 5 do
        local plot = Map.GetAdjacentPlot(x, y, direction)
        if plot then
            city = cityAt(plot:GetX(), plot:GetY())
            if city and (not noForeignSpread or city:GetOwner() == owner) then
                return city
            end
        end
    end
    return nil
end

local function inspect(ownerID, unitID)
    local turn = Game.GetCurrentGameTurn()
    local player = Players[ownerID]
    local units = player and player:GetUnits()
    local unit = units and units:FindID(unitID)
    local base = "turn=" .. atom(turn) .. " actor=" .. atom(ownerID) .. " unit=" .. atom(unitID)
    if not unit then return base .. " present=false" end
    local religion = unit:GetReligion()
    if not religion then return base .. " present=true religion=unavailable" end
    local faith = religion:GetReligionType()
    local noForeignSpread = religion:IsNoForeignSpread()
    if type(noForeignSpread) ~= "boolean" then return base .. " present=true restriction=unavailable" end
    local x, y = unit:GetX(), unit:GetY()
    local city = targetAt(x, y, ownerID, noForeignSpread)
    local result = base .. " present=true x=" .. atom(x) .. " y=" .. atom(y)
        .. " faith=" .. atom(faith) .. " no_foreign=" .. atom(noForeignSpread)
        .. " charges=" .. atom(religion:GetSpreadCharges())
    if not city then return result .. " target=none" end
    local cityReligion = city:GetReligion()
    return result .. " target_owner=" .. atom(city:GetOwner()) .. " target_city=" .. atom(city:GetID())
        .. " majority=" .. atom(cityReligion and cityReligion:GetMajorityReligion())
end

local function onOperation(ownerID, unitID, operationID)
    if remaining <= 0 or operation == nil or operationID ~= operation then return end
    remaining = remaining - 1
    local ok, result = pcall(inspect, ownerID, unitID)
    print("REMSELY RELIGION PROBE " .. (ok and result or ("error=" .. atom(result))))
end

if operation ~= nil and Events.UnitOperationStarted then
    Events.UnitOperationStarted.Add(onOperation)
    print("REMSELY RELIGION PROBE ready operation=" .. atom(operation) .. " limit=8")
else
    print("REMSELY RELIGION PROBE unavailable operation=" .. atom(operation))
end

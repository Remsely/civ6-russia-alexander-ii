--==========================================================================================================================
-- Remsely's Alexander II: Great Reforms, Farm adjacency (docs/remselys-alexander-ii.md, 3.1)
-- Farms get +1 Production per 2 adjacent Farms (max +2 at 4). Only Farms count as neighbours.
--
-- XML cannot count adjacent improvements, so this script keeps two plot properties up to date and the XML modifiers
-- (Data/GameDefines.sql) read them: one for "2+ adjacent Farms", one for "4+ adjacent Farms". The properties are set for
-- every Farm regardless of owner; the modifiers only exist for Alexander II players, so only they get the Production.
--==========================================================================================================================
local DEBUG = false -- set true to write every recalculation to Lua.log
local PROPERTY_2 = "REMSELY_FARM_ADJ_2"
local PROPERTY_4 = "REMSELY_FARM_ADJ_4"

local FARM = GameInfo.Improvements["IMPROVEMENT_FARM"]
if FARM == nil then return end
local FARM_INDEX = FARM.Index

local function IsFarm(plot)
	return plot ~= nil and plot:GetImprovementType() == FARM_INDEX
end

-- skipX/skipY: a plot that is being cleared and must not count as a Farm (its improvement may still be readable)
local function CountAdjacentFarms(x, y, skipX, skipY)
	local count = 0
	for direction = 0, DirectionTypes.NUM_DIRECTION_TYPES - 1, 1 do
		local adjacent = Map.GetAdjacentPlot(x, y, direction)
		if IsFarm(adjacent) and not (adjacent:GetX() == skipX and adjacent:GetY() == skipY) then
			count = count + 1
		end
	end
	return count
end

local function RefreshPlot(plot, skipX, skipY)
	if plot == nil then return end
	local near2, near4 = 0, 0
	if IsFarm(plot) and not (plot:GetX() == skipX and plot:GetY() == skipY) then
		local count = CountAdjacentFarms(plot:GetX(), plot:GetY(), skipX, skipY)
		if count >= 2 then near2 = 1 end
		if count >= 4 then near4 = 1 end
	end
	if (plot:GetProperty(PROPERTY_2) or 0) ~= near2 then plot:SetProperty(PROPERTY_2, near2) end
	if (plot:GetProperty(PROPERTY_4) or 0) ~= near4 then plot:SetProperty(PROPERTY_4, near4) end
	if DEBUG then
		print(string.format("REMSELY_FARMS: plot (%d,%d) farm=%s adjacentFarms=%d -> adj2=%d adj4=%d",
			plot:GetX(), plot:GetY(), tostring(IsFarm(plot)), CountAdjacentFarms(plot:GetX(), plot:GetY(), skipX, skipY), near2, near4))
	end
end

-- Refresh the plot itself and its neighbours (a changed Farm alters the count of every plot around it)
local function RefreshAround(x, y, skipX, skipY)
	RefreshPlot(Map.GetPlot(x, y), skipX, skipY)
	for direction = 0, DirectionTypes.NUM_DIRECTION_TYPES - 1, 1 do
		RefreshPlot(Map.GetAdjacentPlot(x, y, direction), skipX, skipY)
	end
end

local function OnImprovementAddedToMap(plotX, plotY, improvementID)
	if DEBUG then print(string.format("REMSELY_FARMS: ImprovementAddedToMap (%d,%d) improvementID=%s farmIndex=%s", plotX, plotY, tostring(improvementID), tostring(FARM_INDEX))) end
	RefreshAround(plotX, plotY)
end

local function OnImprovementRemovedFromMap(plotX, plotY)
	if DEBUG then print(string.format("REMSELY_FARMS: ImprovementRemovedFromMap (%d,%d)", plotX, plotY)) end
	RefreshAround(plotX, plotY, plotX, plotY)
end

if DEBUG then print("REMSELY_FARMS: script loaded, farm index " .. tostring(FARM_INDEX)) end

Events.ImprovementAddedToMap.Add(OnImprovementAddedToMap)
Events.ImprovementRemovedFromMap.Add(OnImprovementRemovedFromMap)

-- One full pass at load, so a mod added to an existing game (or a different Farm layout in a save) is picked up
for index = 0, Map.GetPlotCount() - 1, 1 do
	local plot = Map.GetPlotByIndex(index)
	if IsFarm(plot) or (plot ~= nil and (plot:GetProperty(PROPERTY_2) or 0) ~= 0) then
		RefreshPlot(plot)
	end
end

--==========================================================================================================================
-- Remsely's Russian Empire: Alexander II - Great Reforms, Railway Network (docs/ru/design.md, 3.3)
-- Every own city gets +1 Production for each own city and +1 Gold for each foreign city connected to it by a
-- continuous railroad; EACH bonus is capped by the city's Population (a 10-Pop city counts at most 10 connected
-- cities per bonus - the user's rule). Two cities are connected when an unbroken path of railroad plots leads
-- from center to center; city centers are junctions, so a line may pass through a city and even tie two networks
-- together. Whoever built the rails does not matter - transit counts. The Capital is an ordinary city here: it
-- receives bonuses like any other.
--
-- XML cannot see routes or count connected cities, so this script keeps two plot properties up to date on the centers
-- of own cities and the XML modifiers (Data/GameDefines.sql) read them:
--   REMSELY_RAIL_OWN_N     - own cities railroad-connected to this city (the city itself excluded), capped by Population
--   REMSELY_RAIL_FOREIGN_N - foreign cities (any other player, city-states included) railroad-connected, capped by Population
-- Recomputed on every route, city and population event, at turn start and once at load.
--==========================================================================================================================
local DEBUG = false -- set true to write every recalculation to Lua.log
local PROPERTY_OWN = "REMSELY_RAIL_OWN_N"
local PROPERTY_FOREIGN = "REMSELY_RAIL_FOREIGN_N"
local PROPERTY_CONNECTED_LEGACY = "REMSELY_RAIL_CONNECTED" -- written by the pre-rework script; wiped on load
local MAX_TIER = 200 -- technical bound of the tier machinery, NOT a design cap; 200 rail-connected cities is beyond any conceivable game

local RAILROAD = GameInfo.Routes["ROUTE_RAILROAD"]
if RAILROAD == nil then return end -- Gathering Storm only; the mod already requires it
local RAIL_INDEX = RAILROAD.Index

-- registry[playerID] = { [plotIndex] = true }: plots this player's properties currently sit on (cleared before recompute)
local registry = {}

local function ClearPlayer(playerID)
	local reg = registry[playerID]
	if reg == nil then return end
	for plotIndex in pairs(reg) do
		local plot = Map.GetPlotByIndex(plotIndex)
		if plot ~= nil then
			plot:SetProperty(PROPERTY_OWN, 0)
			plot:SetProperty(PROPERTY_FOREIGN, 0)
		end
	end
	registry[playerID] = nil
end

local function RecomputePlayer(playerID, player)
	ClearPlayer(playerID)

	-- Population of own cities: each bonus counts at most as many connected cities as the city's Population
	local popByPlot = {}
	for _, city in player:GetCities():Members() do
		local cityPlot = Map.GetPlot(city:GetLocation())
		if cityPlot ~= nil then popByPlot[cityPlot:GetIndex()] = city:GetPopulation() end
	end

	-- One pass over the map: railroad plots and city centers
	local railComponent = {} -- [railPlotIndex] = component id (0 = not yet assigned)
	local cityOwner = {}     -- [cityPlotIndex] = owner id
	for index = 0, Map.GetPlotCount() - 1, 1 do
		local plot = Map.GetPlotByIndex(index)
		if plot ~= nil then
			if plot:GetRouteType() == RAIL_INDEX then railComponent[index] = 0 end
			if plot:IsCity() then
				local owner = plot:GetOwner()
				if owner ~= nil and owner >= 0 then cityOwner[index] = owner end
			end
		end
	end

	-- Connected components of railroad plots
	local componentCount = 0
	for startIndex in pairs(railComponent) do
		if railComponent[startIndex] == 0 then
			componentCount = componentCount + 1
			railComponent[startIndex] = componentCount
			local queue = { startIndex }
			local head = 0
			while head < #queue do
				head = head + 1
				local plot = Map.GetPlotByIndex(queue[head])
				local x, y = plot:GetX(), plot:GetY()
				for direction = 0, DirectionTypes.NUM_DIRECTION_TYPES - 1 do
					local neighbor = Map.GetAdjacentPlot(x, y, direction)
					if neighbor ~= nil then
						local nIndex = neighbor:GetIndex()
						if railComponent[nIndex] == 0 then
							railComponent[nIndex] = componentCount
							queue[#queue + 1] = nIndex
						end
					end
				end
			end
		end
	end

	-- A city touches a component when its center carries a rail or is adjacent to a railroad plot of that component
	local cityComps = {}  -- [cityPlotIndex] = { [component id] = true }
	local compCities = {} -- [component id] = { [cityPlotIndex] = owner id }
	local function Touch(cityIndex, component)
		local comps = cityComps[cityIndex]
		if comps == nil then
			comps = {}
			cityComps[cityIndex] = comps
		end
		if not comps[component] then
			comps[component] = true
			local cities = compCities[component]
			if cities == nil then
				cities = {}
				compCities[component] = cities
			end
			cities[cityIndex] = cityOwner[cityIndex]
		end
	end
	for cityIndex in pairs(cityOwner) do
		local component = railComponent[cityIndex]
		if component ~= nil then Touch(cityIndex, component) end
		local plot = Map.GetPlotByIndex(cityIndex)
		local x, y = plot:GetX(), plot:GetY()
		for direction = 0, DirectionTypes.NUM_DIRECTION_TYPES - 1 do
			local neighbor = Map.GetAdjacentPlot(x, y, direction)
			if neighbor ~= nil then
				local nComponent = railComponent[neighbor:GetIndex()]
				if nComponent ~= nil then Touch(cityIndex, nComponent) end
			end
		end
	end

	-- For every own city: every city reachable over rails (cities are junctions, so the walk alternates
	-- city -> its components -> their cities -> ... until the network closes)
	for cityIndex, owner in pairs(cityOwner) do
		if owner == playerID then
			local own, foreign = 0, 0
			local seenCities = { [cityIndex] = true }
			local seenComps = {}
			local queue = { cityIndex }
			local head = 0
			while head < #queue do
				head = head + 1
				local reachedCity = queue[head]
				for component in pairs(cityComps[reachedCity] or {}) do
					if not seenComps[component] then
						seenComps[component] = true
						for otherIndex, otherOwner in pairs(compCities[component]) do
							if not seenCities[otherIndex] then
								seenCities[otherIndex] = true
								queue[#queue + 1] = otherIndex
								if otherOwner == playerID then own = own + 1
								else foreign = foreign + 1 end
							end
						end
					end
				end
			end
			if own > MAX_TIER then own = MAX_TIER end
			if foreign > MAX_TIER then foreign = MAX_TIER end
			local population = popByPlot[cityIndex] or 1
			if own > population then own = population end
			if foreign > population then foreign = population end
			local plot = Map.GetPlotByIndex(cityIndex)
			plot:SetProperty(PROPERTY_OWN, own)
			plot:SetProperty(PROPERTY_FOREIGN, foreign)
			registry[playerID] = registry[playerID] or {}
			registry[playerID][cityIndex] = true
		end
	end
	if DEBUG then
		print(string.format("REMSELY_RAILWAYS: player %d recompute done, %d rail components", playerID, componentCount))
	end
end

local function RecomputeAll()
	for playerID = 0, PlayerManager.GetWasEverAliveCount() - 1, 1 do
		local player = Players[playerID]
		if player ~= nil and player:IsAlive()
			and PlayerConfigurations[playerID]:GetLeaderTypeName() == "LEADER_REMSELY_ALEXANDER_II" then
			RecomputePlayer(playerID, player)
		end
	end
end

if DEBUG then print("REMSELY_RAILWAYS: script loaded, railroad index " .. tostring(RAIL_INDEX)) end

-- A rail or city event means the network may have changed; TurnBegin sweeps up anything the events missed
-- (ownership flips, city growth into new plots). Handlers ignore the event arguments and recompute everything.
local function OnNetworkChanged() RecomputeAll() end
if Events.RouteAddedToMap then Events.RouteAddedToMap.Add(OnNetworkChanged) end
if Events.RouteChanged then Events.RouteChanged.Add(OnNetworkChanged) end
if Events.RouteRemovedFromMap then Events.RouteRemovedFromMap.Add(OnNetworkChanged) end
if Events.CityAddedToMap then Events.CityAddedToMap.Add(OnNetworkChanged) end
if Events.CityRemovedFromMap then Events.CityRemovedFromMap.Add(OnNetworkChanged) end
if Events.CityPopulationChanged then Events.CityPopulationChanged.Add(OnNetworkChanged) end
if Events.TurnBegin then Events.TurnBegin.Add(OnNetworkChanged) end

-- One full pass at load: clear anything a save carries over (including the legacy property of the pre-rework
-- capital-tree script), then rebuild (like the Farm script's load pass)
for index = 0, Map.GetPlotCount() - 1, 1 do
	local plot = Map.GetPlotByIndex(index)
	if plot ~= nil then
		if (plot:GetProperty(PROPERTY_OWN) or 0) ~= 0 then plot:SetProperty(PROPERTY_OWN, 0) end
		if (plot:GetProperty(PROPERTY_FOREIGN) or 0) ~= 0 then plot:SetProperty(PROPERTY_FOREIGN, 0) end
		if (plot:GetProperty(PROPERTY_CONNECTED_LEGACY) or 0) ~= 0 then plot:SetProperty(PROPERTY_CONNECTED_LEGACY, 0) end
	end
end
RecomputeAll()

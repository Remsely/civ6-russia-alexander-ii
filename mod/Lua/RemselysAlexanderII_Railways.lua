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
--   REMSELY_RAIL_OWN_BIT_<1..128> and REMSELY_RAIL_FOREIGN_BIT_<1..128>
-- encode the respective capped counts as binary flags. Cached rail/city topology
-- avoids rebuilding the graph when event replays do not change it.
--==========================================================================================================================
local DEBUG = false -- set true to write every recalculation to Lua.log
local PROPERTY_OWN = "REMSELY_RAIL_OWN_N"
local PROPERTY_FOREIGN = "REMSELY_RAIL_FOREIGN_N"
local PROPERTY_CONNECTED_LEGACY = "REMSELY_RAIL_CONNECTED" -- written by the pre-rework script; wiped on load
local BIT_WEIGHTS = {1, 2, 4, 8, 16, 32, 64, 128}
local OWN_PREFIX = "REMSELY_RAIL_OWN_BIT_"
local FOREIGN_PREFIX = "REMSELY_RAIL_FOREIGN_BIT_"
local MAX_TIER = 200 -- technical bound of the tier machinery, NOT a design cap; 200 rail-connected cities is beyond any conceivable game

local RAILROAD = GameInfo.Routes["ROUTE_RAILROAD"]
if RAILROAD == nil then return end -- Gathering Storm only; the mod already requires it
local RAIL_INDEX = RAILROAD.Index

-- registry[playerID] = { [plotIndex] = true }: plots this player's properties currently sit on.
local registry = {}
local knownRails = nil
local knownCities = nil
local migrationPending = true
local InitializeMapState

-- The gameplay script is loaded even in games without this leader. Avoid map
-- scans in those games (and while he is eliminated). Forget the snapshot so a
-- revived Alexander is rebuilt from the actual map on the next relevant event.
local function HasLivingAlexander()
	for playerID = 0, PlayerManager.GetWasEverAliveCount() - 1, 1 do
		local player = Players[playerID]
		local config = PlayerConfigurations[playerID]
		if player ~= nil and player:IsAlive() and config ~= nil
			and config:GetLeaderTypeName() == "LEADER_REMSELY_ALEXANDER_II" then
			if migrationPending and InitializeMapState ~= nil then
				migrationPending = false
				InitializeMapState()
			end
			return true
		end
	end
	knownRails, knownCities = nil, nil
	return false
end

-- Snapshot route and city centres once. Subsequent graph builds operate on
-- these sparse sets instead of repeatedly scanning every map tile.
local function ReadTopology()
	local rails, cities = {}, {}
	for index = 0, Map.GetPlotCount() - 1 do
		local plot = Map.GetPlotByIndex(index)
		if plot ~= nil then
			if plot:GetRouteType() == RAIL_INDEX then rails[index] = true end
			if plot:IsCity() then
				local owner = plot:GetOwner()
				if owner ~= nil and owner >= 0 then cities[index] = owner end
			end
		end
	end
	return rails, cities
end

local function EqualSets(a, b)
	for key, value in pairs(a) do if b[key] ~= value then return false end end
	for key, value in pairs(b) do if a[key] ~= value then return false end end
	return true
end

local function ReadRails()
	local rails = {}
	for index = 0, Map.GetPlotCount() - 1 do
		local plot = Map.GetPlotByIndex(index)
		if plot ~= nil and plot:GetRouteType() == RAIL_INDEX then rails[index] = true end
	end
	return rails
end

local function SetIfChanged(plot, property, value)
	if (plot:GetProperty(property) or 0) ~= value then
		plot:SetProperty(property, value)
	end
end

local function SetBits(plot, prefix, value)
	for _, bit in ipairs(BIT_WEIGHTS) do
		SetIfChanged(plot, prefix .. bit, math.floor(value / bit) % 2)
	end
end

local function RecomputePlayer(playerID, player)
	local previous = registry[playerID] or {}
	local current = {}

	-- Population of own cities: each bonus counts at most as many connected cities as the city's Population
	local popByPlot = {}
	for _, city in player:GetCities():Members() do
		local cityPlot = Map.GetPlot(city:GetLocation())
		if cityPlot ~= nil then popByPlot[cityPlot:GetIndex()] = city:GetPopulation() end
	end

	-- Build connected components from the cached sparse topology.
	local railComponent = {} -- [railPlotIndex] = component id (0 = not yet assigned)
	local cityOwner = knownCities
	for index in pairs(knownRails) do railComponent[index] = 0 end

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

	-- Traverse each connected city/component group once rather than repeating the
	-- same breadth-first search for every city in that network.
	local visitedCities, visitedComps = {}, {}
	for cityIndex, owner in pairs(cityOwner) do
		if not visitedCities[cityIndex] then
			local counts, group = {}, {}
			visitedCities[cityIndex] = true
			local queue = { cityIndex }
			local head = 0
			while head < #queue do
				head = head + 1
				local reachedCity = queue[head]
				group[#group + 1] = reachedCity
				local reachedOwner = cityOwner[reachedCity]
				counts[reachedOwner] = (counts[reachedOwner] or 0) + 1
				for component in pairs(cityComps[reachedCity] or {}) do
					if not visitedComps[component] then
						visitedComps[component] = true
						for otherIndex in pairs(compCities[component]) do
							if not visitedCities[otherIndex] then
								visitedCities[otherIndex] = true
								queue[#queue + 1] = otherIndex
							end
						end
					end
				end
			end
			local ownCount = counts[playerID] or 0
			for _, member in ipairs(group) do
				if cityOwner[member] == playerID then
					local population = popByPlot[member] or 1
					local own = math.min(ownCount - 1, MAX_TIER, population)
					local foreign = math.min(#group - ownCount, MAX_TIER, population)
					local plot = Map.GetPlotByIndex(member)
					SetBits(plot, OWN_PREFIX, own)
					SetBits(plot, FOREIGN_PREFIX, foreign)
					current[member] = true
				end
			end
		end
	end
	for cityIndex in pairs(previous) do
		if not current[cityIndex] then
			local plot = Map.GetPlotByIndex(cityIndex)
			local newOwner = cityOwner[cityIndex]
			local newConfig = newOwner and PlayerConfigurations[newOwner]
			-- Another Alexander may already have refreshed this captured city.
			if plot ~= nil and not (newConfig and newConfig:GetLeaderTypeName() == 'LEADER_REMSELY_ALEXANDER_II') then
				SetBits(plot, OWN_PREFIX, 0)
				SetBits(plot, FOREIGN_PREFIX, 0)
			end
		end
	end
	registry[playerID] = current
	if DEBUG then
		print(string.format("REMSELY_RAILWAYS: player %d recompute done, %d rail components", playerID, componentCount))
	end
end

local function RecomputeAll()
	if knownRails == nil then knownRails, knownCities = ReadTopology() end
	for playerID = 0, PlayerManager.GetWasEverAliveCount() - 1, 1 do
		local player = Players[playerID]
		if player ~= nil and player:IsAlive()
			and PlayerConfigurations[playerID]:GetLeaderTypeName() == "LEADER_REMSELY_ALEXANDER_II" then
			RecomputePlayer(playerID, player)
		end
	end
end

if DEBUG then print("REMSELY_RAILWAYS: script loaded, railroad index " .. tostring(RAIL_INDEX)) end

-- City and undocumented route events use a conservative snapshot comparison;
-- TurnBegin sweeps up ownership changes even when a city event arrives early.
local function OnNetworkChanged()
	if not HasLivingAlexander() then return end
	local rails, cities = ReadTopology()
	if knownRails == nil or not EqualSets(knownRails, rails) or not EqualSets(knownCities, cities) then
		knownRails, knownCities = rails, cities
		RecomputeAll()
	end
end
-- The add/remove events have no documented coordinates. Scan only route
-- types, and rebuild the sparse graph only if a rail changed.
local function OnUnknownRouteChanged()
	if not HasLivingAlexander() then return end
	local rails = ReadRails()
	if knownRails == nil then
		knownRails, knownCities = ReadTopology(); RecomputeAll()
	elseif not EqualSets(knownRails, rails) then
		knownRails = rails; RecomputeAll()
	end
end
-- RouteChanged reports coordinates in vanilla. Other route events have no
-- documented signature, so unknown coordinates take the conservative path.
local function OnRouteChanged(x, y)
	if not HasLivingAlexander() then return end
	if type(x) ~= 'number' or type(y) ~= 'number' or knownRails == nil then
		OnNetworkChanged(); return
	end
	local plot = Map.GetPlot(x, y)
	if plot == nil then OnNetworkChanged(); return end
	local old = knownRails[plot:GetIndex()] == true
	local new = plot:GetRouteType() == RAIL_INDEX
	if old ~= new then knownRails[plot:GetIndex()] = new and true or nil; RecomputeAll() end
end
-- Other cities' populations do not affect our per-city population caps.
local function OnPopulationChanged(playerID)
	if not HasLivingAlexander() then return end
	local config = PlayerConfigurations[playerID]
	if config ~= nil and config:GetLeaderTypeName() == "LEADER_REMSELY_ALEXANDER_II" then
		RecomputeAll()
	end
end
-- Vanilla CityAddedToMap supplies player, city, x and y. Replay during load
-- is a no-op when the startup snapshot already contains this centre.
local function OnCityAdded(playerID, cityID, x, y)
	if not HasLivingAlexander() then return end
	if type(x) ~= 'number' or type(y) ~= 'number' or knownCities == nil then
		OnNetworkChanged(); return
	end
	local plot = Map.GetPlot(x, y)
	if not plot then OnNetworkChanged(); return end
	local owner = plot:IsCity() and plot:GetOwner() or nil
	if owner and owner < 0 then owner = nil end
	local index = plot:GetIndex()
	if knownCities[index] ~= owner then
		knownCities[index] = owner
		RecomputeAll()
	end
end
if Events.RouteAddedToMap then Events.RouteAddedToMap.Add(OnUnknownRouteChanged) end
if Events.RouteChanged then Events.RouteChanged.Add(OnRouteChanged) end
if Events.RouteRemovedFromMap then Events.RouteRemovedFromMap.Add(OnUnknownRouteChanged) end
if Events.CityAddedToMap then Events.CityAddedToMap.Add(OnCityAdded) end
if Events.CityRemovedFromMap then Events.CityRemovedFromMap.Add(OnNetworkChanged) end
if Events.CityPopulationChanged then Events.CityPopulationChanged.Add(OnPopulationChanged) end
-- A turn sweep refreshes captured cities even when a city event arrived before
-- its owner changed. Recompute even for unchanged topology to refresh caps.
local function OnTurnBegin()
	if not HasLivingAlexander() then return end
	knownRails, knownCities = ReadTopology()
	RecomputeAll()
end
if Events.TurnBegin then Events.TurnBegin.Add(OnTurnBegin) end

-- Run migration once when a living Alexander is present, including after a
-- revival. Games without him need neither an initial map pass nor event scans.
InitializeMapState = function()
	for index = 0, Map.GetPlotCount() - 1, 1 do
		local plot = Map.GetPlotByIndex(index)
		if plot ~= nil then
			if (plot:GetProperty(PROPERTY_OWN) or 0) ~= 0 then plot:SetProperty(PROPERTY_OWN, 0) end
			if (plot:GetProperty(PROPERTY_FOREIGN) or 0) ~= 0 then plot:SetProperty(PROPERTY_FOREIGN, 0) end
			if (plot:GetProperty(PROPERTY_CONNECTED_LEGACY) or 0) ~= 0 then plot:SetProperty(PROPERTY_CONNECTED_LEGACY, 0) end
			-- Clear stale saved bits on non-Alexander city plots and rebuild below.
			-- Keep valid saved bits in place to avoid a burst of modifier updates.
			if plot:IsCity() then
				local owner = plot:GetOwner()
				local config = owner and PlayerConfigurations[owner]
				if not config or config:GetLeaderTypeName() ~= 'LEADER_REMSELY_ALEXANDER_II' then
					SetBits(plot, OWN_PREFIX, 0); SetBits(plot, FOREIGN_PREFIX, 0)
				end
			end
		end
	end
	knownRails, knownCities = ReadTopology()
	RecomputeAll()
end
HasLivingAlexander()

--==========================================================================================================================
-- Remsely's Alexander II: Great Reforms, Railway Network (docs/ru/design.md, 3.3)
-- Cities connected to the Capital by a continuous railroad get +1 Production each and +1 Gold per foreign connected
-- city - uncapped, per the user's explicit decision (MAX_FOREIGN below is only a technical bound for the tier machinery,
-- far beyond any real game). A city is connected when its center belongs to the railroad tree grown from the Capital's
-- center: the tree walks railroad plots, and connected city centers act as junctions (a line may pass through a city).
-- Whoever built the rails does not matter - transit counts. The Capital is the origin and never bonuses itself.
--
-- XML cannot see routes or count connected cities, so this script keeps two plot properties up to date and the XML
-- modifiers (Data/GameDefines.sql) read them, exactly like the Farm adjacency script:
--   REMSELY_RAIL_CONNECTED  - 1 on the center of each connected own city (non-capital)
--   REMSELY_RAIL_FOREIGN_N  - number of foreign connected cities on the same centers (bounded by MAX_FOREIGN)
-- Recomputed on every route and city event, at turn start and once at load.
--==========================================================================================================================
local DEBUG = false -- set true to write every recalculation to Lua.log
local PROPERTY_CONNECTED = "REMSELY_RAIL_CONNECTED"
local PROPERTY_FOREIGN = "REMSELY_RAIL_FOREIGN_N"
local MAX_FOREIGN = 200 -- technical bound of the tier machinery, NOT a design cap; 200 rail-connected foreign cities is beyond any conceivable game

local RAILROAD = GameInfo.Routes["ROUTE_RAILROAD"]
if RAILROAD == nil then return end -- Gathering Storm only; the mod already requires it
local RAIL_INDEX = RAILROAD.Index

-- registry[playerID] = { [plotIndex] = true }: plots this player's properties currently sit on (cleared before recompute)
local registry = {}

local function IsRail(plot)
	return plot ~= nil and plot:GetRouteType() == RAIL_INDEX
end

local function ClearPlayer(playerID)
	local reg = registry[playerID]
	if reg == nil then return end
	for plotIndex in pairs(reg) do
		local plot = Map.GetPlotByIndex(plotIndex)
		if plot ~= nil then
			plot:SetProperty(PROPERTY_CONNECTED, 0)
			plot:SetProperty(PROPERTY_FOREIGN, 0)
		end
	end
	registry[playerID] = nil
end

local function RecomputePlayer(playerID, player)
	ClearPlayer(playerID)
	local capital = player:GetCities():GetCapitalCity()
	if capital == nil then return end
	local capPlot = Map.GetPlot(capital:GetLocation())
	if capPlot == nil then return end
	local capIndex = capPlot:GetIndex()

	-- Breadth-first walk of the railroad tree. Nodes are railroad plots and city centers reached by the network;
	-- centers are junctions, so a line may pass through a city even if the center plot itself carries no rail.
	local visited = { [capIndex] = true }
	local queue = { capIndex }
	local centers = {} -- [plotIndex] = plot, every city center the tree reaches (including the Capital)
	local head = 0
	while head < #queue do
		head = head + 1
		local plot = Map.GetPlotByIndex(queue[head])
		local x, y = plot:GetX(), plot:GetY()
		for direction = 0, DirectionTypes.NUM_DIRECTION_TYPES - 1 do
			local neighbor = Map.GetAdjacentPlot(x, y, direction)
			if neighbor ~= nil then
				local index = neighbor:GetIndex()
				if not visited[index] and (IsRail(neighbor) or neighbor:IsCity()) then
					visited[index] = true
					queue[#queue + 1] = index
					if neighbor:IsCity() then centers[index] = neighbor end
				end
			end
		end
	end

	-- Foreign connected cities counted once each; own connected centers stamped (the Capital is the origin, not a stop)
	local foreign = 0
	local own = {}
	for _, plot in pairs(centers) do
		local owner = plot:GetOwner()
		if owner == playerID then
			if plot:GetIndex() ~= capIndex then own[#own + 1] = plot end
		elseif owner ~= nil and owner >= 0 then
			foreign = foreign + 1
		end
	end
	if foreign > MAX_FOREIGN then foreign = MAX_FOREIGN end

	for _, plot in ipairs(own) do
		plot:SetProperty(PROPERTY_CONNECTED, 1)
		plot:SetProperty(PROPERTY_FOREIGN, foreign)
		registry[playerID] = registry[playerID] or {}
		registry[playerID][plot:GetIndex()] = true
	end
	if DEBUG then
		print(string.format("REMSELY_RAILWAYS: player %d own connected=%d foreign=%d", playerID, #own, foreign))
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

-- A rail or city event means the tree may have changed; TurnBegin sweeps up anything the events missed
-- (ownership flips, capital moves). Handlers ignore the event arguments and recompute everything - the walk is cheap.
local function OnNetworkChanged() RecomputeAll() end
if Events.RouteAddedToMap then Events.RouteAddedToMap.Add(OnNetworkChanged) end
if Events.RouteChanged then Events.RouteChanged.Add(OnNetworkChanged) end
if Events.RouteRemovedFromMap then Events.RouteRemovedFromMap.Add(OnNetworkChanged) end
if Events.CityAddedToMap then Events.CityAddedToMap.Add(OnNetworkChanged) end
if Events.CityRemovedFromMap then Events.CityRemovedFromMap.Add(OnNetworkChanged) end
if Events.TurnBegin then Events.TurnBegin.Add(OnNetworkChanged) end

-- One full pass at load: clear anything a save carries over, then rebuild (like the Farm script's load pass)
for index = 0, Map.GetPlotCount() - 1, 1 do
	local plot = Map.GetPlotByIndex(index)
	if plot ~= nil then
		if (plot:GetProperty(PROPERTY_CONNECTED) or 0) ~= 0 then plot:SetProperty(PROPERTY_CONNECTED, 0) end
		if (plot:GetProperty(PROPERTY_FOREIGN) or 0) ~= 0 then plot:SetProperty(PROPERTY_FOREIGN, 0) end
	end
end
RecomputeAll()

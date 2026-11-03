-- ===========================================================================
--
--	Loading screen as player goes from shell to game state.
--
-- ===========================================================================

include( "InputSupport" );
include( "InstanceManager" );
include( "SupportFunctions" );
include( "Civ6Common" );
include( "Colors") ;

-- ===========================================================================
--	Action Hotkeys
-- ===========================================================================
local m_actionHotkeyStartGame		:number = Input.GetActionId("StartGame");
local m_actionHotkeyStartGameAlt	:number = Input.GetActionId("StartGameAlt");



-- ===========================================================================
--	CONSTANTS
-- ===========================================================================

local DARKEN_AMOUNT			:number = -25;
local MIN_BLACK_Y			:number = 2;	-- Minimum size for black boxes on row bars
local SIZE_BUILDING_ICON	:number = 32;
local SIZE_CIV_LOGO_ICON	:number = 256;	-- Size of the logo in the background
local SIZE_UNIT_ICON		:number = 32;
local TIMEOUT_LOAD			:number = 1000;	-- # of frames before a timeout occurs obtaining player data for load screen


-- ===========================================================================
--	MEMBERS / VARIABLES
-- ===========================================================================
local m_isLoadComplete				:boolean = false;
local m_isResyncLoad				:boolean = false;
local m_isTraitsFullDescriptions	:boolean = false;



-- ===========================================================================
--	FUNCTIONS
-- ===========================================================================

-- ===========================================================================
function OnActivateButtonClicked()
	Controls.BackgroundImage:UnloadTexture();
	Controls.Portrait:UnloadTexture();
	Events.LoadScreenClose();
	UI.PlaySound("STOP_SPEECH_DAWNOFMAN");
	UI.StartStopMenuMusic(false);
	UI.PlaySound("Game_Begin_Button_Click");
	UI.PlaySound("Set_View_3D");
	UIManager:DequeuePopup( ContextPtr );

	Input.SetActiveContext( InputContext.World );

	if(UILens.IsPlayerLensSetToActive()) then
		UILens.SetActive("Default");
	end

    UI.SetExitOnClose(false);

	-- In PlayByCloud, we should trigger another cloud notification check now.  
	-- This will ensure the player gets a notification for the next cloud match so they can daisy chain all their turns quickly.
	if(GameConfiguration.IsPlayByCloud()) then
		local kandoConnected = FiraxisLive.IsFiraxisLiveLoggedIn();
		if(kandoConnected) then
			FiraxisLive.CheckForCloudNotifications();
		end
	end
end

-- ===========================================================================
--	Input Processing
-- ===========================================================================
function OnInput( uiMsg, wParam, lParam )
    if uiMsg == KeyEvents.KeyUp then
        if wParam == Keys.VK_ESCAPE then
			if m_isLoadComplete then
				OnActivateButtonClicked();
				return true;
			end
        end
    end
    return false;	-- Don't consume all; let hotkey action system get a crack
end

-- ===========================================================================
--	Hotkey
-- ===========================================================================
function OnInputActionTriggered( actionId:number )
	if	actionId == m_actionHotkeyStartGame		or
		actionId == m_actionHotkeyStartGameAlt	then
		if m_isLoadComplete then
			OnActivateButtonClicked();
		end
	end		

end

-- ===========================================================================
function RegisterButtonCallbacks()
	Controls.ActivateButton:RegisterCallback( Mouse.eMouseEnter, function() UI.PlaySound("Main_Menu_Mouse_Over"); end );
	Controls.ActivateButton:RegisterCallback( Mouse.eLClick, OnActivateButtonClicked );
	Controls.StartLabelButton:RegisterCallback( Mouse.eLClick, OnActivateButtonClicked );
end

-- ===========================================================================
function ClearButtonCallbacks()
	Controls.ActivateButton:ClearCallback( Mouse.eLClick );
	Controls.ActivateButton:ClearCallback( Mouse.eMouseEnter );
	Controls.StartLabelButton:ClearCallback( Mouse.eLClick );
end

-- ===========================================================================
--	UI Event
-- ===========================================================================
function OnShow()
	
	m_isLoadComplete	= false;
	m_isResyncLoad		= UI.IsResyncLoadInProgress(); -- Remember if this is a resync load for later.

	UIManager:SetUICursor( 1 );
	Controls.FadeAnim:SetToBeginning();	
	Controls.ActivateButton:SetHide(true);	
	Controls.LoadingContainer:SetHide(false);

	-- Wait until game configuration data is ready before showing anything.
	Controls.BackgroundImage:SetHide(true);
	Controls.Banner:SetHide(true);
	Controls.Portrait:SetHide(true);
	
	-- Clear button callbacks until loading is complete.
	ClearButtonCallbacks();

	-- Signal to a potentially raised state transition context that we're up (so it can hide).
	LuaEvents.Lower_State_Transition("LoadScreen");
end

-- ===========================================================================
--	UI Event
-- ===========================================================================
function OnHide()
	UIManager:SetUICursor( 0 );
end

-- ===========================================================================
function OnInit( isReload:boolean )
	if isReload then		
		OnShow();
		OnLoadScreenContentReady();
		OnLoadGameViewStateDone();
	end
end

-- ===========================================================================
--	All game data exists for the player in order to fill out the screen.
--	Do it...
-- ===========================================================================
function OnLoadScreenContentReady()

	if (GameConfiguration:IsWorldBuilderEditor()) then
		-- This needs to show some kind of World Builder splash screen.
		-- It can't show leaders, etc., they may not be initialized.
		return;
	end

	-- Because Game.GetLocalPlayer() not servicing yet use the network flavor;
	-- if in a hotseat mode the first slot may not be set to the human.
	local localPlayer	:number = Network.GetLocalPlayerID();
	if GameConfiguration.IsHotseat() then

		local maxPlayers :number = MapConfiguration.GetMaxMajorPlayers();
		for playerID = 0, maxPlayers-1,1 do
			local pPlayerConfig :table	= PlayerConfigurations[playerID];
			local slotStatus	:number = pPlayerConfig:GetSlotStatus();
			
			-- Potentially change the localPlayer number to the first human
			-- player in a slot.
			if slotStatus == SlotStatus.SS_TAKEN then
				localPlayer = playerID;	
				break;
			end
		end	
	end	

	local primaryColor, secondaryColor  = UI.GetPlayerColors( localPlayer );

	if primaryColor == nil then
		primaryColor = UI.GetColorValueFromHexLiteral(0xff99aaaa);
		UI.DataError("NIL primary color; likely player object not ready... using default color.");
	end
	if secondaryColor == nil then
		secondaryColor = UI.GetColorValueFromHexLiteral(0xffaa9999);
		UI.DataError("NIL secondary color; likely player object not ready... using default color.");
	end

	local backColor						= UI.DarkenLightenColor(primaryColor, DARKEN_AMOUNT, 255);
	Controls.Banner:SetColor(backColor);
	
	local playerConfig		:table = PlayerConfigurations[localPlayer];
	if playerConfig == nil then
		UI.DataError("Received NIL playerConfig for player #"..tostring(localPlayer));
	else
		local backgroundTexture:string;
		local leaderType:string = playerConfig:GetLeaderTypeName();
		local loadingInfo:table = GameInfo.LoadingInfo[leaderType];
		if loadingInfo and loadingInfo.BackgroundImage then
			backgroundTexture = loadingInfo.BackgroundImage;
		else
			backgroundTexture = leaderType .. "_BACKGROUND";
		end
	
		Controls.BackgroundImage:SetTexture( backgroundTexture );
		if (not Controls.BackgroundImage:HasTexture()) then
			UI.DataError("Failed to load background image texture: "..backgroundTexture);
			Controls.BackgroundImage:SetTexture("LEADER_T_ROOSEVELT_BACKGROUND");	-- Set to well known texture
		end

		-- fix 720P
		if (Controls.Background:GetSizeY() < 768) then
			Controls.Banner:SetSizeY(920);
			Controls.MainStack:SetOffsetY(20);
		else
			Controls.Banner:SetSizeY(987);
			Controls.MainStack:SetOffsetY(0);
		end

		local LEADER_CONTAINER_X = 512;
		local offsetX = math.floor((Controls.Portrait:GetSizeX() - LEADER_CONTAINER_X)/2);
		if (offsetX > 0) then
			Controls.Portrait:SetOffsetX(offsetX);
		else
			Controls.Portrait:SetOffsetX(0);
		end

		local portraitName:string;
		if loadingInfo and loadingInfo.ForegroundImage then
			portraitName = loadingInfo.ForegroundImage;
		else
			portraitName = leaderType .. "_NEUTRAL";
		end
	
		Controls.Portrait:SetTexture( portraitName );
		if (not Controls.Portrait:HasTexture()) then
			UI.DataError("We are lacking a texture for "..portraitName);
		end
		Controls.CivName:SetText( Locale.ToUpper( Locale.Lookup(playerConfig:GetCivilizationDescription())) );

	
		local eraInfoText;
		local leaderInfoText;

		local startEra = GameInfo.Eras[ GameConfiguration.GetStartEra() ];
		if (GameConfiguration.IsSavedGame()) then
			-- Returns a list of 1 entry...
			local metaData = UI.GetSaveGameMetaData();
			if(metaData and #metaData == 1) then
				local item = metaData[1];
				local saveEra = GameInfo.Eras[ item.HostEra ];
				if(saveEra) then
					startEra = saveEra;
				end
			end
		end

		if (startEra ~= nil) then
			eraInfoText = startEra.Description;
		end

		local challengeName;
		local challengeInfoText;

		local isChallengeActive = Challenges.IsChallengeActive();
		if isChallengeActive then
			challengeName = Challenges.GetLocalizedChallengeNameText();
			challengeInfoText = Challenges.GetLocalizedChallengeLoadingScreenDescriptionText();
		end

		local kLeader	:table = GameInfo.Leaders[leaderType];
		local leaderName;
		if kLeader ~= nil then
			leaderName = Locale.ToUpper(Locale.Lookup( kLeader.Name ));

			local details = "LOC_LOADING_INFO_" .. leaderType;
			if(Locale.HasTextKey(details)) then
				leaderInfoText = details;
			end
		else
			UI.DataError("No leader in DB by leaderType '"..leaderType.."'");
		end

		if(challengeName) then
			Controls.LeaderName:SetText(challengeName);
		elseif(leaderName) then
			Controls.LeaderName:SetText(leaderName);
		else
			UI.DataError("No proper text for the LeaderName field");
		end
	
		if(loadingInfo) then
			if(loadingInfo.EraText) then
				eraInfoText = loadingInfo.EraText;
			end

			if(loadingInfo.LeaderText) then
				leaderInfoText = loadingInfo.LeaderText;
			end
		end

		if (eraInfoText) then
			Controls.EraInfo:LocalizeAndSetText(eraInfoText);
			Controls.EraInfo:SetHide(false);
		else
			Controls.EraInfo:SetHide(true);
		end

		if(challengeInfoText) then
			Controls.LeaderInfo:SetText(challengeInfoText);
			Controls.LeaderInfo:SetHide(false);
		elseif(leaderInfoText) then
			Controls.LeaderInfo:LocalizeAndSetText(leaderInfoText);
			Controls.LeaderInfo:SetHide(false);
		else
			Controls.LeaderInfo:SetHide(true);
		end

		local civType	:string = playerConfig:GetCivilizationTypeName();
		local iconName	:string = "ICON_"..civType;
		Controls.LogoContainer:SetColor(primaryColor);
		Controls.Logo:SetColor(secondaryColor);
		Controls.Logo:SetIcon(iconName);

		Controls.Logo:SetHide(false);
		Controls.BackgroundImage:SetHide(false);
		Controls.Banner:SetHide(false);
		Controls.Portrait:SetHide(false);

		-- Find center of remaining space to right of ribbon, portrait will center it's texture on that.
		local ribbonRunsPastCenter:number = 80;
		local screenWidth, screenHeight = UIManager:GetScreenSizeVal();
		local backgroundWidth, backgroundHeight = Controls.BackgroundImage:GetSizeVal();
		local minWidth = math.min(backgroundWidth, screenWidth);
		Controls.PortraitContainer:SetSizeX( (minWidth*0.5) - ribbonRunsPastCenter );

		-- start the voiceover
		local leaderID = playerConfig:GetLeaderTypeID();
		local bPlayDOM = true;

		if(loadingInfo) then
			bPlayDOM = loadingInfo.PlayDawnOfManAudio;
		end

		if (m_isResyncLoad) then
			bPlayDOM = false;
		end

		-- Alexander dawn audio is driven by our embedded extension.
		if leaderType == "LEADER_REMSELY_ALEXANDER_II" then bPlayDOM = false; end

		if bPlayDOM then
			local dawnOfManLeaderID = leaderID;
			local dawnOfManEraHash = startEra.Hash;

			if(loadingInfo and loadingInfo.DawnOfManLeaderId) then
				dawnOfManLeaderID = loadingInfo.DawnOfManLeaderId;	
			end

			if(loadingInfo and loadingInfo.DawnOfManEraId) then
				dawnOfManEraHash = DB.MakeHash(loadingInfo.DawnOfManEraId);
			end

			if (Challenges.IsChallengeActive()) then
				-- Don't play leader/civilization for challenge games as those have the text missing.
				-- Setting this to the "NO_LEADER" values will cause sound not to play
				-- and override any stale values for the switch.
				dawnOfManLeaderID = -1;
			end

			UI.SetSoundSwitchValue("Leader_Screen_Civilization", UI.GetCivilizationSoundSwitchValueByLeader(dawnOfManLeaderID));
			UI.SetSoundSwitchValue("Civilization", UI.GetCivilizationSoundSwitchValueByLeader(dawnOfManLeaderID));
			UI.SetSoundSwitchValue("Era_DawnOfMan", UI.GetEraSoundSwitchValue(dawnOfManEraHash));
			UI.PlaySound("Play_DawnOfMan_Speech");
		end

		-- Obtain "uniques" from Civilization and for the chosen leader
		local uniqueAbilities;
		local uniqueUnits;
		local uniqueBuildings;
		uniqueAbilities, uniqueUnits, uniqueBuildings = GetLeaderUniqueTraits( leaderType );
		local CivUniqueAbilities, CivUniqueUnits, CivUniqueBuildings = GetCivilizationUniqueTraits( civType );
	
		-- Merge tables
		for i,v in ipairs(CivUniqueAbilities)	do table.insert(uniqueAbilities, v) end
		for i,v in ipairs(CivUniqueUnits)		do table.insert(uniqueUnits, v)		end
		for i,v in ipairs(CivUniqueBuildings)	do table.insert(uniqueBuildings, v) end

		-- Generate content
		for _, item in ipairs(uniqueAbilities) do
			--print( "ua:", item.TraitType, item.Name, item.Description, Locale.Lookup(item.Description));	--debug
			local instance:table = {};
			ContextPtr:BuildInstanceForControl("TextInfoInstance", instance, Controls.FeaturesStack );
			if (item.Name ~= nil and item.Name ~= "NONE") then
				local headerText:string = Locale.ToUpper(Locale.Lookup( item.Name )); 
				instance.Header:SetText( headerText );
			else
				instance.Header:SetShow(false);
			end

			if (item.Description ~= nil and item.Description ~= "NONE") then
				instance.Description:SetText( Locale.Lookup( item.Description ) );
			else
				instance.Description:SetShow(false);
			end
		end

		local size:number = SIZE_BUILDING_ICON;

		for _, item in ipairs(uniqueUnits) do
			--print( "uu:", item.TraitType, item.Name, item.Description, Locale.Lookup(item.Description));	--debug
			local instance:table = {};
			ContextPtr:BuildInstanceForControl("IconInfoInstance", instance, Controls.FeaturesStack );
			iconAtlas = "ICON_"..item.Type;
			instance.Icon:SetIcon(iconAtlas);
			instance.TextStack:SetOffsetX( size + 4 );
			local headerText:string = Locale.ToUpper(Locale.Lookup( item.Name ));
			instance.Header:SetText( headerText );
			instance.Description:SetText(Locale.Lookup(item.Description));
		end


		for _, item in ipairs(uniqueBuildings) do
			--print( "ub:", item.TraitType, item.Name, item.Description, Locale.Lookup(item.Description));	--debug
			local instance:table = {};
			ContextPtr:BuildInstanceForControl("IconInfoInstance", instance, Controls.FeaturesStack );
			instance.Icon:SetSizeVal(38,38);
			iconAtlas = "ICON_"..item.Type;
			instance.Icon:SetIcon(iconAtlas);
			instance.TextStack:SetOffsetX( size + 4 );
			local headerText:string = Locale.ToUpper(Locale.Lookup( item.Name ));
			instance.Header:SetText( headerText );
			instance.Description:SetText(Locale.Lookup(item.Description));
		end
	end
end

-- ===========================================================================
-- ENGINE Event
-- ===========================================================================
function OnBeforeMultiplayerInviteProcessing()
	-- We're about to process a game invite.  Get off the popup stack before we accidently break the invite!
	UIManager:DequeuePopup( ContextPtr );
end

-- ===========================================================================
--	ENGINE Event
-- ===========================================================================
function OnLoadGameViewStateDone()
	
	m_isLoadComplete = true;	
	print("OnLoadGameViewStateDone");
	
	UIManager:SetUICursor( 0 );	
	
	if m_isResyncLoad or GameConfiguration.IsAnyMultiplayer() or GameConfiguration:IsWorldBuilderEditor() then
		-- If this is a resync load, skip the Begin Game button.
		OnActivateButtonClicked();
	else
		-- Activate the Begin Game button.
		local strGameButtonName;


		if (GameConfiguration.IsSavedGame()) then
			strGameButtonName = Locale.Lookup("LOC_CONTINUE_GAME");		
		else
			strGameButtonName = Locale.Lookup("LOC_BEGIN_GAME");
		end

		Controls.StartLabelButton:SetText(strGameButtonName);
		Controls.ActivateButton:SetHide(false);
		Controls.LoadingContainer:SetHide(true);
		Controls.FadeAnim:SetToBeginning();
		Controls.FadeAnim:Play();
		UI.PlaySound("Game_Begin_Button_Appear");
        		
		Input.SetActiveContext( InputContext.Ready );

		-- If automation is running, continue on.
		if (Automation.IsAutoStartEnabled()) then
			OnActivateButtonClicked();
		end
	end    
	
	RegisterButtonCallbacks();

	-- Engine loading should be done at this point; enable input handling.	
	ContextPtr:SetInputHandler( OnInput );
	Events.InputActionTriggered.Add( OnInputActionTriggered );
end

-- ===========================================================================
function Initialize()

	Input.SetActiveContext( InputContext.Loading );

	-- EVENTS:
	ContextPtr:SetInitHandler( OnInit );
	-- Do not set input handler until content loading is done; otherwise engine will make LUA calls to engine during load (not recommended).
	ContextPtr:SetShowHandler( OnShow );
	ContextPtr:SetHideHandler( OnHide );	

	Events.LoadScreenContentReady.Add( OnLoadScreenContentReady );		-- Ready to show player info
	Events.LoadGameViewStateDone.Add( OnLoadGameViewStateDone );		-- Ready to start game
	Events.BeforeMultiplayerInviteProcessing.Add( OnBeforeMultiplayerInviteProcessing );

    UI.SetExitOnClose(true);
end
Initialize();

-- BEGIN GENERATED REMSELY LOADING VOICE (tools/loading_screen.py)
-- Generated from installed vanilla WEM metadata; no game audio is included.
REMSELY_LoadingEraSeconds = {
    ["Chinese(PRC)"] = {
        ERA_CLASSICAL = 16.765604,
        ERA_MEDIEVAL = 23.067042,
        ERA_INFORMATION = 22.334458,
        ERA_MODERN = 29.021708,
        ERA_INDUSTRIAL = 22.131271,
        ERA_ANCIENT = 17.889667,
        ERA_RENAISSANCE = 26.788333,
        ERA_ATOMIC = 17.748083,
    },
    ["Chinese(Taiwan)"] = {
        ERA_INDUSTRIAL = 28.483208,
        ERA_INFORMATION = 26.706937,
        ERA_CLASSICAL = 25.101292,
        ERA_MEDIEVAL = 26.483396,
        ERA_ANCIENT = 19.014813,
        ERA_ATOMIC = 21.479125,
        ERA_RENAISSANCE = 31.947563,
        ERA_MODERN = 31.143583,
    },
    ["English(US)"] = {
        ERA_INDUSTRIAL = 24.278646,
        ERA_MEDIEVAL = 23.191979,
        ERA_ANCIENT = 19.284979,
        ERA_MODERN = 31.863646,
        ERA_RENAISSANCE = 26.058958,
        ERA_ATOMIC = 22.897417,
        ERA_INFORMATION = 26.430979,
        ERA_CLASSICAL = 19.574813,
    },
    ["French(France)"] = {
        ERA_ATOMIC = 20.985375,
        ERA_RENAISSANCE = 24.341083,
        ERA_ANCIENT = 16.166833,
        ERA_CLASSICAL = 17.283542,
        ERA_INDUSTRIAL = 22.106792,
        ERA_MEDIEVAL = 20.839125,
        ERA_MODERN = 27.210583,
        ERA_INFORMATION = 27.219792,
    },
    ["German"] = {
        ERA_MODERN = 31.537188,
        ERA_RENAISSANCE = 24.200583,
        ERA_ANCIENT = 18.053896,
        ERA_ATOMIC = 27.844354,
        ERA_MEDIEVAL = 23.368792,
        ERA_CLASSICAL = 19.344333,
        ERA_INFORMATION = 28.737813,
        ERA_INDUSTRIAL = 24.497937,
    },
    ["Italian"] = {
        ERA_ANCIENT = 18.568417,
        ERA_MODERN = 31.032417,
        ERA_MEDIEVAL = 24.725208,
        ERA_INDUSTRIAL = 24.097125,
        ERA_CLASSICAL = 18.396208,
        ERA_ATOMIC = 23.262708,
        ERA_INFORMATION = 29.649375,
        ERA_RENAISSANCE = 27.291958,
    },
    ["Japanese"] = {
        ERA_CLASSICAL = 22.210833,
        ERA_ATOMIC = 31.763771,
        ERA_MODERN = 41.430667,
        ERA_INFORMATION = 38.211604,
        ERA_ANCIENT = 23.714000,
        ERA_RENAISSANCE = 35.705625,
        ERA_MEDIEVAL = 30.582854,
        ERA_INDUSTRIAL = 29.358583,
    },
    ["Korean"] = {
        ERA_INFORMATION = 26.613396,
        ERA_ANCIENT = 18.356729,
        ERA_MEDIEVAL = 24.100271,
        ERA_CLASSICAL = 16.866729,
        ERA_RENAISSANCE = 26.394542,
        ERA_INDUSTRIAL = 23.578625,
        ERA_ATOMIC = 24.787542,
        ERA_MODERN = 31.767583,
    },
    ["Polish"] = {
        ERA_RENAISSANCE = 27.014500,
        ERA_MODERN = 30.664792,
        ERA_ANCIENT = 18.923583,
        ERA_INDUSTRIAL = 22.496021,
        ERA_MEDIEVAL = 24.033313,
        ERA_CLASSICAL = 19.777854,
        ERA_INFORMATION = 31.502542,
        ERA_ATOMIC = 23.959958,
    },
    ["Russian"] = {
        ERA_ATOMIC = 18.778000,
        ERA_MEDIEVAL = 19.838333,
        ERA_INFORMATION = 23.559042,
        ERA_MODERN = 24.212062,
        ERA_CLASSICAL = 14.473479,
        ERA_ANCIENT = 15.617688,
        ERA_INDUSTRIAL = 21.282833,
        ERA_RENAISSANCE = 21.074813,
    },
    ["Spanish(Spain)"] = {
        ERA_INDUSTRIAL = 23.474792,
        ERA_ATOMIC = 21.748500,
        ERA_ANCIENT = 15.492500,
        ERA_RENAISSANCE = 23.538542,
        ERA_MODERN = 26.884958,
        ERA_INFORMATION = 25.323500,
        ERA_MEDIEVAL = 22.976667,
        ERA_CLASSICAL = 18.151583,
    },
};

-- Runs inside the vanilla FrontEnd LoadScreen context after its initialization.
-- For Alexander the vanilla pass posts no dawn audio (bPlayDOM = false in LoadScreen.lua);
-- this script drives the native dawn event itself: the civilization switches point at
-- Russia (DB.MakeHash("Russia") - the value stored in the game's audio bank) so the era
-- narration plays in the selected audio language, then the leader segment (Peter's
-- recording for Russia) is muted with an unmatched switch value, and our own Alexander
-- narration is queued after the era narration of the era the game starts in.
-- Restarting from the pause menu (Network.RestartGame) rebuilds the player
-- configurations, and when this pass runs the local player can still carry the
-- civilization's default leader (Peter for Russia): the vanilla block has then posted
-- the native event with Peter's voice. In that case the leader segment is muted at once
-- and the configuration is watched - when the chosen leader (Alexander) reappears, our
-- narration is queued; when the leader stays Peter, the vanilla speech is restored
-- before the leader segment starts.
-- tools/loading_screen.py embeds this source and the era table in LoadScreen.lua.
-- Every fresh context therefore defines and runs its own initializer without include().
function REMSELY_InitializeLoadingVoice()
    local previous = REMSELY_LoadingVoiceHandlers;
    if previous ~= nil then
        if OnLoadScreenContentReady == previous.contentReady then return; end
        Events.LoadScreenContentReady.Remove(previous.contentReady);
        Events.LoadScreenClose.Remove(previous.stop);
        previous.stop();
    end
    -- Era durations are embedded above this module.
    REMSELY_LoadingVoiceGeneration = (REMSELY_LoadingVoiceGeneration or 0) + 1;
    local baseContentReady = OnLoadScreenContentReady;
    local baseShow = OnShow;
    local baseHide = OnHide;
    local narrationStarted = false;
    local narrationDeadline = nil;
    local leaderMuteDeadline = nil;
    -- Set while the local player's configuration may still be a restart transient:
    -- { postedAt, seconds, decideBy, restored } (see StartTransientWatch).
    local transientWatch = nil;
    -- Mirrors the vanilla m_isResyncLoad capture: the resync flag is read when the
    -- screen is shown, not when the content becomes ready. A pause-menu restart sets
    -- the flag between those moments, and the vanilla dawn block (with its stale
    -- capture) still posts - a live check here would wrongly skip our takeover.
    local resyncAtShow = false;

    local function StopNarration()
        narrationDeadline = nil;
        leaderMuteDeadline = nil;
        transientWatch = nil;
        ContextPtr:ClearUpdate();
        if narrationStarted then
            UI.PlaySound("Stop_REMSELY_AlexanderII_Loading");
            narrationStarted = false;
            print("REMSELY voice: loading narration stopped");
        end
    end

    function OnShow()
        StopNarration();
        resyncAtShow = UI.IsResyncLoadInProgress();
        baseShow();
    end

    function OnHide()
        StopNarration();
        baseHide();
    end

    -- The local player whose dawn audio this screen drives; in hotseat games the first
    -- taken slot is the human watching the loading screen.
    local function GetDawnPlayerID()
        local playerID = Network.GetLocalPlayerID();
        if GameConfiguration.IsHotseat() then
            for id = 0, MapConfiguration.GetMaxMajorPlayers() - 1 do
                local p = PlayerConfigurations[id];
                if p ~= nil and p:GetSlotStatus() == SlotStatus.SS_TAKEN then playerID = id; break; end
            end
        end
        return playerID;
    end

    -- (era, seconds) of the dawn narration: the start era, or the save's HostEra, or the
    -- LoadingInfo override; seconds is nil when the era has no measured duration.
    -- LoadingInfo.PlayDawnOfManAudio is deliberately NOT read here: ours is 0 (it keeps
    -- vanilla contexts we do not control silent) while this extension posts the native
    -- event itself.
    local function GetEraAndDelay()
        local era = GameInfo.Eras[GameConfiguration.GetStartEra()];
        if GameConfiguration.IsSavedGame() then
            local metadata = UI.GetSaveGameMetaData();
            if metadata and #metadata == 1 then era = GameInfo.Eras[metadata[1].HostEra] or era; end
        end
        local info = GameInfo.LoadingInfo["LEADER_REMSELY_ALEXANDER_II"];
        if info then
            if info.DawnOfManEraId then era = GameInfo.Eras[info.DawnOfManEraId] or era; end
        end
        if era == nil then return nil, nil; end
        local language = Options.GetAppOption("Language", "AudioLanguage");
        local times = REMSELY_LoadingEraSeconds[language] or REMSELY_LoadingEraSeconds["English(US)"];
        local seconds = times[era.EraType];
        if seconds == nil then
            -- Ask the native mapping for later/custom eras instead of inventing a default.
            local value = UI.GetEraSoundSwitchValue(era.Hash);
            for eraType, duration in pairs(times) do
                local candidate = GameInfo.Eras[eraType];
                if candidate and UI.GetEraSoundSwitchValue(candidate.Hash) == value then seconds = duration; break; end
            end
        end
        return era, seconds;
    end

    -- The native dawn event is a sequence: the era narration first, a leader-specific
    -- speech second (DOM_LEAD_PET for Russia). The leader segment reads its switch when
    -- that segment starts, so while the era narration is still playing we move
    -- Leader_Screen_Civilization to a value that is not in the bank's table (and is not
    -- the engine's special NO_LEADER, which silences the whole event): Peter's segment
    -- then resolves to nothing and only the era narration is heard.
    local function MuteNativeLeaderDawn()
        leaderMuteDeadline = nil;
        -- Only the group the dawn event's leader segment reads; the "Civilization" group is
        -- left alone so later screens (diplomacy ambience) keep a valid value.
        local muteValue = DB.MakeHash("REMSELY_ALEXANDER_II_MUTE");
        UI.SetSoundSwitchValue("Leader_Screen_Civilization", muteValue);
        print("REMSELY voice: native leader dawn segment muted (value " .. tostring(muteValue) .. ")");
    end

    -- Start the native dawn event for our leader: the era narration in the selected audio
    -- language under Russia's civilization value, with the Peter segment muted shortly
    -- after the post.
    local function PostNativeDawn(era, player)
        local russiaValue = DB.MakeHash("Russia");
        local eraValue = UI.GetEraSoundSwitchValue(era.Hash);
        -- Diagnostics: what the native resolver would have used for our leader and for
        -- Peter, to compare against the value stored in the game's bank (1816587302).
        local ownValue = UI.GetCivilizationSoundSwitchValueByLeader(player:GetLeaderTypeID());
        local peterValue = "n/a";
        if GameInfo.Leaders ~= nil then
            local peter = GameInfo.Leaders["LEADER_PETER_GREAT"];
            if peter then peterValue = tostring(UI.GetCivilizationSoundSwitchValueByLeader(peter.Index)); end
        end
        print("REMSELY voice: dawn values russia=" .. tostring(russiaValue) .. " era=" .. tostring(eraValue)
            .. " (" .. tostring(era.EraType) .. " hash " .. tostring(era.Hash) .. ")"
            .. " ownLeader=" .. tostring(ownValue) .. " peter=" .. peterValue);
        UI.SetSoundSwitchValue("Leader_Screen_Civilization", russiaValue);
        UI.SetSoundSwitchValue("Civilization", russiaValue);
        UI.SetSoundSwitchValue("Era_DawnOfMan", eraValue);
        UI.PlaySound("Play_DawnOfMan_Speech");
        leaderMuteDeadline = UI.GetElapsedTime() + 0.75;
    end

    -- Match the narrator to the audio language, independently of the UI/subtitles.
    -- Other supported game audio languages retain the existing Russian fallback.
    local function GetNarrationEvent()
        local language = Options.GetAppOption("Language", "AudioLanguage") or "";
        if string.sub(language, 1, 7) == "English" then
            return "Play_REMSELY_AlexanderII_LOADING_EN";
        end
        return "Play_REMSELY_AlexanderII_LOADING_RU";
    end

    local function OnNarrationUpdate()
        local now = UI.GetElapsedTime();
        if transientWatch ~= nil then
            local player = PlayerConfigurations[GetDawnPlayerID()];
            local leaderName = player ~= nil and player:GetLeaderTypeName() or nil;
            if leaderName == "LEADER_REMSELY_ALEXANDER_II" then
                local watch = transientWatch;
                transientWatch = nil;
                local deadline = watch.postedAt + watch.seconds + 0.5;
                if now < deadline then
                    -- The era narration is still playing; re-assert the mute because the
                    -- restore below may have run while the configuration was stale.
                    MuteNativeLeaderDawn();
                    narrationDeadline = deadline;
                    print("REMSELY voice: restart leader resolved to Alexander; narration queued, delay "
                        .. tostring(deadline - now));
                else
                    -- The era narration has fully played by now (Peter may even be audible
                    -- for a moment): stop the native event and start our narration at once.
                    UI.PlaySound("STOP_SPEECH_DAWNOFMAN");
                    narrationStarted = true;
                    UI.PlaySound(GetNarrationEvent());
                    print("REMSELY voice: restart leader resolved to Alexander after the era intro; narration started");
                end
            elseif leaderName == "LEADER_PETER_GREAT" then
                if now >= transientWatch.decideBy and not transientWatch.restored then
                    -- A genuine Peter game: hand the leader segment back to the native
                    -- event before it starts, exactly as the vanilla pass left it. Keep
                    -- watching until the era narration ends in case our leader appears
                    -- in the final window (the flip above re-mutes in time).
                    transientWatch.restored = true;
                    UI.SetSoundSwitchValue("Leader_Screen_Civilization", DB.MakeHash("Russia"));
                    print("REMSELY voice: leader stays Peter; native leader dawn restored");
                end
                if now >= transientWatch.postedAt + transientWatch.seconds + 0.5 then
                    transientWatch = nil;
                end
            elseif leaderName ~= nil then
                -- Some other concrete leader replaced the transient: not our game.
                transientWatch = nil;
                UI.SetSoundSwitchValue("Leader_Screen_Civilization", DB.MakeHash("Russia"));
                print("REMSELY voice: leader resolved to " .. leaderName .. "; native leader dawn restored");
            end
            -- A nil configuration is mid-rebuild: keep watching until it resolves.
        end
        if leaderMuteDeadline ~= nil and now >= leaderMuteDeadline then
            MuteNativeLeaderDawn();
        end
        if narrationDeadline ~= nil and now >= narrationDeadline then
            narrationDeadline = nil;
            -- The era narration has ended by now, so stopping the native event can only cut
            -- the already muted Peter segment if it survived, never the era narration.
            UI.PlaySound("STOP_SPEECH_DAWNOFMAN");
            narrationStarted = true;
            UI.PlaySound(GetNarrationEvent());
            print("REMSELY voice: FrontEnd loading narration started after era intro");
        end
        if narrationDeadline == nil and leaderMuteDeadline == nil and transientWatch == nil then
            ContextPtr:ClearUpdate();
        end
    end

    -- A pause-menu restart (Network.RestartGame) rebuilds the player configurations and
    -- can leave the local player on the civilization's default leader when the
    -- content-ready pass runs, so the vanilla block above has already posted the native
    -- dawn event with Peter's voice. Mute the leader segment immediately and watch for
    -- the chosen leader to be re-applied (handled in OnNarrationUpdate). The civilization
    -- name may itself be mid-rebuild (nil) and is only checked when concrete: a leader
    -- other than Peter's Russia is somebody else's screen and stays untouched. Requires
    -- a measured era duration so the restore deadline is known; without one the native
    -- event stays untouched.
    local function StartTransientWatch(player, leaderName)
        local civName = player:GetCivilizationTypeName();
        local era, seconds = GetEraAndDelay();
        if leaderName ~= "LEADER_PETER_GREAT" or (civName ~= nil and civName ~= "CIVILIZATION_RUSSIA") then
            print("REMSELY voice: foreign player " .. tostring(leaderName) .. " (" .. tostring(civName)
                .. "); native loading screen untouched");
            return;
        end
        if era == nil or seconds == nil then
            print("REMSELY voice: restart transient suspected but era duration unknown ("
                .. tostring(era and era.EraType) .. "); native loading screen untouched");
            return;
        end
        MuteNativeLeaderDawn();
        local now = UI.GetElapsedTime();
        transientWatch = { postedAt = now, seconds = seconds, decideBy = now + seconds - 1.5, restored = false };
        ContextPtr:SetUpdate(OnNarrationUpdate);
        print("REMSELY voice: restart transient (default Peter config, civ " .. tostring(civName)
            .. "); waiting for our leader");
    end

    function OnLoadScreenContentReady()
        if narrationStarted or narrationDeadline ~= nil or leaderMuteDeadline ~= nil or transientWatch ~= nil then return; end
        baseContentReady();
        -- One compact state line whenever we do not take the normal path, so a silent
        -- early exit is always visible in Lua.log.
        local function BailState(reason)
            local player = PlayerConfigurations[GetDawnPlayerID()];
            local leaderName = player ~= nil and player:GetLeaderTypeName() or nil;
            local civName = player ~= nil and player:GetCivilizationTypeName() or nil;
            print("REMSELY voice: content-ready bail (" .. reason .. ") resync=" .. tostring(resyncAtShow)
                .. " leader=" .. tostring(leaderName) .. " civ=" .. tostring(civName));
        end
        if resyncAtShow or GameConfiguration:IsWorldBuilderEditor() then
            BailState("resync/worldbuilder");
            return;
        end
        local player = PlayerConfigurations[GetDawnPlayerID()];
        if player == nil then
            BailState("no player configuration");
            return;
        end
        local leaderName = player:GetLeaderTypeName();
        if leaderName ~= "LEADER_REMSELY_ALEXANDER_II" then
            StartTransientWatch(player, leaderName);
            return;
        end
        if Challenges.IsChallengeActive() then return; end
        local era, seconds = GetEraAndDelay();
        if era ~= nil then
            PostNativeDawn(era, player);
            -- Tell the InGame dawn driver (RemselysAlexanderII_Voice) that this load is
            -- already handled, so it does not post a second sequence. Single player only:
            -- restarts (the driver's purpose) never happen in multiplayer.
            if not GameConfiguration.IsAnyMultiplayer() then
                local ok = pcall(GameConfiguration.SetValue, "REMSELY_LoadingVoiceHandled", true);
                print("REMSELY voice: dawn handled marker " .. (ok and "set" or "NOT set"));
            end
        end
        if seconds == nil then
            if leaderMuteDeadline ~= nil then ContextPtr:SetUpdate(OnNarrationUpdate); end
            print("REMSELY voice: unknown era narration duration; custom narration not queued");
            return;
        end
        narrationDeadline = UI.GetElapsedTime() + seconds + 0.5;
        ContextPtr:SetUpdate(OnNarrationUpdate);
        print("REMSELY voice: loading narration queued after era intro, delay " .. tostring(seconds + 0.5));
    end

    Events.LoadScreenContentReady.Remove(baseContentReady);
    Events.LoadScreenContentReady.Add(OnLoadScreenContentReady);
    Events.LoadScreenClose.Add(StopNarration);
    ContextPtr:SetShowHandler(OnShow);
    ContextPtr:SetHideHandler(OnHide);
    REMSELY_LoadingVoiceHandlers = { contentReady = OnLoadScreenContentReady, stop = StopNarration };
    print("REMSELY voice: FrontEnd loading hook ready, generation " .. tostring(REMSELY_LoadingVoiceGeneration));
end
REMSELY_InitializeLoadingVoice();
-- END GENERATED REMSELY LOADING VOICE

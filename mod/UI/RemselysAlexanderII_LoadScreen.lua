-- Runs inside the vanilla FrontEnd LoadScreen context after its initialization.
-- For Alexander the vanilla pass posts no dawn audio (bPlayDOM = false in LoadScreen.lua);
-- this script drives the native dawn event itself: the civilization switches point at
-- Russia (DB.MakeHash("Russia") - the value stored in the game's audio bank) so the era
-- narration plays in the selected audio language, then the leader segment (Peter's
-- recording for Russia) is muted with an unmatched switch value, and our own Alexander
-- narration is queued after the era narration of the era the game starts in.
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
    include("RemselysAlexanderII_LoadingEraDurations");
    REMSELY_LoadingVoiceGeneration = (REMSELY_LoadingVoiceGeneration or 0) + 1;
    local baseContentReady = OnLoadScreenContentReady;
    local baseShow = OnShow;
    local baseHide = OnHide;
    local narrationStarted = false;
    local narrationDeadline = nil;
    local leaderMuteDeadline = nil;

    local function StopNarration()
        narrationDeadline = nil;
        leaderMuteDeadline = nil;
        ContextPtr:ClearUpdate();
        if narrationStarted then
            UI.PlaySound("Stop_REMSELY_AlexanderII_Loading");
            narrationStarted = false;
            print("REMSELY voice: loading narration stopped");
        end
    end

    function OnShow()
        StopNarration();
        baseShow();
    end

    function OnHide()
        StopNarration();
        baseHide();
    end

    -- (era, seconds) of the dawn narration: the start era, or the save's HostEra, or the
    -- LoadingInfo override; seconds is nil when the era has no measured duration.
    local function GetEraAndDelay()
        local era = GameInfo.Eras[GameConfiguration.GetStartEra()];
        if GameConfiguration.IsSavedGame() then
            local metadata = UI.GetSaveGameMetaData();
            if metadata and #metadata == 1 then era = GameInfo.Eras[metadata[1].HostEra] or era; end
        end
        local info = GameInfo.LoadingInfo["LEADER_REMSELY_ALEXANDER_II"];
        if info then
            if info.PlayDawnOfManAudio == false then return nil, 0; end
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
        if narrationDeadline == nil and leaderMuteDeadline == nil then
            ContextPtr:ClearUpdate();
        end
    end

    function OnLoadScreenContentReady()
        if narrationStarted or narrationDeadline ~= nil or leaderMuteDeadline ~= nil then return; end
        baseContentReady();
        if UI.IsResyncLoadInProgress() or GameConfiguration:IsWorldBuilderEditor() then return; end
        local playerID = Network.GetLocalPlayerID();
        if GameConfiguration.IsHotseat() then
            for id = 0, MapConfiguration.GetMaxMajorPlayers() - 1 do
                local p = PlayerConfigurations[id];
                if p ~= nil and p:GetSlotStatus() == SlotStatus.SS_TAKEN then playerID = id; break; end
            end
        end
        local player = PlayerConfigurations[playerID];
        if player == nil or player:GetLeaderTypeName() ~= "LEADER_REMSELY_ALEXANDER_II" then return; end
        if Challenges.IsChallengeActive() then return; end
        local era, seconds = GetEraAndDelay();
        if era ~= nil then
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

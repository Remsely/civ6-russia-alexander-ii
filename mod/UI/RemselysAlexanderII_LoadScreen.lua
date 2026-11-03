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
    include("RemselysAlexanderII_LoadingEraDurations");
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

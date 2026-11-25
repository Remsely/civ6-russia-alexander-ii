"""Exercise explicit skip handling without consuming UI input."""
from pathlib import Path

from lupa import LuaRuntime


def runtime():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute('''
      skips=0; hidden=true; dealOpen=false; popupOpen=false; fadeStopped=true
      function event()
        local e={handlers={}}
        e.Add=function(f) table.insert(e.handlers,f) end
        e.Remove=function(f) end
        return setmetatable(e,{__call=function(self,...)
          for _,f in ipairs(self.handlers) do f(...) end
        end})
      end
      LuaEvents={DiploScene_SceneOpened=event(), DiploScene_LeaderSelect=event(),
        DiploScene_SceneClosed=event(), REMSELY_VoiceUserSkip=event()}
      LuaEvents.REMSELY_VoiceUserSkip.Add(function() skips=skips+1 end)
      setmetatable(LuaEvents,{__index=function(t,k) local e=event(); rawset(t,k,e); return e end})
      PlayerConfigurations={
        [1]={GetLeaderTypeName=function() return 'LEADER_REMSELY_ALEXANDER_II' end},
        [2]={GetLeaderTypeName=function() return 'OTHER' end}}
      KeyEvents={KeyUp=1,KeyDown=2}; Keys={VK_ESCAPE=27}; MouseEvents={RButtonUp=3,LButtonUp=4}
      function control(parent)
        return {parent=parent, hidden=false, hovered=false, disabled=false,
          IsHidden=function(self) return self.hidden end,
          IsVisible=function(self) return not self.hidden end,
          GetParent=function(self) return self.parent end,
          HasMouseOver=function(self) return self.hovered end,
          IsDisabled=function(self) return self.disabled end}
      end
      root=control(nil); deal=control(nil); popup=control(root)
      function deal:IsHidden() return not dealOpen end
      function popup:IsVisible() return popupOpen end
      conversation=control(root); stack=control(conversation)
      alpha=control(conversation); slide=control(alpha); grid=control(slide); stack.parent=grid
      first=control(stack); second=control(stack)
      function stack:GetChildren() return {first,second} end
      overview=control(root); close=control(overview); cinema=control(root); cinema.hidden=true
      fade=control(root); function fade:IsStopped() return fadeStopped end
      ACTION='/InGame/Diplomacy/DiplomacyActionView'
      controls={[ACTION]=root,
        ['/InGame/Diplomacy/DiplomacyDealView']=deal,
        [ACTION..'/PopupRoot']=popup,
        [ACTION..'/ConversationContainer']=conversation,
        [ACTION..'/ConversationContainer/ConversationSelection_Alpha']=alpha,
        [ACTION..'/ConversationContainer/ConversationSelection_Alpha/ConversationSelection_Slide']=slide,
        [ACTION..'/ConversationContainer/ConversationSelection_Alpha/ConversationSelection_Slide/ConversationSelectionGrid']=grid,
        [ACTION..'/ConversationContainer/ConversationSelection_Alpha/ConversationSelection_Slide/ConversationSelectionGrid/ConversationSelectionStack']=stack,
        [ACTION..'/VoiceoverTextContainer']=cinema,
        [ACTION..'/OverviewContainer']=overview,
        [ACTION..'/OverviewContainer/CloseButton']=close,
        [ACTION..'/BlackFade/BlackFadeAnim']=fade}
      ContextPtr={SetHide=function(_,v) hidden=v end,
        LookUpControl=function(_,path) return controls[path] end,
        SetInputHandler=function(_,fn) inputHandler=fn end, SetShutdown=function(_,fn) shutdown=fn end}
      function fire(name,...) for _,f in ipairs(LuaEvents[name].handlers) do f(...) end end
      function input(kind,key)
        return inputHandler({GetMessageType=function() return kind end,GetKey=function() return key end})
      end
    ''')
    lua.execute(Path('mod/UI/RemselysAlexanderII_VoiceInput.lua').read_text(encoding='utf-8'))
    return lua


def test_choices_stop_before_next_response_and_never_consume():
    lua = runtime()
    lua.execute('''
      fire('DiploScene_SceneOpened',1); assert(not hidden)
      first.hovered=true
      assert(input(4,0)==false and skips==1)
      -- A response is posted only after the input continues to the game.
      local newResponsePlayed=true; assert(newResponsePlayed and skips==1)
      first.disabled=true; assert(input(4,0)==false and skips==1)
      first.disabled=false; conversation.hidden=true
      assert(input(4,0)==false and skips==1)
      conversation.hidden=false; first.hovered=false
      assert(input(4,0)==false and skips==1)
      fire('DiploScene_SceneClosed'); assert(hidden)
      first.hovered=true; assert(input(4,0)==false and skips==1)
    ''')


def test_escape_right_click_and_close_obey_surface_and_popup():
    lua = runtime()
    lua.execute('''
      fire('DiploScene_SceneOpened',1)
      assert(input(1,27)==false and skips==1)
      assert(input(3,0)==false and skips==1) -- RMB ignored in conversation
      cinema.hidden=false; assert(input(3,0)==false and skips==2)
      fadeStopped=false; assert(input(3,0)==false and skips==2)
      assert(input(1,27)==false and skips==3) -- cinematic skips even during fade
      cinema.hidden=true; assert(input(1,27)==false and skips==3) -- conversation waits
      fadeStopped=true; popupOpen=true
      first.hovered=true; close.hovered=true
      assert(input(4,0)==false and input(1,27)==false and skips==3)
      popupOpen=false; dealOpen=true
      assert(input(4,0)==false and input(1,27)==false and skips==3)
      dealOpen=false; first.hovered=false
      assert(input(4,0)==false and skips==4) -- overview X
      fire('DiploScene_LeaderSelect',2); assert(hidden)
      assert(input(4,0)==false and skips==4)
    ''')


def test_missing_popup_falls_back_but_available_popup_still_blocks():
    lua = runtime()
    lua.execute('''
      fire('DiploScene_SceneOpened',1)
      controls[ACTION..'/PopupRoot']=nil
      first.hovered=true; assert(input(4,0)==false and skips==1)
      controls[ACTION..'/PopupRoot']=popup
      popupOpen=true; assert(input(4,0)==false and skips==1)
      popupOpen=false; assert(input(4,0)==false and skips==2)
      function popup:IsVisible() error('broken popup') end
      assert(input(4,0)==false and skips==2)
    ''')


def test_missing_or_broken_required_controls_fail_closed():
    lua = runtime()
    lua.execute('''
      fire('DiploScene_SceneOpened',1)
      first.hovered=true
      controls[ACTION]=nil; assert(input(4,0)==false and skips==0)
      controls[ACTION]=root
      controls['/InGame/Diplomacy/DiplomacyDealView']=nil
      assert(input(4,0)==false and skips==0)
      controls['/InGame/Diplomacy/DiplomacyDealView']=deal
      function conversation:IsHidden() error('broken UI') end
      assert(input(4,0)==false and skips==0)
    ''')


def test_popup_instance_namespace_is_checked_when_direct_path_missing():
    lua = runtime()
    lua.execute('''
      fire('DiploScene_SceneOpened',1)
      controls[ACTION..'/PopupRoot']=nil
      controls[ACTION..'/PopupDialog/PopupRoot']=popup
      first.hovered=true; popupOpen=true
      assert(input(4,0)==false and skips==0)
      popupOpen=false; assert(input(4,0)==false and skips==1)
    ''')


def test_hidden_ancestor_above_action_does_not_disable_visible_buttons():
    lua = runtime()
    lua.execute('''
      -- Diplomacy is nested under other contexts. Only action controls decide
      -- whether this view can receive a choice, not unrelated ancestors.
      local ancestor=control(nil); ancestor.hidden=true; root.parent=ancestor
      fire('DiploScene_SceneOpened',1); first.hovered=true
      assert(input(4,0)==false and skips==1)
      conversation.hidden=true; assert(input(4,0)==false and skips==1)
      conversation.hidden=false; stack.hidden=true
      assert(input(4,0)==false and skips==1)
      stack.hidden=false; grid.hidden=true
      assert(input(4,0)==false and skips==1)
    ''')


def test_input_and_voice_contexts_preserve_new_response_after_automatic_close():
    lua = runtime()
    lua.execute('''
      calls={}; Events=setmetatable({},{__index=function(t,k) local e=event(); rawset(t,k,e); return e end})
      function include() end
      UI={PlaySound=function(name) table.insert(calls,name) end, SetSoundSwitchValue=function() end}
      Game={GetLocalPlayer=function() return 0 end}; Players={}; DiplomacyMoodTypes={UNDEFINED=-1}
      DiplomacyManager={GetKeyName=function(x) return x end,FindTextKey=function(x) return x end}
      currentText='LOC_DIPLO_DELEGATION_FROM_AI_LEADER_REMSELY_ALEXANDER_II_ANY'
      DiplomacySupport_ExtractStatement=function() return {StatementText=currentText} end
    ''')
    source = Path('mod/UI/RemselysAlexanderII_Voice.lua').read_text(encoding='utf-8')
    lua.execute(source.split('-- ===========================================================================\n-- Dawn-of-man fallback')[0])
    lua.execute('''
      local v={StatementType='X',StatementSubType='Y',FromPlayer=1,FromPlayerMood=0}
      fire('DiploScene_SceneOpened',1)
      Events.DiplomacyStatement(1,0,v)
      assert(calls[#calls]=='Play_REMSELY_AlexanderII_DELEGATION_FROM_AI')
      first.hovered=true; assert(input(4,0)==false)
      assert(calls[#calls]=='Stop_REMSELY_AlexanderII_Speech')
      currentText='LOC_DIPLO_FIRST_MEET_VISIT_RECIPIENT_LEADER_REMSELY_ALEXANDER_II_ANY'
      Events.DiplomacyStatement(1,0,v)
      assert(calls[#calls]=='Play_REMSELY_AlexanderII_FIRST_MEET_VISIT_RECIPIENT')
      local before=#calls
      fire('DiploScene_SceneClosed'); Events.HideLeaderScreen()
      assert(#calls==before, 'automatic close must not stop the new response')
    ''')

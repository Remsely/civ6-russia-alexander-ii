"""Check filtering and bounded output of the temporary read-only event trace."""
from pathlib import Path
import re

from lupa import LuaRuntime


SOURCE=Path('tools/experiments/religion_event_stream_trace.lua')


def runtime(missing=(), local_id=1, operation=123):
    lua=LuaRuntime(unpack_returned_tuples=True)
    lua.execute('''
      output={};print=function(s) output[#output+1]=s end
      function event()
        return {Add=function(fn) end}
      end
      function makeEvent()
        local e={};e.Add=function(fn) e.fn=fn end;return e
      end
      Events={UnitMoved=makeEvent(),UnitTeleported=makeEvent(),UnitChargesChanged=makeEvent(),UnitOperationStarted=makeEvent(),
        CityReligionChanged=makeEvent(),GameCoreEventPublishComplete=makeEvent()}
      GameEvents={OnUnitMoved=makeEvent()}
      localId=1;Game={GetLocalPlayer=function() return localId end,GetCurrentGameTurn=function() return 42 end}
      GameInfo={UnitOperations={UNITOPERATION_SPREAD_RELIGION={Hash=123}}}
    ''')
    lua.globals().localId=local_id
    lua.globals().GameInfo.UnitOperations.UNITOPERATION_SPREAD_RELIGION.Hash=operation
    for namespace,name in missing:
        lua.globals()[namespace][name]=None
    lua.execute(SOURCE.read_text(encoding='utf-8'))
    return lua


def test_all_spreads_and_cities_are_recorded_but_only_local_opens_window():
    lua=runtime()
    lua.execute('''
      for i=1,800 do
        Events.UnitOperationStarted.fn(2,i,123)
        Events.UnitMoved.fn(2,i,7,8)
        GameEvents.OnUnitMoved.fn(2,i,1,2,3,4)
      end
      assert(#output==514) -- ready, 512 AI raw observations and limit marker
      GameEvents.OnUnitMoved.fn(1,9,1,2,3,4)
      Events.UnitMoved.fn(1,9,3,4,true,false)
      Events.CityReligionChanged.fn(2,13,5)
      Events.UnitOperationStarted.fn(1,9,124)
      assert(#output==515) -- city changes have their own independent stream
      Events.UnitOperationStarted.fn(1,9,123)
      Events.UnitTeleported.fn(1,9,5,6)
      Events.UnitChargesChanged.fn(1,9,0,1,'extra')
      Events.UnitChargesChanged.fn(2,9,0,1)
      Events.CityReligionChanged.fn(2,13,6)
      Events.GameCoreEventPublishComplete.fn()
      Events.GameCoreEventPublishComplete.fn()
    ''')
    lines=[lua.globals().output[i] for i in range(1,len(lua.globals().output)+1)]
    joined='\n'.join(lines)
    assert 'event=sync_move argc=6 a1=1 a2=9 a3=1 a4=2 a5=3 a6=4' in joined
    assert 'event=unit_moved argc=6 a1=1 a2=9' in joined
    assert 'event=spread_operation argc=3 a1=1 a2=9 a3=123' in joined
    assert 'event=city_religion_changed argc=3 a1=2 a2=13 a3=5' in joined
    assert 'event=city_religion_changed argc=3 a1=2 a2=13 a3=6' in joined
    assert 'event=unit_teleported argc=4 a1=1 a2=9 a3=5 a4=6' in joined
    assert 'event=unit_charges_changed argc=5 a1=1 a2=9 a3=0 a4=1 a5="extra"' in joined
    assert 'event=unit_charges_changed argc=4 a1=2' not in joined
    assert 'raw=other_spread n=512 ' in joined
    assert 'raw=other_spread limit=512 reached; further events omitted' in joined
    assert 'raw=city n=1 ' in joined and 'raw=local_spread n=1 ' in joined
    assert 'a1=2 a2=800' not in joined
    assert 'end reason=publish_limit' in joined


def test_ring_and_total_output_are_bounded_under_large_event_streams():
    lua=runtime()
    lua.execute('''
      for i=1,2000 do Events.CityReligionChanged.fn(3,i,9) end
      for round=1,30 do
        Events.UnitOperationStarted.fn(1,round,123)
        for i=1,100 do Events.CityReligionChanged.fn(3,i,9) end
        Events.GameCoreEventPublishComplete.fn();Events.GameCoreEventPublishComplete.fn()
      end
    ''')
    lines=[lua.globals().output[i] for i in range(1,len(lua.globals().output)+1)]
    assert len(lines)<=240 + 512 + 64 + 512 + 16 + 4
    assert sum(' begin local=' in line for line in lines)<=3
    assert sum('raw=city n=' in line for line in lines)==512
    assert sum('raw=local_spread n=' in line for line in lines)==30
    assert sum('raw=city limit=512 reached' in line for line in lines)==1
    # A new window exposes at most 64 retained precursors.
    assert all(int(re.search(r'ring=(\d+)',line).group(1))<=64 for line in lines if ' begin local=' in line)


def test_ai_saturation_preserves_city_local_and_detailed_window_budgets():
    lua=runtime()
    lua.execute('''
      for i=1,800 do Events.UnitOperationStarted.fn(2,i,123) end
      Events.CityReligionChanged.fn(2,13,6)
      Events.UnitOperationStarted.fn(1,9,123)
      Events.CityReligionChanged.fn(2,13,7)
      Events.GameCoreEventPublishComplete.fn()
      Events.GameCoreEventPublishComplete.fn()
    ''')
    text='\n'.join(lua.globals().output[i] for i in range(1,len(lua.globals().output)+1))
    assert text.count('raw=other_spread n=')==512
    assert text.count('raw=other_spread limit=512 reached')==1
    assert text.count('raw=city n=')==2
    assert 'raw=local_spread n=1 ' in text
    assert 'window=1 begin local=1' in text
    assert 'phase=before' in text and 'phase=after' in text


def test_passive_city_event_is_recorded_without_a_spread_operation():
    lua=runtime()
    lua.execute('Events.CityReligionChanged.fn(2,13,6)')
    assert len(lua.globals().output)==2
    assert 'raw=city n=1 ' in lua.globals().output[2]
    assert 'argc=3 a1=2 a2=13 a3=6' in lua.globals().output[2]
    assert 'window=' not in lua.globals().output[2]


def test_two_local_spreads_and_city_change_in_one_packet_remain_in_order():
    lua=runtime()
    lua.execute('''
      Events.UnitOperationStarted.fn(1,9,123)
      Events.CityReligionChanged.fn(2,13,6)
      Events.UnitChargesChanged.fn(1,9,0,1)
      Events.UnitOperationStarted.fn(1,10,123)
      Events.GameCoreEventPublishComplete.fn()
    ''')
    lines=[lua.globals().output[i] for i in range(1,len(lua.globals().output)+1)]
    relevant=[x for x in lines if 'phase=after' in x and (
        'event=spread_operation' in x or 'event=city_religion_changed' in x or 'event=unit_charges_changed' in x)]
    assert len(relevant)==4
    assert 'a2=9' in relevant[0] and 'event=city_religion_changed' in relevant[1]
    assert 'event=unit_charges_changed' in relevant[2] and 'a2=10' in relevant[3]
    assert all('batch=0' in x for x in relevant)


def test_missing_optional_events_or_invalid_hash_are_safe():
    lua=runtime(missing=(('Events','UnitTeleported'),('GameEvents','OnUnitMoved')))
    assert 'UnitTeleported:missing' in lua.globals().output[1]
    assert 'OnUnitMoved:missing' in lua.globals().output[1]
    lua.globals().Events.UnitOperationStarted.fn(1,9,123)
    assert len(lua.globals().output)>1
    disabled=runtime(operation='not-a-hash')
    assert 'operation=nil' in disabled.globals().output[1]
    assert disabled.globals().Events.UnitOperationStarted.fn is None
    disabled.globals().Events.CityReligionChanged.fn(2,13,6)
    assert 'raw=city n=1 ' in disabled.globals().output[2]


def test_unavailable_local_player_records_unknown_but_opens_no_window():
    lua=runtime(local_id=-1)
    lua.execute('''
      Events.UnitMoved.fn(1,9,3,4);Events.UnitOperationStarted.fn(1,9,123)
      assert(#output==2 and string.find(output[2], 'raw=unknown_spread', 1, true))
      localId=1;Events.UnitOperationStarted.fn(1,9,123);assert(#output>1)
    ''')


def test_callback_payload_is_bounded_and_objects_are_not_touched():
    lua=runtime()
    lua.execute('''
      local secret=setmetatable({},{__tostring=function() error('object was traversed') end})
      Events.UnitOperationStarted.fn(1,9,123,secret,nil,'line'..string.char(10)..'break',4,5,6,7,8,9)
    ''')
    text='\n'.join(lua.globals().output[i] for i in range(1,len(lua.globals().output)+1))
    assert 'a4=<table>' in text and 'a5=nil' in text and 'truncated=true' in text
    assert 'a6="line?break"' in text


def test_callbacks_never_write_state_or_scan_map():
    lua=runtime()
    lua.execute('''
      forbidden=0
      Game.SetProperty=function(...) forbidden=forbidden+1;error('state mutation') end
      Map=setmetatable({},{__index=function() forbidden=forbidden+1;error('map access') end})
      CityManager=setmetatable({},{__index=function() forbidden=forbidden+1;error('city access') end})
      playerReads,aiReads=0,0
      local religion={GetReligionType=function() return 7 end,GetSpreadCharges=function() return 0 end}
      local unit={GetReligion=function() return religion end,GetX=function() return -9999 end,GetY=function() return -9999 end}
      local units={FindID=function(_,id) return unit end}
      Players=setmetatable({[1]={GetUnits=function() playerReads=playerReads+1;return units end},
        [2]={GetUnits=function() aiReads=aiReads+1;return units end}},
        {__index=function() forbidden=forbidden+1;error('unrelated player access') end})
      for i=1,200 do
        GameEvents.OnUnitMoved.fn(1,i,0,0,1,1)
        Events.UnitMoved.fn(1,i,1,1)
        Events.UnitChargesChanged.fn(1,i,1,2)
        Events.CityReligionChanged.fn(2,i,4)
        Events.UnitOperationStarted.fn(2,i,123)
      end
      assert(playerReads==0 and aiReads==200)
      Events.UnitOperationStarted.fn(1,9,123)
      assert(playerReads==1)
      Events.UnitTeleported.fn(1,9,7,9)
      Events.GameCoreEventPublishComplete.fn()
      assert(forbidden==0)
    ''')
    text='\n'.join(lua.globals().output[i] for i in range(1,len(lua.globals().output)+1))
    assert 'event=spread_snapshot_delivery argc=6 a1=1 a2=9 a3=-9999 a4=-9999 a5=7 a6=0' in text
    assert 'delivery_x=-9999 delivery_y=-9999 delivery_faith=7 delivery_charges=0' in text


def test_ai_snapshot_is_bounded_and_missing_or_error_does_not_break_diagnostic():
    lua=runtime()
    lua.execute('''
      aiReads=0
      local religion={GetReligionType=function() return 7 end,GetSpreadCharges=function() return 1 end}
      local unit={GetReligion=function() return religion end,GetX=function() return 12 end,GetY=function() return 23 end}
      Players={[2]={GetUnits=function()
        aiReads=aiReads+1
        if aiReads==1 then error('temporarily unavailable') end
        if aiReads==2 then return {FindID=function() return nil end} end
        return {FindID=function() return unit end}
      end}}
      for i=1,800 do Events.UnitOperationStarted.fn(2,i,123) end
      assert(aiReads==512)
    ''')
    lines=[lua.globals().output[i] for i in range(1,len(lua.globals().output)+1)]
    assert 'delivery_snapshot=unavailable' in lines[1]
    assert 'delivery_snapshot=unavailable' in lines[2]
    assert 'delivery_x=12 delivery_y=23 delivery_faith=7 delivery_charges=1' in lines[3]


def test_after_both_window_and_raw_limits_callbacks_stop_reading_game_state():
    lua=runtime()
    lua.execute('''
      localReads,turnReads=0,0
      Game.GetLocalPlayer=function() localReads=localReads+1;return 1 end
      Game.GetCurrentGameTurn=function() turnReads=turnReads+1;return 42 end
      for i=1,3 do
        Events.UnitOperationStarted.fn(1,i,123)
        Events.GameCoreEventPublishComplete.fn();Events.GameCoreEventPublishComplete.fn()
      end
      for i=1,600 do
        Events.CityReligionChanged.fn(2,i,7)
        Events.UnitOperationStarted.fn(1,i,123)
        Events.UnitOperationStarted.fn(2,i,123)
      end
      Game.GetLocalPlayer=function() localReads=localReads+1;return -1 end
      for i=1,20 do Events.UnitOperationStarted.fn(2,i,123) end
      Game.GetLocalPlayer=function() localReads=localReads+1;return 1 end
      local beforeLocal,beforeTurn,beforeOutput=localReads,turnReads,#output
      for i=1,500 do
        Events.CityReligionChanged.fn(2,i,7);Events.UnitMoved.fn(1,i,1,2)
        Events.UnitOperationStarted.fn(1,i,123);GameEvents.OnUnitMoved.fn(1,i,1,2,3,4)
        Events.UnitTeleported.fn(1,i,1,2);Events.GameCoreEventPublishComplete.fn()
        Events.UnitChargesChanged.fn(1,i,0,1)
      end
      assert(localReads==beforeLocal and turnReads==beforeTurn and #output==beforeOutput)
    ''')

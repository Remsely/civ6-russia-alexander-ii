"""Stub exact shapes found in the local GameCore wrappers; no game claims."""
from pathlib import Path

from lupa import LuaRuntime


def runtime():
    lua=LuaRuntime(unpack_returned_tuples=True)
    lua.execute('''
      live, objects, calls, nextId = {}, {}, {owner=0, player=0, attach=0}, 100
      expected={'BIT1','BIT2','BIT4','BIT8','BIT16','BIT32'}
      effects={}
      effects.GetModifiers=function()
        local out={};for id in pairs(live) do out[#out+1]=id end;return out
      end
      effects.GetModifierDefinition=function(id)
        local v=live[id];if not v then return nil end
        return {Id=v.id,Type='DYNAMIC',Arguments={}}
      end
      effects.GetModifierOwner=function(id)
        calls.owner=calls.owner+1;local v=live[id];return v and v.object or nil
      end
      effects.GetObjectsPlayerId=function(id) calls.player=calls.player+1;return objects[id] end
      players={[1]={},[2]={}}
      function players[1]:AttachModifierByID(name)
        calls.attach=calls.attach+1;local id=nextId;nextId=nextId+1
        live[id]={id=name,object=501};objects[501]=1;return id
      end
    '''.replace('function players[1]:AttachModifierByID(name)', 'players[1].AttachModifierByID=function(self,name)'))
    adapter=lua.execute(Path('tools/experiments/religion_gameeffects_adapter.lua').read_text(encoding='utf-8'))
    attach=lua.execute(Path('tools/experiments/religion_modifier_attach.lua').read_text(encoding='utf-8'))
    lua.globals().api=adapter.new(lua.globals().effects,lua.globals().players)
    lua.globals().ensure=attach.ensure
    return lua


def test_actual_shapes_handle_owner_object_and_unrelated_ownerless_instances():
    lua=runtime()
    lua.execute('''
      -- An unrelated no-owner object must not trigger any owner lookup.
      live[1]={id='SOME_OTHER_MODIFIER'}
      local ok,ids=ensure(api,1,expected)
      assert(ok and #ids==6 and calls.attach==6 and calls.owner==6 and calls.player==6)
      assert(ensure(api,1,expected) and calls.attach==6)
    ''')


def test_valid_owner_object_not_equal_player_id_and_non_player_owner():
    lua=runtime()
    lua.execute('''
      live[1]={id='BIT1',object=900};objects[900]=2
      live[2]={id='BIT2',object=901} -- no associated player
      local ok=ensure(api,1,expected)
      assert(ok and calls.attach==6)
      assert(ensure(api,1,expected) and calls.attach==6)
    ''')


def test_disappearing_definition_or_invalid_owner_aborts_safely():
    lua=runtime()
    lua.execute('''
      effects.GetModifiers=function() return {55} end
      local ok,why=ensure(api,1,expected)
      assert(not ok and why=='describe_failed' and calls.attach==0)
      live[55]={id='BIT1',object='bad'}
      ok,why=ensure(api,1,expected)
      assert(not ok and why=='describe_failed' and calls.attach==0)
    ''')

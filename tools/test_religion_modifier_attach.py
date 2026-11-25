"""Test restart recovery using native instances as the authority."""
from pathlib import Path

from lupa import LuaRuntime


def runtime():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute('''
      live, savedMarker, nextId, scans, attachCount = {}, {}, 1, 0, 0
      failAfterAttach, failMarker, failDescribe = false, false, false
      expected={'BIT1','BIT2','BIT4','BIT8','BIT16','BIT32'}
      function create(owner,name)
        local id=nextId;nextId=nextId+1;live[id]={owner=owner,name=name};return id
      end
      api={
        instances=function()
          scans=scans+1;local ids={};for id in pairs(live) do ids[#ids+1]=id end;return ids
        end,
        describe=function(id)
          if failDescribe then error('unavailable') end
          local item=live[id];if not item then return nil,nil end
          return item.name,item.owner
        end,
        attach=function(owner,name)
          attachCount=attachCount+1;local id=create(owner,name)
          if failAfterAttach then failAfterAttach=false;error('response lost') end
          return id
        end,
        marker=function(owner,ids)
          if failMarker then error('storage failed') end
          savedMarker[owner]=ids
        end}
    ''')
    module = lua.execute(Path('tools/experiments/religion_modifier_attach.lua').read_text(encoding='utf-8'))
    lua.globals().ensure = module.ensure
    return lua


def test_empty_complete_and_unrelated_instances():
    lua = runtime()
    lua.execute('''
      create(3,'BIT1');create(1,'UNRELATED')
      local ok,ids=ensure(api,1,expected)
      assert(ok and #ids==6 and attachCount==6 and scans==1 and #savedMarker[1]==6)
      local again=ensure(api,1,expected)
      assert(again and attachCount==6 and scans==2)
    ''')


def test_every_partial_prefix_only_attaches_missing():
    for existing in range(1, 7):
        lua = runtime()
        lua.globals().existing = existing
        lua.execute('''
          for i=1,existing do create(1,expected[i]) end
          local ok,ids=ensure(api,1,expected)
          assert(ok and #ids==6 and attachCount==6-existing)
        ''')


def test_failure_after_native_attach_is_recovered_without_duplicate():
    lua = runtime()
    lua.execute('''
      failAfterAttach=true
      local ok,why=ensure(api,1,expected)
      assert(not ok and why=='attach_uncertain' and attachCount==1 and savedMarker[1]==nil)
      ok=ensure(api,1,expected)
      assert(ok and attachCount==6 and scans==2)
    ''')


def test_marker_failure_is_never_authority():
    lua = runtime()
    lua.execute('''
      failMarker=true
      assert(ensure(api,1,expected) and attachCount==6 and savedMarker[1]==nil)
      assert(ensure(api,1,expected) and attachCount==6)
    ''')


def test_duplicates_refuse_all_changes_even_with_valid_marker():
    lua = runtime()
    lua.execute('''
      local ok=ensure(api,1,expected);assert(ok)
      create(1,'BIT4')
      local old=attachCount;local result,why=ensure(api,1,expected)
      assert(not result and why=='duplicate_instance' and attachCount==old)
    ''')


def test_unavailable_snapshot_or_description_never_triggers_attach():
    lua = runtime()
    lua.execute('''
      create(3,'UNRELATED');failDescribe=true
      local result,why=ensure(api,1,expected)
      assert(not result and why=='describe_failed' and attachCount==0)
      failDescribe=false;api.instances=function() error('unavailable') end
      result,why=ensure(api,1,expected)
      assert(not result and why=='instances_unavailable' and attachCount==0)
    ''')

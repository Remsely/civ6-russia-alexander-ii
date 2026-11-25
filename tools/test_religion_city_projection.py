"""Recovery and pair isolation for the unconnected City projection prototype."""
from pathlib import Path

from lupa import LuaRuntime


def runtime():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute('''
      records, plots, capitals, owners, writes = {}, {}, {}, {}, {}
      failBitAt, bitWrites, failRecordAfterWrite = nil, 0, false
      api = {maxPlayers=16,
        get=function(key) return records[key] end,
        set=function(key,val)
          records[key]=val
          if failRecordAfterWrite then failRecordAfterWrite=false; error('write lost response') end
        end,
        capital=function(id) return capitals[id] end,
        owner=function(plot) return owners[plot] end,
        getBit=function(plot,key) return plots[plot] and plots[plot][key] end,
        setBit=function(plot,key,val)
          bitWrites=bitWrites+1
          if bitWrites==failBitAt then failBitAt=nil;error('injected interruption') end
          plots[plot]=plots[plot] or {};plots[plot][key]=val
          writes[#writes+1]={plot=plot,key=key,value=val}
        end}
      function projected(leader,plot)
        local score=0
        for _,w in ipairs({1,2,4,8,16,32}) do
          score=score+(plots[plot] and plots[plot]['REMSELY_REL_PROTOTYPE_'..leader..'_BIT_'..w] or 0)*w
        end
        return score
      end
      capitals[2]=100;owners[100]=2
      capitals[3]=200;owners[200]=3
    ''')
    source = Path('tools/experiments/religion_city_projection.lua').read_text(encoding='utf-8')
    module = lua.execute(source)
    lua.globals().factory = module
    lua.globals().driver = module.new(lua.globals().api)
    return lua


def test_cap_expiry_duplicates_and_both_kinds():
    lua = runtime()
    lua.execute('''
      local ok,val=driver.offense(1,2,'home',10,1)
      assert(ok and val==12 and projected(1,100)==12)
      ok,val=driver.offense(1,2,'abroad',11,2)
      assert(ok and val==18 and projected(1,100)==18)
      ok,val=driver.offense(1,2,'home',12,2)
      assert(not ok and val=='duplicate' and projected(1,100)==18)
      for seq=3,50 do assert(driver.offense(1,2,'home',12,seq)) end
      assert(projected(1,100)==54)
      -- Different buckets expire at different times; cap is on their total.
      ok,val=driver.expire(1,2,41);assert(ok and val==54 and projected(1,100)==54)
      ok,val=driver.expire(1,2,42);assert(ok and val==0 and projected(1,100)==0)
    ''')


def test_interrupted_projection_recovers_from_saved_authority_without_duplicate():
    lua = runtime()
    lua.execute('''
      assert(driver.offense(1,2,'home',10,1)); assert(projected(1,100)==12)
      bitWrites=0;failBitAt=2
      local ok=driver.offense(1,2,'abroad',11,2)
      assert(not ok and driver.inspect(1,2).seq==2)
      -- Simulate a fresh Lua runtime reading only saved records and plot bits.
      local restored=factory.new(api)
      assert(restored.reconcile(1,2)); assert(projected(1,100)==18)
      ok=restored.offense(1,2,'abroad',11,2)
      assert(not ok and projected(1,100)==18)
      assert(restored.offense(1,2,'abroad',12,3)); assert(projected(1,100)==20)
    ''')


def test_interrupted_authoritative_write_is_idempotent_on_retry():
    lua = runtime()
    lua.execute('''
      failRecordAfterWrite=true
      local ok=driver.offense(1,2,'home',10,1)
      assert(not ok and driver.inspect(1,2).seq==1 and projected(1,100)==0)
      ok=driver.offense(1,2,'home',10,1)
      assert(not ok and projected(1,100)==12)
    ''')


def test_capital_transfer_restores_captor_projection_without_cross_pair_damage():
    lua = runtime()
    lua.execute('''
      assert(driver.offense(1,2,'home',10,1))
      assert(driver.offense(1,3,'abroad',10,1))
      assert(projected(1,100)==12 and projected(1,200)==6)
      -- Player 2 changes capital; old plot belongs to 3 and is now 3's capital.
      capitals[2]=300;owners[300]=2;capitals[3]=100;owners[100]=3
      assert(driver.reconcile(1,2))
      assert(projected(1,100)==6 and projected(1,300)==12)
      -- Reconcile 3 removes its previous capital projection.
      assert(driver.reconcile(1,3))
      assert(projected(1,100)==6 and projected(1,200)==0 and projected(1,300)==12)
      capitals[2]=nil
      assert(driver.reconcile(1,2));assert(projected(1,300)==0)
    ''')


def test_interrupted_capital_move_retains_old_location_until_fully_reconciled():
    for fail_at in range(1, 5):
        lua = runtime()
        lua.globals().fail_at = fail_at
        lua.execute('''
          assert(driver.offense(1,2,'home',10,1));assert(projected(1,100)==12)
          capitals[2]=300;owners[100]=3;owners[300]=2
          bitWrites=0;failBitAt=fail_at
          local ok=driver.reconcile(1,2)
          assert(not ok and driver.inspect(1,2).projected==100)
          local restored=factory.new(api)
          assert(restored.reconcile(1,2))
          assert(projected(1,100)==0 and projected(1,300)==12)
          assert(restored.inspect(1,2).projected==300)
        ''')


def test_two_alexanders_keep_independent_bits_and_removals_precede_additions():
    lua = runtime()
    lua.execute('''
      assert(driver.offense(1,2,'home',10,1))
      assert(driver.offense(4,2,'abroad',10,1))
      assert(projected(1,100)==12 and projected(4,100)==6)
      writes={}
      assert(driver.offense(1,2,'abroad',11,2)) -- 12 -> 18: remove 4,8 then add 2,16
      local adding=false
      for _,x in ipairs(writes) do
        if x.value==1 then adding=true else assert(not adding,'removed after adding') end
      end
      assert(projected(1,100)==18 and projected(4,100)==6)
    ''')

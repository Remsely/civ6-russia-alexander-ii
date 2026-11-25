"""Unconnected seven-weight action host: controlled stubs, not gameplay."""
from pathlib import Path

from test_religion_verified_action_host import runtime as base_runtime


def runtime():
    lua = base_runtime()
    root = Path('tools/experiments')
    lua.globals().projection = lua.execute((root / 'religion_city_projection_75.lua').read_text(encoding='utf-8'))
    lua.globals().attach = lua.execute((root / 'religion_modifier_attach_75.lua').read_text(encoding='utf-8'))
    lua.globals().hostModule = lua.execute((root / 'religion_verified_action_host_75.lua').read_text(encoding='utf-8'))
    lua.execute('''
      modules={core=core,projection=projection,attach=attach,gameeffects=gameeffects}
      function createHost() return hostModule.new(modules,env) end
      function projected(leader,plot)
        local n=0;for _,w in ipairs({1,2,4,8,16,32,64}) do
          n=n+(plots[plot] and plots[plot]['REMSELY_REL_COMPONENT75_'..leader..'_BIT_'..w] or 0)*w
        end;return n
      end
      function expectedNames(leader,defs)
        local weights={1,2,4,8,16,32,64}
        if #defs~=#weights then return false end
        for i,w in ipairs(weights) do
          if defs[i]~='REMSELY_REL_COMPONENT75_'..leader..'_MOD_'..w then return false end
        end
        return true
      end
      env.confirmDefinitions=function(leader,defs)
        return definitionsAllowed and expectedNames(leader,defs)
      end
      host=createHost()
    ''')
    return lua


def test_attaches_all_seven_canonical_weights_and_caps_own_component():
    lua = runtime()
    lua.execute('''
      local home=action(1,2,1,-1,5)
      local foreign=action(1,2,3,7,5)
      assert(host.offense(home,10,1));assert(host.offense(foreign,11,2))
      assert(attachCount==7 and scans==1 and projected(1,100)==18)
      for _,w in ipairs({1,2,4,8,16,32,64}) do
        local found=0
        for _,item in pairs(live) do
          if item.name=='REMSELY_REL_COMPONENT75_1_MOD_'..w then found=found+1 end
        end
        assert(found==1)
      end
      for seq=3,50 do assert(host.offense(home,12,seq)) end
      assert(projected(1,100)==75 and host.inspect(1,2).seq==50 and attachCount==7)
      local ok,why=host.offense(home,12,50)
      assert(not ok and why=='duplicate' and projected(1,100)==75)
      assert(host.expire(1,2,42) and projected(1,100)==0)
    ''')


def test_interrupted_projection_and_repeated_restart_restore_without_duplicate_attachments():
    lua = runtime()
    lua.execute('''
      local home=action(1,2,1,-1,5)
      assert(host.offense(home,10,1));bitWrites=0;failBitAt=2
      local ok=host.offense(action(1,2,3,7,5),11,2)
      assert(not ok and host.inspect(1,2).seq==2)
      for i=1,3 do
        host=createHost()
        assert(host.reconcile(1,2) and projected(1,100)==18 and attachCount==7)
      end
      ok=host.offense(home,11,2);assert(not ok and projected(1,100)==18)
      assert(host.offense(home,12,3) and projected(1,100)==21 and attachCount==7)
    ''')


def test_lost_or_duplicate_seventh_modifier_and_distinct_leaders():
    lua = runtime()
    lua.execute('''
      local home=action(1,2,1,-1,5)
      assert(host.offense(home,10,1))
      assert(host.offense(action(4,2,3,7,5),10,1))
      assert(attachCount==14 and projected(1,100)==12 and projected(4,100)==6)
      for id,item in pairs(live) do
        if item.name=='REMSELY_REL_COMPONENT75_1_MOD_64' then live[id]=nil;break end
      end
      assert(host.offense(home,11,2) and attachCount==15 and projected(1,100)==15)
      local id=nextId;nextId=id+1
      live[id]={name='REMSELY_REL_COMPONENT75_1_MOD_64',object=1001};objects[1001]=1
      host.invalidate(1)
      local ok,why=host.offense(home,11,3)
      assert(not ok and why=='attachment_duplicate_instance' and host.inspect(1,2).seq==2)
    ''')


def test_rejects_unverified_or_mutated_definition_set_without_state_changes():
    lua = runtime()
    lua.execute('''
      local home=action(1,2,1,-1,5)
      actionAllowed=false;assert(not host.offense(home,10,1));actionAllowed=true
      baselineAllowed=false;assert(not host.offense(home,10,1));baselineAllowed=true
      definitionsAllowed=false;assert(not host.offense(home,10,1));definitionsAllowed=true
      env.confirmDefinitions=function(leader,defs)
        defs[7]='SOME_OTHER_MODIFIER';return true
      end
      local ok,why=host.offense(home,10,1)
      assert(not ok and why=='definitions_unavailable' and attachCount==0 and recordWrites==0)
    ''')


def test_uncertain_attachment_recovers_by_scanning_seven_live_instances():
    lua = runtime()
    lua.execute('''
      local home=action(1,2,1,-1,5);failAfterAttach=true
      local ok,why=host.offense(home,10,1)
      assert(not ok and why=='attachment_attach_uncertain' and recordWrites==0)
      assert(host.offense(home,10,1) and attachCount==7 and projected(1,100)==12)
      host=createHost()
      assert(host.reconcile(1,2) and attachCount==7 and projected(1,100)==12)
    ''')


def test_eligible_foreign_city_and_restoration_after_capital_move():
    lua = runtime()
    lua.execute('''
      local foreign=action(1,2,3,7,5)
      assert(host.offense(foreign,10,1) and projected(1,100)==6)
      local unprotected=action(1,2,3,8,5)
      assert(not host.offense(unprotected,10,2) and projected(1,100)==6)
      capitals[2]=300;owners[100]=3;owners[300]=2
      host=createHost()
      assert(host.reconcile(1,2))
      assert(projected(1,100)==0 and projected(1,300)==6 and attachCount==7)
    ''')

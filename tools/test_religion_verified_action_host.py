"""Integration of the unconnected action host against real experimental modules."""
from pathlib import Path

from lupa import LuaRuntime


def runtime():
    lua=LuaRuntime(unpack_returned_tuples=True)
    lua.execute('''
      records,plots,owners,capitals,live,objects={},{},{},{},{},{}
      nextId,attachCount,recordWrites,scans=100,0,0,0
      leaderAllowed,offenseAllowed,actionAllowed,baselineAllowed,definitionsAllowed=true,true,true,true,true
      failAfterAttach,failBitAt,bitWrites=false,nil,0
      capitals[2]=100;owners[100]=2;capitals[3]=200;owners[200]=3
      storage={maxPlayers=16,
        get=function(k) return records[k] end,
        set=function(k,v) recordWrites=recordWrites+1;records[k]=v end,
        capital=function(p) return capitals[p] end,owner=function(p) return owners[p] end,
        getBit=function(p,k) return plots[p] and plots[p][k] end,
        setBit=function(p,k,v)
          bitWrites=bitWrites+1
          if bitWrites==failBitAt then failBitAt=nil;error('interrupted projection') end
          plots[p]=plots[p] or {};plots[p][k]=v
        end}
      function projected(leader,plot)
        local n=0;for _,w in ipairs({1,2,4,8,16,32}) do
          n=n+(plots[plot] and plots[plot]['REMSELY_REL_PROTOTYPE_'..leader..'_BIT_'..w] or 0)*w
        end;return n
      end
      effects={}
      effects.GetModifiers=function() scans=scans+1;local r={};for id in pairs(live) do r[#r+1]=id end;return r end
      effects.GetModifierDefinition=function(id) local x=live[id];if x then return {Id=x.name} end end
      effects.GetModifierOwner=function(id) local x=live[id];if x then return x.object end end
      effects.GetObjectsPlayerId=function(id) return objects[id] end
      players={}
      for _,leader in ipairs({1,4}) do
        players[leader]={AttachModifierByID=function(self,name)
          local id=nextId;nextId=nextId+1;attachCount=attachCount+1
          local object=1000+leader;live[id]={name=name,object=object};objects[object]=leader
          if failAfterAttach then failAfterAttach=false;error('lost attach response') end
          return id
        end}
      end
      function names(leader)
        local r={};for _,w in ipairs({1,2,4,8,16,32}) do r[#r+1]='BIT_'..leader..'_'..w end;return r
      end
      env={projection=storage,effects=effects,players=players,definitions=names,
        confirmDefinitions=function(leader,defs) return definitionsAllowed end,
        eligibleLeader=function(leader) return leaderAllowed and (leader==1 or leader==4) end,
        eligibleOffense=function(leader,actor) return offenseAllowed and (actor==2 or actor==3) end,
        validateVerifiedAction=function(action,turn,seq) return actionAllowed end,
        confirmBaseline=function(leader) return baselineAllowed end}
      function action(leader,actor,owner,before,faith)
        return {leader=leader,actor=actor,cityOwner=owner,cityID=55,beforeReligion=before,
          unitReligion=faith,leaderReligion=7,known=true,alexanderAI=true,success=true,candidateCount=1}
      end
    ''')
    paths={'core':'religious_agenda_core.lua','projection':'religion_city_projection.lua',
           'attach':'religion_modifier_attach.lua','gameeffects':'religion_gameeffects_adapter.lua',
           'hostModule':'religion_verified_action_host.lua'}
    for name,filename in paths.items():
        lua.globals()[name]=lua.execute(Path('tools/experiments',filename).read_text(encoding='utf-8'))
    lua.execute('''
      modules={core=core,projection=projection,attach=attach,gameeffects=gameeffects}
      function createHost() return hostModule.new(modules,env) end
      host=createHost()
    ''')
    return lua


def test_home_foreign_repeats_and_per_leader_cap():
    lua=runtime()
    lua.execute('''
      local home=action(1,2,1,-1,5)
      local foreign=action(1,2,3,7,5)
      local ok,value=host.offense(home,10,1)
      assert(ok and value==12 and projected(1,100)==12 and attachCount==6 and scans==1)
      ok,value=host.offense(foreign,11,2)
      assert(ok and value==18 and projected(1,100)==18 and scans==1)
      ok,value=host.offense(foreign,11,2)
      assert(not ok and value=='duplicate' and projected(1,100)==18)
      for n=3,50 do assert(host.offense(home,12,n)) end
      assert(projected(1,100)==54 and host.inspect(1,2).seq==50 and scans==1)
      ok,value=host.expire(1,2,42);assert(ok and value==0 and projected(1,100)==0)
    ''')


def test_rejects_invalid_faith_human_nonmajor_stale_and_undocumented_action():
    lua=runtime()
    lua.execute('''
      local bad=action(1,2,3,5,5);assert(not host.offense(bad,10,1)) -- abroad not our faith
      bad=action(1,2,3,7,7);assert(not host.offense(bad,10,1)) -- same faith
      bad=action(1,2,1,-1,5);bad.alexanderAI=false;assert(not host.offense(bad,10,1))
      bad.alexanderAI=true;bad.known=false;assert(not host.offense(bad,10,1))
      bad.known=true;bad.success=false;assert(not host.offense(bad,10,1))
      bad.success=true;bad.candidateCount=2;assert(not host.offense(bad,10,1))
      bad.candidateCount=1;actionAllowed=false;assert(not host.offense(bad,10,1))
      actionAllowed=true;offenseAllowed=false;assert(not host.offense(bad,10,1))
      offenseAllowed=true;leaderAllowed=false;assert(not host.offense(bad,10,1))
      leaderAllowed=true;baselineAllowed=false;assert(not host.offense(bad,10,1))
      baselineAllowed=true;definitionsAllowed=false;assert(not host.offense(bad,10,1))
      assert(recordWrites==0 and attachCount==0 and projected(1,100)==0)
    ''')


def test_failed_or_duplicate_attachment_blocks_state_and_retries_safely():
    lua=runtime()
    lua.execute('''
      local a=action(1,2,1,-1,5);failAfterAttach=true
      local ok,why=host.offense(a,10,1)
      assert(not ok and why=='attachment_attach_uncertain' and recordWrites==0 and projected(1,100)==0)
      assert(host.offense(a,10,1) and attachCount==6 and projected(1,100)==12)
      -- Force a fresh scan; duplicate instances cannot silently add effects.
      local id=nextId;nextId=id+1;live[id]={name='BIT_1_4',object=1001};objects[1001]=1
      host.invalidate(1)
      ok,why=host.offense(a,11,2)
      assert(not ok and why=='attachment_duplicate_instance' and host.inspect(1,2).seq==1)
    ''')


def test_recovery_after_interrupted_projection_and_restart():
    lua=runtime()
    lua.execute('''
      local a=action(1,2,1,-1,5)
      assert(host.offense(a,10,1));bitWrites=0;failBitAt=2
      local ok=host.offense(action(1,2,3,7,5),11,2)
      assert(not ok and host.inspect(1,2).seq==2)
      host=createHost()
      assert(host.reconcile(1,2) and projected(1,100)==18 and attachCount==6)
      ok=host.offense(a,11,2);assert(not ok and projected(1,100)==18)
      assert(host.offense(a,12,3) and projected(1,100)==21)
    ''')


def test_two_leaders_capital_replacement_and_lost_handle():
    lua=runtime()
    lua.execute('''
      assert(host.offense(action(1,2,1,-1,5),10,1))
      assert(host.offense(action(4,2,3,7,5),10,1))
      assert(attachCount==12 and projected(1,100)==12 and projected(4,100)==6)
      capitals[2]=300;owners[100]=3;owners[300]=2
      assert(host.reconcile(1,2) and host.reconcile(4,2))
      assert(projected(1,100)==0 and projected(4,100)==0)
      assert(projected(1,300)==12 and projected(4,300)==6)
      -- A removed native effect invalidates the cached handle; rescan and reattach.
      for id,item in pairs(live) do if item.name=='BIT_1_4' then live[id]=nil;break end end
      assert(host.offense(action(1,2,1,-1,5),11,2) and attachCount==13)
      assert(projected(1,300)==15 and projected(4,300)==6)
      capitals[2]=nil
      assert(host.reconcile(1,2) and host.reconcile(4,2))
      assert(projected(1,300)==0 and projected(4,300)==0)
    ''')


def test_changed_definition_mapping_blocks_even_with_cached_handles():
    lua=runtime()
    lua.execute('''
      local a=action(1,2,1,-1,5)
      assert(host.offense(a,10,1) and projected(1,100)==12)
      local prior=recordWrites;definitionsAllowed=false
      local ok,why=host.offense(a,11,2)
      assert(not ok and why=='definitions_unavailable')
      assert(recordWrites==prior and host.inspect(1,2).seq==1 and projected(1,100)==12)
    ''')

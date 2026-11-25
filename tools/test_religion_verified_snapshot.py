"""Contract tests for the experimental snapshot adapter, not engine delivery."""
from pathlib import Path

import pytest
from lupa import LuaRuntime


@pytest.fixture
def lua():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.globals().target = lua.execute(Path('tools/experiments/religion_spread_target.lua').read_text(encoding='utf-8'))
    lua.globals().adapter = lua.execute(Path('tools/experiments/religion_verified_snapshot.lua').read_text(encoding='utf-8'))
    lua.execute('''
      function fresh()
        local s={actor=2,leader=1,actorAliveMajor=true,leaderAliveAI=true,known=true,
          turn=50,sequence=2,x=5,y=5,noForeignSpread=false,unitReligion=3,leaderReligion=4,
          evidence={successfulOperation=true,exactBeforeState=true,orderedEvents=true,
            completeMap=true,unitIdentity=true,lifecycleHandled=true,uniquePersistentSequence=true},
          cells={}}
        for i=0,6 do s.cells[i]={exists=true,x=5+i,y=5,cityKnown=true} end
        return s
      end
      function city(owner,id,faith) return {owner=owner,id=id,beforeReligion=faith} end
      function check(s) return adapter.attribute(target,s) end
    ''')
    return lua


def test_home_and_foreign_city_use_same_pre_operation_snapshot(lua):
    lua.execute('''
      local s=fresh(); s.cells[1].city=city(1,100,3)
      local action,reason=check(s)
      assert(reason==nil and action.cityOwner==1 and action.cityID==100 and action.beforeReligion==3)
      assert(action.actor==2 and action.leader==1 and action.success and action.candidateCount==1)
      s.cells[1].city=city(7,101,4); action,reason=check(s)
      assert(reason==nil and action.cityOwner==7 and action.cityID==101)
      s.cells[1].city=city(2,102,4); action,reason=check(s)
      assert(reason==nil and action.cityOwner==2)
      s.cells[1].city=city(7,101,5); action,reason=check(s)
      assert(action==nil and reason=='unprotected_city')
    ''')


def test_target_order_own_city_priority_and_no_foreign_spread(lua):
    lua.execute('''
      local s=fresh(); s.cells[0].city=city(2,10,4); s.cells[1].city=city(1,11,4)
      local a=check(s); assert(a.cityID==10) -- own unit's tile has priority
      s.cells[0].city=city(7,12,4); a=check(s); assert(a.cityID==11)
      s.noForeignSpread=true; local _,reason=check(s); assert(reason=='no_eligible_target')
      s.cells[2].city=city(2,13,4); a=check(s); assert(a.cityID==13)
    ''')


def test_all_evidence_must_be_provided_not_assumed(lua):
    lua.execute('''
      for _,name in ipairs({'successfulOperation','exactBeforeState','orderedEvents',
        'completeMap','unitIdentity','lifecycleHandled','uniquePersistentSequence'}) do
        local s=fresh(); s.cells[1].city=city(1,1,4); s.evidence[name]=nil
        local action,reason=check(s); assert(action==nil and reason=='unverified_evidence',name)
      end
    ''')


def test_incomplete_or_inconsistent_map_is_not_treated_as_empty(lua):
    lua.execute('''
      local s=fresh(); s.cells[1].city=city(1,1,4); s.cells[2]=nil
      local a,r=check(s); assert(a==nil and r=='incomplete_map')
      s=fresh(); s.cells[1].city=city(1,1,4); s.cells[2].cityKnown=false
      a,r=check(s); assert(a==nil and r=='incomplete_map')
      s=fresh(); s.cells[1].city=city(1,1,4); s.cells[2]={exists=false}
      a,r=check(s); assert(a.cityID==1 and r==nil)
      s=fresh(); s.cells[1].city=city(1,1,4); s.cells[2].x=s.cells[1].x
      a,r=check(s); assert(a==nil and r=='inconsistent_map')
    ''')


def test_missing_prestate_wrong_faith_and_unverified_actor_declined(lua):
    lua.execute('''
      local s=fresh(); s.cells[1].city=city(1,1,nil)
      local a,r=check(s); assert(a==nil and r=='invalid_city')
      s=fresh(); s.cells[1].city=city(1,1,4); s.unitReligion=4
      a,r=check(s); assert(a==nil and r=='same_faith')
      s=fresh(); s.cells[1].city=city(1,1,4); s.noForeignSpread=nil
      a,r=check(s); assert(a==nil and r=='invalid_unit')
      s=fresh(); s.cells[1].city=city(1,1,4); s.actorAliveMajor=false
      a,r=check(s); assert(a==nil and r=='invalid_participants')
      s=fresh(); s.cells[1].city=city(1,1,4); s.sequence=0
      a,r=check(s); assert(a==nil and r=='invalid_participants')
    ''')


def test_target_failure_or_absence_does_not_emit_action(lua):
    lua.execute('''
      local s=fresh(); s.cells[1].city=city(1,1,4)
      local action,reason=adapter.attribute({find=function() error('bad selector') end},s)
      assert(action==nil and reason=='target_error')
      s.cells[1].city=nil; action,reason=check(s)
      assert(action==nil and reason=='no_eligible_target')
    ''')

"""Classification contracts only: engine attribution is not established."""
from pathlib import Path

import pytest
from lupa import LuaRuntime


@pytest.fixture
def lua():
    runtime = LuaRuntime(unpack_returned_tuples=True)
    runtime.globals().core = runtime.execute(
        Path('tools/experiments/religion_offense_decision.lua').read_text(encoding='utf-8')
    )
    runtime.execute('''
      function action(owner, before)
        return {leader=1, actor=2, cityOwner=owner, cityID=42,
          beforeReligion=before, leaderReligion=7, unitReligion=5,
          turn=90, sequence=123, known=true, alexanderAI=true, success=true,
          candidateCount=1, verifiedPrestate=true, verifiedActor=true,
          durableSequence=true}
      end
      function change(owner, before, after)
        return {owner=owner,cityID=42,turn=90,sequence=123,
          beforeReligion=before,afterReligion=after,verifiedLink=true}
      end
    ''')
    return runtime


def test_own_city_spread_and_foreign_city_require_prior_faith(lua):
    lua.execute('''
      local a=action(1,-1)
      local result,reason=core.classify(a)
      assert(result.kind=='home' and result.majorityChanged==nil and reason==nil)
      a=action(3,7);result,reason=core.classify(a)
      assert(result.kind=='abroad' and result.majorityChanged==nil and reason==nil)
      -- The offender can spread another faith in its own city which formerly
      -- followed the leader's faith; it is still a foreign protected city.
      a=action(2,7); result=core.classify(a);assert(result.kind=='abroad')
      a=action(3,5);result,reason=core.classify(a)
      assert(result==nil and reason=='unprotected_city')
      a=action(3,-1);result,reason=core.classify(a)
      assert(result==nil and reason=='unprotected_city')
    ''')


def test_majority_change_requires_verified_causal_link(lua):
    lua.execute('''
      local a=action(3,7);local c=change(3,7,5)
      local result,reason=core.classify(a,c)
      assert(result.kind=='abroad' and result.majorityChanged and reason==nil)
      c.afterReligion=7;result,reason=core.classify(a,c)
      assert(result.kind=='abroad' and not result.majorityChanged and reason==nil)
      c.afterReligion=3;result,reason=core.classify(a,c)
      assert(result==nil and reason=='unrelated_majority')
      c=change(3,7,5);c.verifiedLink=false;result,reason=core.classify(a,c)
      assert(result==nil and reason=='unverified_city_change')
      for _,field in ipairs({'owner','cityID','turn','sequence','beforeReligion'}) do
        c=change(3,7,5);c[field]=999;result,reason=core.classify(a,c)
        assert(result==nil and reason=='unverified_city_change',field)
      end
    ''')


def test_incomplete_evidence_and_same_religion_do_not_create_offense(lua):
    lua.execute('''
      for _,field in ipairs({'known','alexanderAI','success','verifiedPrestate',
          'verifiedActor','durableSequence'}) do
        local a=action(1,7);a[field]=nil
        local result,reason=core.classify(a)
        assert(result==nil and reason=='unverified_action',field)
      end
      local a=action(1,7);a.candidateCount=2
      local result,reason=core.classify(a)
      assert(result==nil and reason=='unverified_action')
      a=action(1,7);a.unitReligion=7;result,reason=core.classify(a)
      assert(result==nil and reason=='same_religion')
      a=action(1,7);a.actor=1;result,reason=core.classify(a)
      assert(result==nil and reason=='invalid_action')
    ''')


def test_unvalidated_ids_and_sequence_are_rejected(lua):
    lua.execute('''
      for _,field in ipairs({'actor','leader','cityOwner','cityID','beforeReligion',
          'leaderReligion','unitReligion','turn','sequence'}) do
        local a=action(1,7);a[field]=nil
        local result,reason=core.classify(a)
        assert(result==nil and reason=='invalid_action',field)
      end
      local a=action(3,7);a.sequence=0
      local result,reason=core.classify(a)
      assert(result==nil and reason=='invalid_action')
      a=action(3,7);a.turn=0/0;result,reason=core.classify(a)
      assert(result==nil and reason=='invalid_action')
    ''')

"""Pure founder rivalry model; does not prove gameplay delivery or actor."""
from pathlib import Path

from lupa import LuaRuntime


def runtime():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.globals().model = lua.execute(
        Path('tools/experiments/religion_founder_rivalry.lua').read_text(encoding='utf-8')
    )
    lua.execute('''
      function event(seq, majority, owner, founder, founderReligion, unitCauseVerified)
        return {leader=1,cityOwner=owner or 3,cityID=44,leaderReligion=7,
          majority=majority,sequence=seq,founder=founder,
          founderReligion=founderReligion,founderEligible=true,
          unitCauseVerified=unitCauseVerified}
      end
    ''')
    return lua


def test_foreign_change_names_founder_as_rival_not_source_of_pressure():
    lua = runtime()
    lua.execute('''
      local state, result, why = model.observe(nil, event(1,7))
      assert(state and not result and why=='baseline')
      local nextState, rivalry
      nextState, rivalry, why = model.observe(state, event(2,5,3,4,5,true))
      assert(why=='rivalry' and rivalry.rival==4 and rivalry.basis=='religion_founder')
      assert(rivalry.cityOwner==3 and rivalry.previousReligion==7 and rivalry.newReligion==5)
      assert(rivalry.actor==nil and rivalry.source==nil)
      assert(state.majority==7 and nextState.majority==5)
      local _, repeated
      _, repeated, why = model.observe(nextState, event(2,5,3,4,5))
      assert(not repeated and why=='duplicate_or_stale')
      _, repeated, why = model.observe(nextState, event(3,5,3,4,5))
      assert(not repeated and why=='unprotected_before')
    ''')


def test_own_city_and_nonprotected_or_no_change_are_ignored():
    lua = runtime()
    lua.execute('''
      local own = model.observe(nil,event(1,7,1))
      local _, result, why = model.observe(own,event(2,5,1,4,5))
      assert(not result and why=='home_skipped')
      local foreign = model.observe(nil,event(1,7,3))
      _, result, why = model.observe(foreign,event(2,7,3,4,5))
      assert(not result and why=='unchanged')
      local other = model.observe(nil,event(1,6,3))
      _, result, why = model.observe(other,event(2,5,3,4,5))
      assert(not result and why=='unprotected_before')
      _, result, why = model.observe(foreign,event(2,-1,3))
      assert(not result and why=='no_new_religion')
    ''')


def test_unknown_or_ineligible_founder_is_not_misidentified():
    lua = runtime()
    lua.execute('''
      local state = model.observe(nil,event(1,7))
      local nextState, result, why = model.observe(state,event(2,5,3,nil,nil,true))
      assert(nextState.majority==5 and not result and why=='founder_unknown')
      _, result, why = model.observe(state,event(2,5,3,4,6,true))
      assert(not result and why=='founder_unknown')
      _, result, why = model.observe(state,event(2,5,3,1,5,true))
      assert(not result and why=='self_founder')
      local notEligible=event(2,5,3,4,5,true);notEligible.founderEligible=false
      _, result, why=model.observe(state,notEligible)
      assert(not result and why=='founder_ineligible')
    ''')


def test_sequence_and_city_identity_must_be_preserved_externally():
    lua = runtime()
    lua.execute('''
      local state=model.observe(nil,event(7,7))
      local nextState, result, why=model.observe(state,event(6,5,3,4,5))
      assert(nextState==state and not result and why=='duplicate_or_stale')
      local different=event(8,5,2,4,5)
      nextState,result,why=model.observe(state,different)
      assert(not nextState and not result and why=='invalid_previous')
      local invalid=event(8,5,3,4,5);invalid.sequence=nil
      nextState,result,why=model.observe(state,invalid)
      assert(not nextState and not result and why=='invalid_event')
    ''')


def test_reconversion_and_later_new_loss_are_separate_transitions():
    lua = runtime()
    lua.execute('''
      local state=model.observe(nil,event(1,7))
      local result
      state,result=model.observe(state,event(2,5,3,4,5,true));assert(result)
      state,result=model.observe(state,event(3,7));assert(not result)
      state,result=model.observe(state,event(4,5,3,4,5,true));assert(result)
    ''')


def test_passive_or_unattributed_loss_never_penalizes_founder():
    lua = runtime()
    lua.execute('''
      local initial = model.observe(nil, event(1,7))
      for _, transition in ipairs({event(2,5,3,4,5), event(2,5,3,4,5,false)}) do
        local state, penalty, why = model.observe(initial, transition)
        assert(state.majority==5 and not penalty and why=='unit_cause_unverified')
        local nextState, duplicatePenalty, duplicateWhy = model.observe(state,event(3,5,3,4,5,true))
        assert(nextState.majority==5 and not duplicatePenalty and duplicateWhy=='unprotected_before')
      end
    ''')

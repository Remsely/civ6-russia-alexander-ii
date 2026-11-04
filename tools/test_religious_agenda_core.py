from pathlib import Path
from lupa import LuaRuntime

SOURCE = Path(__file__).parent / 'experiments' / 'religious_agenda_core.lua'

def setup():
    lua = LuaRuntime(unpack_returned_tuples=True)
    core = lua.execute(SOURCE.read_text(encoding='utf-8-sig'))
    state = lua.table()
    action = lua.table_from(dict(actor=1, leader=0, cityOwner=2, known=True,
        alexanderAI=True, success=True, candidateCount=1, beforeReligion=3,
        leaderReligion=3, unitReligion=4))
    calls = []
    def apply(delta):
        calls.append(delta)
        return True
    return lua, core, state, action, calls, apply

def test_foreign_accumulates_with_cap_and_expires_after_reload():
    lua, core, state, action, calls, apply = setup()
    for turn in range(10, 24):
        assert core.offense(state, action, turn, apply)
    assert calls == [-6] + [-2] * 12
    assert state.abroad == 30 and state.abroadExpires == 53
    restored = lua.table_from(dict(abroad=state.abroad, abroadExpires=state.abroadExpires))
    assert not core.expire(restored, 52, apply)
    assert core.expire(restored, 53, apply)
    assert sum(calls) == 0

def test_home_and_abroad_have_independent_expiry_and_bounded_total():
    _, core, state, action, calls, apply = setup()
    for turn in range(1, 15):
        assert core.offense(state, action, turn, apply)
    action.cityOwner = 0
    for turn in range(15, 33):
        assert core.offense(state, action, turn, apply)
    assert state.home == 60 and state.abroad == 30
    assert sum(calls) == -75
    assert core.expire(state, 44, apply)
    assert sum(calls) == -60
    assert core.expire(state, 62, apply)
    assert sum(calls) == 0

def test_reject_innocent_ambiguous_and_ineligible_cases():
    for field, value in [('success', False), ('candidateCount', 2), ('candidateCount', 0),
                         ('beforeReligion', 4), ('beforeReligion', -1), ('unitReligion', 3),
                         ('unitReligion', -1), ('known', False), ('alexanderAI', False),
                         ('cityOwner', 1), ('actor', 0)]:
        _, core, state, action, calls, apply = setup()
        action[field] = value
        assert not core.offense(state, action, 1, apply), field
        assert calls == [] and state.abroad is None and state.home is None

def test_failed_diplomacy_write_does_not_advance_state():
    _, core, state, action, calls, apply = setup()
    assert not core.offense(state, action, 1, lambda delta: False)
    assert state.abroad is None
    assert core.offense(state, action, 1, apply)
    assert not core.expire(state, 31, lambda delta: False)
    assert state.abroadExpires == 31
    assert core.expire(state, 32, apply)

def test_matching_requires_one_city_same_turn_and_actual_gain():
    lua, core, _, action, _, _ = setup()
    assert core.start(action, lua.table_from([]), 4) is None
    assert core.start(action, lua.table_from([11, 12]), 4) is None
    token = core.start(action, lua.table_from([11]), 4)
    assert core.cityChanged(token, 12, 4, 1, 2) is None
    assert core.cityChanged(token, 11, 5, 1, 2) is None
    assert core.cityChanged(token, 11, 4, 1, 2) is not None
    assert core.cityChanged(token, 11, 4, 1, 3) is None
    token = core.start(action, lua.table_from([11]), 4)
    assert core.cityChanged(token, 11, 4, 2, 2) is None
    assert core.cityChanged(token, 11, 4, 2, 3) is None

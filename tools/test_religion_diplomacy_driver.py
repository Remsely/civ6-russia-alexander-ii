"""Tests for an isolated adapter, not Civ VI's event or save semantics."""

from pathlib import Path

import pytest
from lupa import LuaError, LuaRuntime


ROOT = Path(__file__).parent
CORE = ROOT / "experiments" / "religious_agenda_core.lua"
DRIVER = ROOT / "experiments" / "religion_diplomacy_driver.lua"
PREFIX = "REMSELY_RELIGION_TEST_V1_"


class FakeGame:
    def __init__(self):
        self.properties = {}
        self.scores = {}
        self.calls = []
        self.set_calls = 0
        self.fail_set_at = None
        self.fail_set_after = False
        self.fail_get = False
        self.get_calls = 0
        self.fail_get_at = None
        self.fail_adjust = None
        self.confirmed = True
        self.eligible = True

    def get(self, key):
        self.get_calls += 1
        if self.fail_get or self.get_calls == self.fail_get_at:
            raise RuntimeError("read failed")
        return self.properties.get(key)

    def set(self, key, value):
        self.set_calls += 1
        failing = self.set_calls == self.fail_set_at
        if failing and not self.fail_set_after:
            raise RuntimeError("write did not happen")
        self.properties[key] = value
        if failing:
            raise RuntimeError("write happened before error")

    def adjust(self, leader, offender, delta):
        if self.fail_adjust == "before":
            raise RuntimeError("native call failed")
        self.calls.append((leader, offender, delta))
        self.scores[(leader, offender)] = self.scores.get((leader, offender), 0) + delta
        if self.fail_adjust == "after":
            raise RuntimeError("native call changed state before error")
        if self.fail_adjust == "false":
            return False  # hostile API may return failure after changing state
        # Civ's void-style native method may also return nil on success.
        return None

    def validate(self, leader, offender):
        return self.eligible

    def baseline(self):
        return self.confirmed


def make(game=None, max_players=16):
    game = game or FakeGame()
    lua = LuaRuntime(unpack_returned_tuples=True)
    core = lua.execute(CORE.read_text(encoding="utf-8-sig"))
    factory = lua.execute(DRIVER.read_text(encoding="utf-8-sig"))
    as_lua = lua.eval("function(f) return function(...) return f(...) end end")
    api = lua.table_from(
        dict(core=core, get=as_lua(game.get), set=as_lua(game.set), adjust=as_lua(game.adjust),
             validatePair=as_lua(game.validate), confirmBaseline=as_lua(game.baseline), maxPlayers=max_players)
    )
    return lua, game, factory.new(api)


def action(lua, leader=0, offender=1, owner=2, before=3, leader_religion=3, unit_religion=4):
    return lua.table_from(dict(actor=offender, leader=leader, cityOwner=owner, known=True,
                               alexanderAI=True, success=True, candidateCount=1,
                               beforeReligion=before, leaderReligion=leader_religion,
                               unitReligion=unit_religion))


def test_independent_pairs_and_replay_survive_recreated_driver():
    lua, game, driver = make()
    assert driver.offense(0, 1, action(lua), 5, 1) == (True, "applied")
    assert driver.offense(0, 2, action(lua, offender=2, owner=2), 5, 1) == (True, "applied")
    assert game.scores == {(0, 1): -6, (0, 2): -6}
    assert driver.offense(0, 1, action(lua), 6, 2) == (True, "applied")
    lua2, _, restored = make(game)
    assert restored.offense(0, 1, action(lua2), 6, 2) == (False, "stale_or_duplicate")
    assert restored.offense(0, 1, action(lua2), 7, 1) == (False, "stale_or_duplicate")
    assert restored.offense(0, 1, action(lua2), 7, 3) == (True, "applied")
    assert game.scores == {(0, 1): -10, (0, 2): -6}


@pytest.mark.parametrize("leader,other", [(-1, 1), (0, -1), (0, 16), (16, 1), (0, 0), (0.5, 1)])
def test_invalid_player_ids_never_reach_native_method(leader, other):
    lua, game, driver = make()
    driver.offense(leader, other, action(lua, leader=leader, offender=other), 1, 1)
    assert game.calls == []
    assert game.properties == {}


def test_pair_and_baseline_are_checked_before_any_write():
    lua, game, driver = make()
    game.eligible = False
    assert driver.offense(0, 1, action(lua), 1, 1) == (False, "invalid_pair")
    game.eligible = True
    game.confirmed = False
    assert driver.offense(0, 1, action(lua), 1, 1) == (False, "unconfirmed_baseline")
    assert game.calls == [] and game.properties == {}


def test_player_id_bound_follows_inspected_native_array_size():
    with pytest.raises(LuaError):
        make(max_players=65)
    lua, game, driver = make(max_players=64)
    assert driver.offense(0, 64, action(lua, offender=64), 1, 1) == (False, "invalid_pair")
    assert game.calls == []
    assert driver.offense(0, 63, action(lua, offender=63), 1, 1) == (True, "applied")
    assert game.calls == [(0, 63, -6)]


def test_cap_and_expiry_refund_only_own_contribution():
    lua, game, driver = make()
    home = action(lua, owner=0, before=7)
    for seq in range(1, 16):
        assert driver.offense(0, 1, home, seq, seq)[0]
    assert game.scores[(0, 1)] == -54
    foreign = action(lua, owner=2)
    assert driver.offense(0, 1, foreign, 16, 16) == (True, "recorded")
    assert game.scores[(0, 1)] == -54
    # Other modifiers' effects do not belong to this driver's ledger.
    game.scores[(0, 1)] -= 4
    assert driver.expire(0, 1, 45) == (True, "applied")
    assert game.scores[(0, 1)] == -10  # foreign six + independent four
    assert driver.expire(0, 1, 45) == (False, "not_due")
    assert driver.expire(0, 1, 46) == (True, "applied")
    assert game.scores[(0, 1)] == -4


def test_new_action_settles_overdue_bucket_in_one_adjustment():
    lua, game, driver = make()
    assert driver.offense(0, 1, action(lua), 0, 1)[0]
    assert driver.offense(0, 1, action(lua, owner=0), 35, 2)[0]
    assert game.calls == [(0, 1, -6), (0, 1, -6)]  # +6 expired, -12 new
    assert game.scores[(0, 1)] == -12


def test_failed_intent_write_never_calls_native_method():
    lua, game, driver = make()
    game.fail_set_at = 1
    assert driver.offense(0, 1, action(lua), 1, 1) == (False, "storage_uncertain")
    assert game.calls == []
    assert driver.offense(0, 1, action(lua), 1, 1) == (False, "pending_reconciliation")
    # Failure was before the write; a new instance sees the old state.
    lua2, _, restored = make(game)
    assert restored.offense(0, 1, action(lua2), 1, 1) == (True, "applied")


def test_written_intent_is_recognized_even_if_setter_throws_after_write():
    lua, game, driver = make()
    game.fail_set_at = 1
    game.fail_set_after = True
    assert driver.offense(0, 1, action(lua), 1, 1) == (True, "applied")
    assert game.calls == [(0, 1, -6)]


@pytest.mark.parametrize("moment", ["before", "after", "false"])
def test_uncertain_native_failure_is_never_automatically_retried(moment):
    lua, game, driver = make()
    game.fail_adjust = moment
    assert driver.offense(0, 1, action(lua), 1, 1) == (False, "adjustment_uncertain")
    before = list(game.calls)
    saved = game.properties[PREFIX + "0_1"]
    assert saved.startswith("1:P:1:C:0:0:-1:-1:0|1:C:0:6:-1:31:1|-6")
    game.fail_adjust = None
    lua2, _, restored = make(game)
    assert restored.offense(0, 1, action(lua2), 1, 1) == (False, "pending_reconciliation")
    assert restored.expire(0, 1, 100) == (False, "pending_reconciliation")
    assert game.calls == before


def test_uncertain_commit_never_reapplies_on_restart():
    lua, game, driver = make()
    game.fail_set_at = 2  # intent succeeds, adjustment succeeds, commit fails
    assert driver.offense(0, 1, action(lua), 1, 1) == (False, "commit_uncertain")
    assert game.scores[(0, 1)] == -6
    lua2, _, restored = make(game)
    assert restored.offense(0, 1, action(lua2), 2, 2) == (False, "pending_reconciliation")
    assert game.calls == [(0, 1, -6)]


def test_failed_intent_readback_does_not_call_native_and_blocks_restart():
    lua, game, driver = make()
    game.fail_get_at = 2  # first read is old state; second reads back intent
    assert driver.offense(0, 1, action(lua), 1, 1) == (False, "storage_uncertain")
    assert game.calls == []
    lua2, _, restored = make(game)
    assert restored.offense(0, 1, action(lua2), 1, 1) == (False, "pending_reconciliation")
    assert game.calls == []


def test_failed_commit_readback_cannot_duplicate_an_applied_action():
    lua, game, driver = make()
    game.fail_get_at = 3  # old state, intent readback, then committed state
    assert driver.offense(0, 1, action(lua), 1, 1) == (False, "commit_uncertain")
    assert game.calls == [(0, 1, -6)]
    lua2, _, restored = make(game)
    assert restored.offense(0, 1, action(lua2), 1, 1) == (False, "stale_or_duplicate")
    assert game.calls == [(0, 1, -6)]


def test_invalid_records_and_failed_reads_are_fail_closed():
    lua, game, driver = make()
    game.fail_get = True
    assert driver.offense(0, 1, action(lua), 1, 1) == (False, "read_failed")
    game.fail_get = False
    game.properties[PREFIX + "0_1"] = "1:C:61:0:31:-1:1"
    assert driver.offense(0, 1, action(lua), 1, 1) == (False, "invalid_record")
    assert game.calls == []


def test_invalid_action_cannot_smuggle_another_pair():
    lua, game, driver = make()
    assert driver.offense(0, 2, action(lua, offender=1), 1, 1) == (False, "invalid_action")
    assert driver.offense(0, 1, action(lua, unit_religion=-1), 1, 1) == (False, "invalid_action")
    assert driver.offense(0, 1, action(lua, before=99), 1, 1) == (False, "ineligible")
    assert game.calls == [] and game.properties == {}


def test_concrete_game_binding_uses_alexanders_ai_and_checks_membership():
    lua = LuaRuntime(unpack_returned_tuples=True)
    core = lua.execute(CORE.read_text(encoding="utf-8-sig"))
    factory = lua.execute(DRIVER.read_text(encoding="utf-8-sig"))
    fixture = lua.execute("""
        local game = { props = {} }
        function game:GetProperty(key) return self.props[key] end
        function game:SetProperty(key, value) self.props[key] = value end
        local ai = {calls = {}}
        function ai:AdjustBaseDiplomacy(other, delta)
            table.insert(self.calls, {other, delta})
        end
        local dip = {met = true}
        function dip:HasMet(other) return self.met and other == 1 end
        local a = {alive = true, major = true, human = false}
        function a:IsAlive() return self.alive end
        function a:IsMajor() return self.major end
        function a:IsHuman() return self.human end
        function a:GetDiplomacy() return dip end
        function a:GetAi_Diplomacy() return ai end
        local b = {alive = true, major = true}
        function b:IsAlive() return self.alive end
        function b:IsMajor() return self.major end
        local config = {leader = "LEADER_REMSELY_ALEXANDER_II"}
        function config:GetLeaderTypeName() return self.leader end
        return {game=game, ai=ai, dip=dip, leader=a, other=b,
                players={[0]=a,[1]=b}, configs={[0]=config}, config=config}
    """)
    driver = factory.newGameDriver(core, fixture.game, fixture.players, fixture.configs,
                                   4, lua.eval("function() return true end"))
    assert driver.offense(0, 1, action(lua), 1, 1) == (True, "applied")
    assert fixture.ai.calls[1][1] == 1
    assert fixture.ai.calls[1][2] == -6
    fixture.dip.met = False
    assert driver.offense(0, 1, action(lua), 2, 2) == (False, "invalid_pair")
    fixture.dip.met = True
    fixture.leader.human = True
    assert driver.offense(0, 1, action(lua), 2, 2) == (False, "invalid_pair")
    fixture.leader.human = False
    fixture.other.alive = False
    assert driver.expire(0, 1, 32) == (False, "invalid_pair")
    assert len(fixture.ai.calls) == 1


def test_game_binding_without_confirmed_baseline_does_nothing():
    lua, game, driver = make()
    game.confirmed = False
    assert driver.offense(0, 1, action(lua), 1, 1) == (False, "unconfirmed_baseline")
    assert game.calls == [] and game.set_calls == 0

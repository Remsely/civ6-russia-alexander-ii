from pathlib import Path

from lupa import LuaRuntime


SOURCE = Path(__file__).parent / "experiments" / "religion_spread_target.lua"


def setup():
    lua = LuaRuntime(unpack_returned_tuples=True)
    core = lua.execute(SOURCE.read_text(encoding="utf-8-sig"))
    make = lua.eval("function(x,y,owner) return {GetX=function() return x end, GetY=function() return y end, GetOwner=function() return owner end} end")
    adjacent = {i: make(i + 1, 0, -1) for i in range(6)}
    cities = {}
    calls = []

    def get_adjacent(x, y, direction):
        calls.append(direction)
        return adjacent.get(direction)

    def get_city(x, y):
        return cities.get((x, y))

    return core, make, adjacent, cities, calls, get_adjacent, get_city


def test_own_city_precedes_neighbours():
    core, make, _, cities, calls, adjacent, city = setup()
    cities[(10, 10)] = make(10, 10, 1)
    cities[(1, 0)] = make(1, 0, 2)
    result = core.find(10, 10, 1, False, adjacent, city)
    assert result.GetOwner() == 1
    assert calls == []


def test_first_allowed_city_wins_in_game_direction_order():
    core, make, _, cities, calls, adjacent, city = setup()
    cities[(2, 0)] = make(2, 0, 2)
    cities[(3, 0)] = make(3, 0, 1)
    assert core.find(10, 10, 1, False, adjacent, city).GetOwner() == 2
    assert calls == [0, 1]
    calls.clear()
    assert core.find(10, 10, 1, True, adjacent, city).GetOwner() == 1
    assert calls == [0, 1, 2]


def test_foreign_city_under_unit_is_not_selected():
    core, make, _, cities, _, adjacent, city = setup()
    cities[(10, 10)] = make(10, 10, 2)
    cities[(1, 0)] = make(1, 0, 3)
    assert core.find(10, 10, 1, False, adjacent, city).GetOwner() == 3


def test_no_valid_city_and_missing_api_state_fail_closed():
    core, make, plots, cities, calls, adjacent, city = setup()
    plots[0] = None
    cities[(2, 0)] = make(2, 0, 2)
    assert core.find(10, 10, 1, True, adjacent, city) is None
    assert calls == list(range(6))
    calls.clear()
    assert core.find(10, 10, 1, None, adjacent, city) is None
    assert calls == []

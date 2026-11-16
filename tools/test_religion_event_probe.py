from pathlib import Path

from lupa import LuaRuntime


SOURCE = Path(__file__).parent / "experiments" / "religion_event_probe.lua"


def setup(present=True, no_foreign=False):
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute(
        """
        output = {}
        print = function(s) table.insert(output, s) end
        event = {Add = function(f) event.handler = f end}
        Events = {UnitOperationStarted = event}
        UnitOperationTypes = {SPREAD_RELIGION = 123}
        Game = {GetCurrentGameTurn = function() return 11 end}
        religion = {GetReligionType=function() return 3 end,
                    IsNoForeignSpread=function() return RESTRICT end,
                    GetSpreadCharges=function() return 1 end}
        unit = {GetReligion=function() return religion end,
                GetX=function() return 4 end, GetY=function() return 7 end}
        units = {FindID=function(_, id) if PRESENT then return unit end end}
        Players = {[2] = {GetUnits=function() return units end}}
        cityReligion = {GetMajorityReligion=function() return 5 end}
        city = {GetOwner=function() return 4 end, GetID=function() return 8 end,
                GetReligion=function() return cityReligion end}
        CityManager = {GetCityAt=function(x,y) if x == 5 and y == 7 then return city end end}
        Map = {GetAdjacentPlot=function(x,y,d)
            if d == 0 then return {GetX=function() return 5 end, GetY=function() return 7 end} end
        end}
        """
    )
    lua.globals().PRESENT = present
    lua.globals().RESTRICT = no_foreign
    lua.execute(SOURCE.read_text(encoding="utf-8"))
    return lua


def test_records_only_spreads_and_correct_target():
    lua = setup()
    handler = lua.globals().event.handler
    handler(2, 9, 124)
    assert len(lua.globals().output) == 1
    handler(2, 9, 123)
    output = lua.globals().output[2]
    assert "actor=2 unit=9 present=true" in output
    assert "target_owner=4 target_city=8 majority=5" in output


def test_missing_unit_is_reported_without_fabricated_target():
    lua = setup(present=False)
    lua.globals().event.handler(2, 9, 123)
    assert "present=false" in lua.globals().output[2]
    assert "target_owner=" not in lua.globals().output[2]


def test_does_not_select_forbidden_foreign_city():
    lua = setup(no_foreign=True)
    lua.globals().event.handler(2, 9, 123)
    assert "target=none" in lua.globals().output[2]


def test_output_is_bounded():
    lua = setup()
    for _ in range(20):
        lua.globals().event.handler(2, 9, 123)
    assert len(lua.globals().output) == 9

from pathlib import Path

from lupa import LuaRuntime


SOURCE = Path(__file__).parent / "experiments" / "religion_event_probe.lua"


def setup(present=True, no_foreign=False, charges=1, definition="present"):
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute(
        """
        output = {}
        print = function(s) table.insert(output, s) end
        event = {Add = function(f) event.handler = f end}
        Events = {UnitOperationStarted = event}
        -- Keep an incorrect enum and row index to prove neither is used as a
        -- fallback for the operation hash.
        UnitOperationTypes = {SPREAD_RELIGION = 999}
        GameInfo = {UnitOperations = {
          UNITOPERATION_SPREAD_RELIGION = {Hash=123, Index=456}
        }}
        Game = {GetCurrentGameTurn = function() return 11 end}
        religion = {GetReligionType=function() return 3 end,
                    IsNoForeignSpread=function() return RESTRICT end,
                    GetSpreadCharges=function() return CHARGES end}
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
    lua.globals().CHARGES = charges
    if definition == "missing_row":
        lua.execute("GameInfo.UnitOperations.UNITOPERATION_SPREAD_RELIGION = nil")
    elif definition == "missing_table":
        lua.execute("GameInfo = nil")
    elif definition == "missing_hash":
        lua.execute("GameInfo.UnitOperations.UNITOPERATION_SPREAD_RELIGION.Hash = nil")
    elif definition == "invalid_hash":
        lua.execute('GameInfo.UnitOperations.UNITOPERATION_SPREAD_RELIGION.Hash = "123"')
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


def test_last_charge_may_have_reached_zero_or_removed_the_unit():
    visible = setup(charges=0)
    visible.globals().event.handler(2, 9, 123)
    assert "present=true" in visible.globals().output[2]
    assert "charges=0" in visible.globals().output[2]
    removed = setup(present=False)
    removed.globals().event.handler(2, 9, 123)
    assert "present=false" in removed.globals().output[2]


def test_missing_or_invalid_definition_does_not_register_fallback():
    for definition in ("missing_row", "missing_table", "missing_hash", "invalid_hash"):
        lua = setup(definition=definition)
        assert lua.globals().event.handler is None
        assert "unavailable operation=nil" in lua.globals().output[1]


def test_hash_not_row_index_or_unrelated_enum_selects_spread_event():
    lua = setup()
    handler = lua.globals().event.handler
    handler(2, 9, 456)
    handler(2, 9, 999)
    assert len(lua.globals().output) == 1
    handler(2, 9, 123)
    assert "actor=2 unit=9" in lua.globals().output[2]


def test_does_not_select_forbidden_foreign_city():
    lua = setup(no_foreign=True)
    lua.globals().event.handler(2, 9, 123)
    assert "target=none" in lua.globals().output[2]


def test_output_is_bounded():
    lua = setup()
    for _ in range(20):
        lua.globals().event.handler(2, 9, 123)
    assert len(lua.globals().output) == 9

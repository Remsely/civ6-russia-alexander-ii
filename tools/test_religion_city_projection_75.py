"""Component cap experiment: no game integration is implied by these stubs."""
from pathlib import Path
import sqlite3
import xml.etree.ElementTree as ET
import zlib

from lupa import LuaRuntime


def runtime():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute('''
      records, plots, capitals, owners = {}, {}, {[2]=100,[3]=200}, {[100]=2,[200]=3}
      api = {maxPlayers=16,
        get=function(key) return records[key] end,
        set=function(key,val) records[key]=val end,
        capital=function(id) return capitals[id] end,
        owner=function(plot) return owners[plot] end,
        getBit=function(plot,key) return plots[plot] and plots[plot][key] end,
        setBit=function(plot,key,val)
          plots[plot]=plots[plot] or {}; plots[plot][key]=val
        end}
      function projected(leader,plot)
        local score=0
        for _,w in ipairs({1,2,4,8,16,32,64}) do
          score=score+(plots[plot] and plots[plot]['REMSELY_REL_COMPONENT75_'..leader..'_BIT_'..w] or 0)*w
        end
        return score
      end
    ''')
    module = lua.execute(Path('tools/experiments/religion_city_projection_75.lua').read_text(encoding='utf-8'))
    lua.globals().factory = module
    lua.globals().driver = module.new(lua.globals().api)
    return lua


def test_home_alone_reaches_and_never_exceeds_component_cap():
    lua = runtime()
    lua.execute('''
      assert(driver.offense(1,2,'home',10,1)); assert(projected(1,100)==12)
      for seq=2,22 do assert(driver.offense(1,2,'home',10,seq)) end
      assert(projected(1,100)==75)
      for seq=23,60 do assert(driver.offense(1,2,'home',10,seq)) end
      assert(projected(1,100)==75)
      assert(not driver.offense(1,2,'home',10,60)); assert(projected(1,100)==75)
      assert(driver.expire(1,2,40)); assert(projected(1,100)==0)
    ''')


def test_abroad_mixed_and_pair_isolation():
    lua = runtime()
    lua.execute('''
      assert(driver.offense(1,2,'home',10,1)); assert(driver.offense(1,2,'abroad',11,2))
      assert(projected(1,100)==18)
      for seq=3,45 do assert(driver.offense(1,2,'abroad',11,seq)) end
      assert(projected(1,100)==75)
      assert(driver.offense(1,3,'abroad',11,1)); assert(projected(1,200)==6)
      assert(driver.expire(1,2,40)); assert(projected(1,100)==75)
      assert(driver.expire(1,2,41)); assert(projected(1,100)==0 and projected(1,200)==6)
    ''')


def test_restoration_and_transfer_preserve_seven_bit_cap():
    lua = runtime()
    lua.execute('''
      for seq=1,30 do assert(driver.offense(1,2,'home',10,seq)) end
      local restored=factory.new(api)
      assert(restored.reconcile(1,2)); assert(projected(1,100)==75)
      capitals[2]=300; owners[300]=2
      assert(restored.reconcile(1,2)); assert(projected(1,100)==0 and projected(1,300)==75)
    ''')


def test_independent_sql_has_seven_bits_per_slot_and_no_automatic_attachment():
    root = Path(__file__).resolve().parents[1]
    db_path = root / 'reference/game-db/DebugGameplay.sqlite'
    source = sqlite3.connect(db_path.resolve().as_uri() + '?mode=ro', uri=True)
    db = sqlite3.connect(':memory:')
    source.backup(db)
    source.close()
    db.create_function('Make_Hash', 1, lambda value: zlib.crc32(str(value).encode()))
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript((root / 'tools/experiments/religion_city_projection_75.sql').read_text(encoding='utf-8'))
    weights = (1, 2, 4, 8, 16, 32, 64)
    for slot in range(64):
        for weight in weights:
            base = f'REMSELY_REL_COMPONENT75_{slot}'
            modifier = f'{base}_MOD_{weight}'
            requirement = f'{base}_REQ_{weight}'
            row = db.execute('SELECT ModifierType,SubjectRequirementSetId FROM Modifiers WHERE ModifierId=?', (modifier,)).fetchone()
            assert row == ('MODIFIER_REMSELY_REL_COMPONENT75_CAPITAL_DIPLOMACY', f'{base}_SET_{weight}')
            args = dict(db.execute('SELECT Name,Value FROM RequirementArguments WHERE RequirementId=?', (requirement,)))
            assert args == {'PropertyName': f'{base}_BIT_{weight}', 'PropertyMinimum': '1'}
            values = dict(db.execute('SELECT Name,Value FROM ModifierArguments WHERE ModifierId=?', (modifier,)))
            assert values == {'InitialValue': str(-weight), 'MaxValue': str(-weight), 'ReductionTurns': '0',
                              'SimpleModifierDescription': 'LOC_DIPLO_MODIFIER_REMSELY_REL_COMPONENT75'}
            # The engine asks for Sample before constructing a diplomacy reason.
            # This checks SQL data, not actual presentation or effect in game.
            sample = db.execute('SELECT Text FROM ModifierStrings WHERE ModifierId=? AND Context=?',
                                (modifier, 'Sample')).fetchall()
            assert sample == [('LOC_TOOLTIP_SAMPLE_DIPLOMACY_ALL',)]
    assert db.execute("SELECT COUNT(*) FROM Modifiers WHERE ModifierId LIKE 'REMSELY_REL_COMPONENT75_%'").fetchone()[0] == 448
    assert db.execute("SELECT COUNT(*) FROM TraitModifiers WHERE ModifierId LIKE 'REMSELY_REL_COMPONENT75_%'").fetchone()[0] == 0
    assert not list(db.execute('PRAGMA foreign_key_check'))
    assert all(sum(w for w in weights if (value // w) % 2) == value for value in range(76))
    rows = ET.parse(root / 'tools/experiments/religion_city_projection_75_text.xml').findall('./LocalizedText/Row')
    assert {row.attrib['Language'] for row in rows} == {'en_US', 'ru_RU'}
    assert all(row.attrib['Tag'] == 'LOC_DIPLO_MODIFIER_REMSELY_REL_COMPONENT75' and row.findtext('Text') for row in rows)
    db.close()

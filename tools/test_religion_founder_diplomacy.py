"""Detached diplomacy projection tests; no Civ runtime or engine proof."""
from pathlib import Path
import sqlite3
import xml.etree.ElementTree as ET
import zlib

from lupa import LuaRuntime


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / 'tools/experiments'
WEIGHTS = (2, 4, 8, 16)


def runtime():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute('''
      records,plots,owners,capitals,writes={},{},{},{},{}
      failBitAt,bitWrites,failAfterWrite=nil,0,false
      capitals[2]=100; owners[100]=2; capitals[3]=200; owners[200]=3
      api={maxPlayers=16,
        get=function(k) return records[k] end,
        set=function(k,v) records[k]=v;if failAfterWrite then failAfterWrite=false;error('lost reply') end end,
        getBit=function(p,k) return plots[p] and plots[p][k] end,
        setBit=function(p,k,v)
          bitWrites=bitWrites+1
          if bitWrites==failBitAt then failBitAt=nil;error('interrupted') end
          plots[p]=plots[p] or {};plots[p][k]=v;writes[#writes+1]={plot=p,key=k,value=v}
        end,
        capital=function(id) return capitals[id] end,owner=function(p) return owners[p] end}
      function score(leader,plot)
        local total=0
        for _,weight in ipairs({2,4,8,16}) do
          total=total+(plots[plot] and plots[plot]['REMSELY_REL_RIVALRY_'..leader..'_BIT_'..weight] or 0)*weight
        end
        return total
      end
    ''')
    lua.globals().factory = lua.execute((EXPERIMENTS / 'religion_founder_diplomacy.lua').read_text(encoding='utf-8'))
    lua.execute('driver=factory.new(api)')
    return lua


def test_score_repeats_expiry_and_separate_pairs():
    lua = runtime()
    lua.execute('''
      local ok,n=driver.record(1,2,5,1);assert(ok and n==6 and score(1,100)==6)
      ok,n=driver.record(1,2,6,2);assert(ok and n==8 and score(1,100)==8)
      ok,n=driver.record(1,2,6,2);assert(not ok and n=='duplicate' and score(1,100)==8)
      assert(driver.record(1,3,6,3) and score(1,200)==6)
      assert(driver.record(4,2,6,4) and score(4,100)==6 and score(1,100)==8)
      for seq=5,50 do assert(driver.record(1,2,7,seq)) end
      assert(score(1,100)==30)
      ok,n=driver.expire(1,2,36);assert(ok and n==30)
      ok,n=driver.expire(1,2,37);assert(ok and n==0 and score(1,100)==0)
      ok,n=driver.record(1,2,38,51);assert(ok and n==6)
    ''')


def test_recovery_after_partial_projection_or_record_response_loss():
    lua = runtime()
    lua.execute('''
      assert(driver.record(1,2,5,1));bitWrites=0;failBitAt=2
      assert(not driver.record(1,2,6,2));assert(driver.inspect(1,2).seq==2)
      local restored=factory.new(api);assert(restored.reconcile(1,2));assert(score(1,100)==8)
      local ok,why=restored.record(1,2,6,2);assert(not ok and why=='duplicate' and score(1,100)==8)
      failAfterWrite=true;assert(not restored.record(1,2,7,3))
      assert(restored.inspect(1,2).seq==3);restored=factory.new(api)
      assert(restored.reconcile(1,2) and score(1,100)==10)
    ''')


def test_capital_capture_does_not_erase_new_owners_projection():
    lua = runtime()
    lua.execute('''
      assert(driver.record(1,2,5,1));assert(driver.record(1,3,5,2))
      capitals[2]=300;owners[300]=2;capitals[3]=100;owners[100]=3
      assert(driver.reconcile(1,2) and score(1,100)==6 and score(1,300)==6)
      assert(driver.reconcile(1,3) and score(1,200)==0 and score(1,100)==6)
      capitals[2]=nil;assert(driver.reconcile(1,2) and score(1,300)==0)
    ''')


def test_bit_clear_precedes_set_on_score_change():
    lua = runtime()
    lua.execute('''
      assert(driver.record(1,2,5,1));writes={}
      assert(driver.record(1,2,6,2)) -- 6 to 8
      local added=false
      for _,w in ipairs(writes) do
        if w.value==1 then added=true else assert(not added) end
      end
    ''')


def test_sql_is_detached_and_defines_precise_weights():
    source = sqlite3.connect((ROOT / 'reference/game-db/DebugGameplay.sqlite').resolve().as_uri() + '?mode=ro', uri=True)
    db = sqlite3.connect(':memory:')
    source.backup(db)
    source.close()
    db.create_function('Make_Hash', 1, lambda value: zlib.crc32(str(value).encode()))
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript((EXPERIMENTS / 'religion_founder_diplomacy.sql').read_text(encoding='utf-8'))
    assert db.execute("SELECT COUNT(*) FROM Modifiers WHERE ModifierId LIKE 'REMSELY_REL_RIVALRY_%'").fetchone() == (256,)
    assert db.execute("SELECT COUNT(*) FROM TraitModifiers WHERE ModifierId LIKE 'REMSELY_REL_RIVALRY_%'").fetchone() == (0,)
    for slot in range(64):
        for weight in WEIGHTS:
            prefix = f'REMSELY_REL_RIVALRY_{slot}'
            name, req = f'{prefix}_MOD_{weight}', f'{prefix}_REQ_{weight}'
            args = dict(db.execute('SELECT Name,Value FROM ModifierArguments WHERE ModifierId=?', (name,)))
            assert args == {'InitialValue':str(-weight), 'MaxValue':str(-weight), 'ReductionTurns':'0',
                            'SimpleModifierDescription':'LOC_DIPLO_MODIFIER_REMSELY_REL_RIVALRY'}
            requirements = dict(db.execute('SELECT Name,Value FROM RequirementArguments WHERE RequirementId=?', (req,)))
            assert requirements == {'PropertyName':f'{prefix}_BIT_{weight}', 'PropertyMinimum':'1'}
            assert db.execute('SELECT Text FROM ModifierStrings WHERE ModifierId=? AND Context=?', (name,'Sample')).fetchone() == ('LOC_TOOLTIP_SAMPLE_DIPLOMACY_ALL',)
    assert not list(db.execute('PRAGMA foreign_key_check'))
    db.close()


def test_attachment_rescans_live_instances_and_refuses_duplicates():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.globals().attachModule = lua.execute((EXPERIMENTS / 'religion_founder_attach.lua').read_text(encoding='utf-8'))
    lua.execute('''
      live,nextID,attempts,failAfterAttach={},100,0,false
      api={
        validate=function(leader,weight,name) return leader==1 end,
        instances=function() local ids={} for id in pairs(live) do ids[#ids+1]=id end return ids end,
        describe=function(id,wanted) local row=live[id] if not row then error('missing') end return row.name,row.owner end,
        attach=function(owner,name)
          local id=nextID;nextID=id+1;attempts=attempts+1;live[id]={name=name,owner=owner}
          if failAfterAttach then failAfterAttach=false;error('lost reply') end
          return id
        end}
      failAfterAttach=true
      local ok,err=attachModule.ensure(api,1);assert(not ok and err=='attach_uncertain')
      ok=attachModule.ensure(api,1);assert(ok and attempts==4)
      ok=attachModule.ensure(api,1);assert(ok and attempts==4)
      live[999]={owner=1,name='REMSELY_REL_RIVALRY_1_MOD_2'}
      ok,err=attachModule.ensure(api,1);assert(not ok and err=='duplicate_instance')
      ok,err=attachModule.ensure(api,2);assert(not ok and err=='invalid_definition')
    ''')


def test_rivalry_localization_names_founder_rivalry_in_both_languages():
    rows = ET.parse(EXPERIMENTS / 'religion_founder_diplomacy_text.xml').findall('./LocalizedText/Row')
    assert {row.attrib['Language'] for row in rows} == {'en_US', 'ru_RU'}
    assert all(row.attrib['Tag'] == 'LOC_DIPLO_MODIFIER_REMSELY_REL_RIVALRY' and row.findtext('Text') for row in rows)

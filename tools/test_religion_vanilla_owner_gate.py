"""SQL shape tests on a private game DB; do not prove engine evaluation."""
from pathlib import Path
import sqlite3
import zlib

import pytest

ROOT = Path(__file__).resolve().parents[1]
SQL = (ROOT / 'tools/experiments/religion_vanilla_owner_gate.sql').read_text(encoding='utf-8')
DB = ROOT / 'reference/game-db/DebugGameplay.sqlite'
MOD = 'STANDARD_DIPLOMATIC_CONVERTED_CITY'
GATE = 'REMSELY_REL_GATE_OWNER'


@pytest.fixture
def db():
    source = sqlite3.connect(DB.resolve().as_uri() + '?mode=ro', uri=True)
    db = sqlite3.connect(':memory:')
    source.backup(db)
    source.close()
    db.create_function('Make_Hash', 1, lambda value: zlib.crc32(str(value).encode()))
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('UPDATE Modifiers SET OwnerRequirementSetId=NULL WHERE ModifierId=?', (MOD,))
    yield db
    db.close()


def reqset(db, name, child=None):
    db.execute('INSERT INTO RequirementSets(RequirementSetId,RequirementSetType) VALUES (?,?)', (name, 'REQUIREMENTSET_TEST_ALL'))
    if child is not None:
        rid = name + '_nested'
        db.execute('INSERT INTO Requirements(RequirementId,RequirementType) VALUES (?,?)', (rid,'REQUIREMENT_REQUIREMENTSET_IS_MET'))
        db.execute('INSERT INTO RequirementArguments(RequirementId,Name,Value) VALUES (?,?,?)', (rid,'RequirementSetId',child))
        db.execute('INSERT INTO RequirementSetRequirements(RequirementSetId,RequirementId) VALUES (?,?)', (name,rid))


def run(db):
    db.commit()
    try:
        db.executescript(SQL)
    except Exception:
        db.rollback()
        raise


def test_null_owner_uses_inverse_leader_condition_and_keeps_existing_data(db):
    before = db.execute('SELECT ModifierType, SubjectRequirementSetId FROM Modifiers WHERE ModifierId=?',(MOD,)).fetchone()
    before_args = db.execute('SELECT * FROM ModifierArguments WHERE ModifierId=? ORDER BY Name',(MOD,)).fetchall()
    run(db)
    assert db.execute('SELECT ModifierType, SubjectRequirementSetId,OwnerRequirementSetId FROM Modifiers WHERE ModifierId=?',(MOD,)).fetchone() == (*before,GATE)
    assert db.execute('SELECT * FROM ModifierArguments WHERE ModifierId=? ORDER BY Name',(MOD,)).fetchall() == before_args
    assert db.execute('SELECT RequirementId FROM RequirementSetRequirements WHERE RequirementSetId=?',(GATE,)).fetchall() == [('REMSELY_REL_GATE_NOT_LEADER',)]
    assert db.execute("SELECT RequirementType,Inverse FROM Requirements WHERE RequirementId='REMSELY_REL_GATE_NOT_LEADER'").fetchone() == ('REQUIREMENT_PLAYER_LEADER_TYPE_MATCHES',1)
    assert db.execute("SELECT Value FROM RequirementArguments WHERE RequirementId='REMSELY_REL_GATE_NOT_LEADER' AND Name='LeaderType'").fetchone() == ('LEADER_REMSELY_ALEXANDER_II',)
    assert not list(db.execute('PRAGMA foreign_key_check'))


def test_existing_nested_owner_requirement_is_preserved_without_copying_or_editing(db):
    reqset(db, 'ZTEST_INNER')
    reqset(db, 'ZTEST_OUTER', 'ZTEST_INNER')
    db.execute('UPDATE Modifiers SET OwnerRequirementSetId=? WHERE ModifierId=?', ('ZTEST_OUTER',MOD))
    run(db)
    assert set(db.execute('SELECT RequirementId FROM RequirementSetRequirements WHERE RequirementSetId=?',(GATE,)).fetchall()) == {('REMSELY_REL_GATE_NOT_LEADER',),('REMSELY_REL_GATE_PREVIOUS',)}
    assert db.execute("SELECT Value FROM RequirementArguments WHERE RequirementId='REMSELY_REL_GATE_PREVIOUS' AND Name='RequirementSetId'").fetchone() == ('ZTEST_OUTER',)
    assert db.execute("SELECT Value FROM RequirementArguments WHERE RequirementId='ZTEST_OUTER_nested' AND Name='RequirementSetId'").fetchone() == ('ZTEST_INNER',)


def test_existing_cyclic_set_aborts_without_mutating_modifier(db):
    reqset(db, 'ZTEST_ONE')
    reqset(db, 'ZTEST_TWO', 'ZTEST_ONE')
    db.execute('INSERT INTO Requirements(RequirementId,RequirementType) VALUES (?,?)', ('ZTEST_LOOP','REQUIREMENT_REQUIREMENTSET_IS_MET'))
    db.execute('INSERT INTO RequirementArguments(RequirementId,Name,Value) VALUES (?,?,?)', ('ZTEST_LOOP','RequirementSetId','ZTEST_TWO'))
    db.execute('INSERT INTO RequirementSetRequirements(RequirementSetId,RequirementId) VALUES (?,?)', ('ZTEST_ONE','ZTEST_LOOP'))
    db.execute('UPDATE Modifiers SET OwnerRequirementSetId=? WHERE ModifierId=?', ('ZTEST_ONE',MOD))
    with pytest.raises(sqlite3.IntegrityError): run(db)
    assert db.execute('SELECT OwnerRequirementSetId FROM Modifiers WHERE ModifierId=?',(MOD,)).fetchone() == ('ZTEST_ONE',)
    assert db.execute('SELECT 1 FROM RequirementSets WHERE RequirementSetId=?',(GATE,)).fetchone() is None


def test_dangling_nested_requirement_fails_closed(db):
    reqset(db, 'ZTEST_OUTER', 'ZTEST_MISSING')
    db.execute('UPDATE Modifiers SET OwnerRequirementSetId=? WHERE ModifierId=?', ('ZTEST_OUTER',MOD))
    with pytest.raises(sqlite3.IntegrityError): run(db)
    assert db.execute('SELECT OwnerRequirementSetId FROM Modifiers WHERE ModifierId=?',(MOD,)).fetchone() == ('ZTEST_OUTER',)


def test_later_mod_can_override_this_global_field(db):
    reqset(db, 'ZTEST_LATER')
    run(db)
    db.execute('UPDATE Modifiers SET OwnerRequirementSetId=? WHERE ModifierId=?', ('ZTEST_LATER',MOD))
    assert db.execute('SELECT OwnerRequirementSetId FROM Modifiers WHERE ModifierId=?',(MOD,)).fetchone() == ('ZTEST_LATER',)


def test_missing_target_aborts(db):
    db.execute('PRAGMA foreign_keys=OFF')
    db.execute('DELETE FROM Modifiers WHERE ModifierId=?', (MOD,))
    with pytest.raises(sqlite3.IntegrityError): run(db)
    assert db.execute('SELECT 1 FROM RequirementSets WHERE RequirementSetId=?',(GATE,)).fetchone() is None


def test_reserved_name_collision_aborts_without_overwriting(db):
    reqset(db, GATE)
    with pytest.raises(sqlite3.IntegrityError): run(db)
    assert db.execute('SELECT OwnerRequirementSetId FROM Modifiers WHERE ModifierId=?',(MOD,)).fetchone() == (None,)


def test_missing_owner_set_does_not_become_null(db):
    db.commit()
    db.execute('PRAGMA foreign_keys=OFF')
    db.execute('UPDATE Modifiers SET OwnerRequirementSetId=? WHERE ModifierId=?', ('ZTEST_MISSING',MOD))
    with pytest.raises(sqlite3.IntegrityError): run(db)
    assert db.execute('SELECT OwnerRequirementSetId FROM Modifiers WHERE ModifierId=?',(MOD,)).fetchone() == ('ZTEST_MISSING',)

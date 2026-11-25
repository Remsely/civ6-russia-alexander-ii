"""Validate detached prototype definitions against a private copy of Civ DB.

These tests do not attach a modifier or prove its behaviour in the game.
"""
from pathlib import Path
import sqlite3
import xml.etree.ElementTree as ET
import zlib

import pytest


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / 'reference/game-db/DebugGameplay.sqlite'
SQL = ROOT / 'tools/experiments/religion_city_projection.sql'
TEXT = ROOT / 'tools/experiments/religion_city_projection_text.xml'
WEIGHTS = (1, 2, 4, 8, 16, 32)


@pytest.fixture(scope='module')
def database():
    assert DB.is_file(), 'gameplay reference DB is required for schema validation'
    source = sqlite3.connect(DB.resolve().as_uri() + '?mode=ro', uri=True)
    db = sqlite3.connect(':memory:')
    source.backup(db)
    source.close()
    db.create_function('Make_Hash', 1, lambda value: zlib.crc32(str(value).encode()))
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript(SQL.read_text(encoding='utf-8'))
    yield db
    db.close()


def test_each_slot_has_only_six_weighted_modifiers_with_matching_property(database):
    for slot in range(64):
        for weight in WEIGHTS:
            base = f'REMSELY_REL_PROTOTYPE_{slot}'
            mod, req, reqset = (f'{base}_MOD_{weight}', f'{base}_REQ_{weight}', f'{base}_SET_{weight}')
            row = database.execute('SELECT ModifierType, SubjectRequirementSetId FROM Modifiers WHERE ModifierId=?', (mod,)).fetchone()
            assert row == ('MODIFIER_REMSELY_REL_PROTOTYPE_CAPITAL_DIPLOMACY', reqset)
            assert database.execute('SELECT RequirementId FROM RequirementSetRequirements WHERE RequirementSetId=?', (reqset,)).fetchall() == [(req,)]
            args = dict(database.execute('SELECT Name,Value FROM RequirementArguments WHERE RequirementId=?', (req,)))
            assert args == {'PropertyName': f'{base}_BIT_{weight}', 'PropertyMinimum': '1'}
            values = dict(database.execute('SELECT Name,Value FROM ModifierArguments WHERE ModifierId=?', (mod,)))
            assert values == {'InitialValue': str(-weight), 'MaxValue': str(-weight), 'ReductionTurns': '0',
                              'SimpleModifierDescription': 'LOC_DIPLO_MODIFIER_REMSELY_REL_PROTOTYPE'}
    assert database.execute("SELECT COUNT(*) FROM Modifiers WHERE ModifierId LIKE 'REMSELY_REL_PROTOTYPE_%'").fetchone()[0] == 384


def test_collection_and_effect_are_declared_without_any_attached_trait(database):
    assert database.execute("SELECT CollectionType,EffectType FROM DynamicModifiers WHERE ModifierType='MODIFIER_REMSELY_REL_PROTOTYPE_CAPITAL_DIPLOMACY'").fetchone() == ('COLLECTION_ALL_CAPITAL_CITIES', 'EFFECT_DIPLOMACY_SIMPLE_EFFECT')
    assert database.execute("SELECT Tag FROM TypeTags WHERE Type='MODIFIER_REMSELY_REL_PROTOTYPE_CAPITAL_DIPLOMACY'").fetchone() == ('DIPLOMACY_MODIFIER',)
    assert database.execute("SELECT COUNT(*) FROM TraitModifiers WHERE ModifierId LIKE 'REMSELY_REL_PROTOTYPE_%'").fetchone()[0] == 0
    assert not list(database.execute('PRAGMA foreign_key_check'))


def test_integer_bit_projections_represent_each_permitted_score():
    for value in range(55):
        assert sum(weight for weight in WEIGHTS if (value // weight) % 2) == value


def test_experimental_text_has_two_nonempty_localizations():
    rows = ET.parse(TEXT).findall('./LocalizedText/Row')
    assert {row.attrib['Language'] for row in rows} == {'en_US', 'ru_RU'}
    assert all(row.attrib['Tag'] == 'LOC_DIPLO_MODIFIER_REMSELY_REL_PROTOTYPE' and row.findtext('Text') for row in rows)


def test_sql_does_not_depend_on_existing_builtin_type_rows():
    source = sqlite3.connect(DB.resolve().as_uri() + '?mode=ro', uri=True)
    db = sqlite3.connect(':memory:')
    source.backup(db)
    source.close()
    db.create_function('Make_Hash', 1, lambda value: zlib.crc32(str(value).encode()))
    db.execute('PRAGMA foreign_keys=ON')
    for name in ('COLLECTION_ALL_CAPITAL_CITIES', 'REQUIREMENT_PLOT_PROPERTY_MATCHES', 'EFFECT_DIPLOMACY_SIMPLE_EFFECT'):
        db.execute('DELETE FROM Types WHERE Type=?', (name,))
    db.executescript(SQL.read_text(encoding='utf-8'))
    assert db.execute("SELECT Kind FROM Types WHERE Type='COLLECTION_ALL_CAPITAL_CITIES'").fetchone() == ('KIND_COLLECTION',)
    assert db.execute("SELECT Kind FROM Types WHERE Type='REQUIREMENT_PLOT_PROPERTY_MATCHES'").fetchone() == ('KIND_REQUIREMENT',)
    assert db.execute("SELECT Kind FROM Types WHERE Type='EFFECT_DIPLOMACY_SIMPLE_EFFECT'").fetchone() == ('KIND_EFFECT',)
    assert not list(db.execute('PRAGMA foreign_key_check'))
    db.close()


@pytest.mark.parametrize('name', ['COLLECTION_ALL_CAPITAL_CITIES', 'REQUIREMENT_PLOT_PROPERTY_MATCHES', 'EFFECT_DIPLOMACY_SIMPLE_EFFECT'])
def test_builtin_type_with_wrong_kind_fails_instead_of_silent_ignore(name):
    source = sqlite3.connect(DB.resolve().as_uri() + '?mode=ro', uri=True)
    db = sqlite3.connect(':memory:')
    source.backup(db)
    source.close()
    db.create_function('Make_Hash', 1, lambda value: zlib.crc32(str(value).encode()))
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('UPDATE Types SET Kind=? WHERE Type=?', ('KIND_MODIFIER', name))
    with pytest.raises(sqlite3.IntegrityError, match='CHECK constraint failed'):
        db.executescript(SQL.read_text(encoding='utf-8'))
    assert db.execute("SELECT COUNT(*) FROM Types WHERE Type='MODIFIER_REMSELY_REL_PROTOTYPE_CAPITAL_DIPLOMACY'").fetchone()[0] == 0
    db.close()

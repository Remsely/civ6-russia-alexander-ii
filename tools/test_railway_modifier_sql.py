"""Check that binary railway bonuses retain the old numerical behavior."""
from pathlib import Path
import sqlite3
import zlib


def test_binary_modifiers_on_game_database():
    root = Path(__file__).resolve().parents[1]
    db = sqlite3.connect(':memory:')
    with sqlite3.connect(root / 'reference/game-db/DebugGameplay.sqlite') as src:
        src.backup(db)
    db.create_function('Make_Hash', 1, lambda value: zlib.crc32(str(value).encode()))
    db.execute('PRAGMA foreign_keys = ON')
    db.executescript((root / 'mod/Data/GameDefines.sql').read_text(encoding='utf-8'))
    assert not db.execute('PRAGMA foreign_key_check').fetchall()
    trait = 'TRAIT_LEADER_REMSELY_ALEXANDER_II_REFORMS'
    for category, yield_type in [('OWN', 'YIELD_PRODUCTION'), ('FOREIGN', 'YIELD_GOLD')]:
        rows = db.execute('''SELECT m.ModifierId, m.SubjectRequirementSetId,
            (SELECT Value FROM ModifierArguments a WHERE a.ModifierId=m.ModifierId AND a.Name='YieldType'),
            (SELECT Value FROM ModifierArguments a WHERE a.ModifierId=m.ModifierId AND a.Name='Amount')
            FROM TraitModifiers t JOIN Modifiers m ON m.ModifierId=t.ModifierId
            WHERE t.TraitType=? AND m.ModifierId LIKE ?''', (trait, f'REMSELY_REFORMS_RAIL_{category}_BIT_%')).fetchall()
        assert len(rows) == 8
        weights = []
        for _, reqset, kind, amount in rows:
            weight = int(amount)
            weights.append(weight)
            assert kind == yield_type
            req = db.execute('SELECT RequirementId FROM RequirementSetRequirements WHERE RequirementSetId=?', (reqset,)).fetchone()[0]
            args = dict(db.execute('SELECT Name, Value FROM RequirementArguments WHERE RequirementId=?', (req,)))
            assert args['PropertyName'] == f'REMSELY_RAIL_{category}_BIT_{weight}'
            assert args['PropertyMinimum'] == '1'
        assert sorted(weights) == [1, 2, 4, 8, 16, 32, 64, 128]
        for count in range(201):
            assert sum(w for w in weights if count & w) == count
    legacy = "(ModifierId GLOB 'REMSELY_REFORMS_RAIL_OWN_[0-9]*' OR ModifierId GLOB 'REMSELY_REFORMS_RAIL_GOLD_[0-9]*')"
    assert db.execute('SELECT count(*) FROM Modifiers WHERE ' + legacy).fetchone()[0] == 400
    assert db.execute('SELECT count(*) FROM TraitModifiers WHERE TraitType=? AND ' + legacy, (trait,)).fetchone()[0] == 0

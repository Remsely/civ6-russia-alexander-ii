"""Static checks for the mod. Run from anywhere: python tools/validate.py

Checks:
  1. .modinfo: every action file is listed in <Files> and exists on disk.
  2. SQL: each script runs against an in-memory copy of the game's debug databases
     (tables, columns, constraints), so invented names fail here, not in the game.
  3. Text: en_US/ru_RU have the same tags, tags carry the REMSELY prefix, ru name tags
     have six case forms, placeholders match, no letter "yo".
  4. Every LOC_ tag used in SQL exists in the mod text or in the game's localization.
Exit code 1 on any error.
"""
import re
import sqlite3
import sys
import zlib
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parent.parent
DB_DIR = ROOT / "reference" / "game-db"
MOD = ROOT / "mod"  # the mod itself (ModBuddy project); reference/ stays outside its pantry
MODINFO = MOD / "RemselysAlexanderII.modinfo"

# Which database each modinfo action type is applied to (front end uses the config DB).
CONFIG_ACTIONS = {"FrontEndActions": "DebugConfiguration.sqlite"}
GAMEPLAY_DB = "DebugGameplay.sqlite"

NAME_TAG = re.compile(r"^LOC_(LEADER|UNIT|BUILDING|DISTRICT|IMPROVEMENT|CIVILIZATION)_.+_NAME$")
PLACEHOLDER = re.compile(r"\[[A-Z_0-9]+\]|\{[^}]*\}|%\d")
LOC_REF = re.compile(r"'(LOC_[A-Z0-9_]+)'")

errors: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)


def load_modinfo():
    tree = etree.parse(str(MODINFO))
    files = {f.text.strip() for f in tree.findall("./Files/File")}
    actions = []  # (section, action type, file)
    for section in ("FrontEndActions", "InGameActions"):
        for action in tree.findall(f"./{section}/*"):
            for f in action.findall("File"):
                actions.append((section, action.tag, f.text.strip()))
    return files, actions


def check_files(files, actions):
    for rel in sorted(files):
        if not (MOD / rel).is_file():
            err(f"modinfo: file listed but missing on disk: {rel}")
    for section, tag, rel in actions:
        if rel not in files:
            err(f"modinfo: {section}/{tag} uses {rel}, which is not in <Files>")


COLORS_DIR = ROOT / "reference" / "vanilla" / "Base" / "UI" / "Colors"


def build_colors_db(mem) -> None:
    """In-memory copy of the game's color tables, filled from the vanilla XML (Colors.xml, PlayerStandardColors.xml, PlayerColors.xml).
    Columns come from the XML itself, so a column the game does not have (e.g. TextColor) fails here as it does in Database.log."""
    for name, table in (("PlayerStandardColors.xml", "Colors"), ("Colors.xml", "Colors"), ("PlayerColors.xml", "PlayerColors")):
        path = COLORS_DIR / name
        if not path.is_file():
            continue
        for tbl in etree.parse(str(path)).getroot():
            rows = [{c.tag: (c.text or "") for c in row} for row in tbl.findall("Row")]
            if not rows or tbl.tag != table:
                continue
            columns = sorted({k for r in rows for k in r}, key=lambda k: (k != "Type", k))
            mem.execute(f"CREATE TABLE IF NOT EXISTS {tbl.tag} ({', '.join(columns)})")
            existing = {r[1] for r in mem.execute(f"PRAGMA table_info({tbl.tag})")}
            for col in columns:
                if col not in existing:
                    mem.execute(f"ALTER TABLE {tbl.tag} ADD COLUMN {col}")
            for r in rows:
                mem.execute(f"INSERT INTO {tbl.tag} ({', '.join(r)}) VALUES ({', '.join('?' * len(r))})", list(r.values()))


def check_sql(actions):
    for section, tag, rel in actions:
        if tag != "UpdateDatabase" and tag != "UpdateColors":
            continue
        # Colors live in the gameplay DB in both sections; config data in the config DB.
        db_name = CONFIG_ACTIONS.get(section) if tag == "UpdateDatabase" else GAMEPLAY_DB
        db_name = db_name or GAMEPLAY_DB
        src = DB_DIR / db_name
        if not src.is_file():
            err(f"sql: reference database missing: {src} (see CLAUDE.md, reference/game-db)")
            continue
        mem = sqlite3.connect(":memory:")
        if tag == "UpdateColors":
            build_colors_db(mem)  # the real colors DB (ColorManager) is not in the dumps, and its schema differs
        else:
            with sqlite3.connect(src) as disk:
                disk.backup(mem)
        # The game's triggers call its own hash function; any stable value is fine for validation.
        mem.create_function("Make_Hash", 1, lambda s: zlib.crc32(str(s).encode()))
        mem.execute("PRAGMA foreign_keys = ON")
        try:
            mem.executescript((MOD / rel).read_text(encoding="utf-8"))
        except sqlite3.Error as e:
            err(f"sql: {rel} ({section}/{tag}) failed against {db_name}: {e}")
            continue
        for row in mem.execute("PRAGMA foreign_key_check"):
            err(f"sql: {rel} breaks a foreign key: {row}")
        mem.close()


def read_text_file(path: Path):
    """Return {tag: (text, has_gender_and_plurality)}"""
    tree = etree.parse(str(path))
    out = {}
    for el in tree.iter("Replace", "Row"):
        tag = el.get("Tag")
        text_el = el.find("Text")
        text = text_el.text if text_el is not None and text_el.text else ""
        has_meta = el.find("Gender") is not None and el.find("Plurality") is not None
        if tag in out:
            err(f"text: duplicate tag {tag} in {path.name}")
        out[tag] = (text, has_meta)
    return out


def check_text(files):
    text_files = sorted(f for f in files if f.startswith("Text/") and f.endswith(".xml"))
    by_lang = {}
    for rel in text_files:
        lang = Path(rel).stem
        by_lang[lang] = read_text_file(MOD / rel)
    en, ru = by_lang.get("en_US", {}), by_lang.get("ru_RU", {})
    for tag in sorted(en.keys() - ru.keys()):
        err(f"text: {tag} has no ru_RU translation")
    for tag in sorted(ru.keys() - en.keys()):
        err(f"text: {tag} has no en_US text")
    for lang, tags in by_lang.items():
        for tag, (text, has_meta) in tags.items():
            if "REMSELY" not in tag:
                err(f"text: {tag} ({lang}) lacks the REMSELY prefix")
            if "ё" in text.lower():
                err(f"text: {tag} ({lang}) uses the letter 'yo' (the official text does not)")
    for tag, (text, has_meta) in ru.items():
        if NAME_TAG.match(tag):
            if text.count("|") != 5:
                err(f"text: {tag} needs six case forms separated by '|'")
            if not has_meta:
                err(f"text: {tag} needs <Gender> and <Plurality>")
        if tag in en and sorted(PLACEHOLDER.findall(text)) != sorted(PLACEHOLDER.findall(en[tag][0])):
            err(f"text: {tag} placeholders differ between en_US and ru_RU")
    check_required_leader_text(set(en) | set(ru))
    return set(en) | set(ru)


# Texts a vanilla leader has (checked against the Peter the Great set in DebugLocalization.sqlite): the loading screen looks up
# LOC_LOADING_INFO_<LeaderType> by itself, the Civilopedia leader page is built from the PEDIA keys below.
LEADER = "REMSELY_ALEXANDER_II"
REQUIRED_LEADER_TAGS = [
    f"LOC_LEADER_{LEADER}_NAME",
    f"LOC_LOADING_INFO_LEADER_{LEADER}",
    f"LOC_PEDIA_LEADERS_PAGE_LEADER_{LEADER}_TITLE",
    f"LOC_PEDIA_LEADERS_PAGE_LEADER_{LEADER}_SUBTITLE",
    f"LOC_PEDIA_LEADERS_PAGE_LEADER_{LEADER}_CHAPTER_CAPSULE_BODY",
    f"LOC_PEDIA_LEADERS_PAGE_LEADER_{LEADER}_CHAPTER_DETAILED_BODY",
    f"LOC_PEDIA_LEADERS_PAGE_LEADER_{LEADER}_CHAPTER_HISTORY_PARA_1",
]


def check_required_leader_text(tags):
    for tag in REQUIRED_LEADER_TAGS:
        if tag not in tags:
            err(f"text: required leader text {tag} is missing")


def check_loc_refs(actions, mod_tags):
    loc_db = DB_DIR / "DebugLocalization.sqlite"
    if not loc_db.is_file():
        err(f"loc: {loc_db} missing, cannot verify LOC_ references")
        return
    known = sqlite3.connect(loc_db)
    for rel in sorted({r for _, t, r in actions if t == "UpdateDatabase"}):
        for ref in sorted(set(LOC_REF.findall((MOD / rel).read_text(encoding="utf-8")))):
            if ref in mod_tags:
                continue
            if known.execute("SELECT 1 FROM LocalizedText WHERE Tag=? LIMIT 1", (ref,)).fetchone():
                continue
            err(f"loc: {rel} references {ref}, defined neither in the mod nor in the game")


COLOR_ATLAS = ROOT / "reference" / "vanilla" / "Base" / "UI" / "Civ6_ColorAtlas.xml"
COLOR_TAG = re.compile(r"\[COLOR_([A-Za-z0-9_]+)\]")


def check_text_colors(files):
    """[COLOR_X] in text resolves only against Civ6_ColorAtlas.xml (COLOR_FLOAT_GOLD, COLOR_LIGHTBLUE, ...). Names from the player
    palette (COLOR_STANDARD_ORANGE_MD) are not text colors: the game renders such text invisible."""
    if not COLOR_ATLAS.is_file():
        return
    known = {e.get("Name") for e in etree.parse(str(COLOR_ATLAS)).iter("Color", "ColorSet")}
    sources = [MODINFO, *(MOD / f for f in files if f.endswith(".xml"))]
    for path in sources:
        for name in sorted(set(COLOR_TAG.findall(path.read_text(encoding="utf-8")))):
            if f"COLOR_{name}" not in known:
                err(f"text color: [COLOR_{name}] in {path.name} is not in Civ6_ColorAtlas.xml (invisible in game)")


def main() -> int:
    files, actions = load_modinfo()
    check_text_colors(files)
    check_files(files, actions)
    check_sql(actions)
    mod_tags = check_text(files)
    check_loc_refs(actions, mod_tags)
    for e in errors:
        print("ERROR", e)
    print(f"{len(errors)} error(s)" if errors else "OK")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

"""Read-only census of installed vanilla diplomacy templates and review candidates.

This is a source audit, not evidence that a particular line is reachable or audible.
Run from the repository root with the Python standard library:
    python tools/experiments/audit_voice_coverage.py
"""
import collections
import json
from pathlib import Path
import re
import sqlite3
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "reference/vanilla/Base"
DLC = ROOT / "reference/samples/DLC"
PLAN = ROOT / "art/voice/candidates/remaining-bulk-v1/plan.json"


def relative(path):
    return path.relative_to(ROOT).as_posix()


def main():
    candidates = json.loads(PLAN.read_text(encoding="utf-8-sig"))["items"]
    candidate_keys = {x.get("original_key", x["key"]) for x in candidates}
    # The first seven candidates were created in two earlier batches and use
    # short internal keys, not the localization tags that the UI resolves.
    candidate_keys.update({
        "LOC_DIPLO_KUDO_LEADER_ANY_REASON_AGENDA_MODIFIER_WONDER_ADVOCATE_LAG",
        "LOC_DIPLO_WARNING_LEADER_ANY_REASON_AGENDA_SYMPATHIZER_GOLDEN_AGE",
        "LOC_DIPLO_WARNING_STOP_CONVERTING_MY_CITIES_LEADER_ANY_ANY",
        "LOC_DIPLO_WARNING_LEADER_ANY_REASON_AGENDA_GREAT_WHITE_FLEET",
        "LOC_DIPLO_MAKE_DEAL_AI_ACCEPT_DEAL_ANY_ANY",
        "LOC_DIPLO_MAKE_DEAL_AI_REFUSE_DEAL_ANY_ANY",
        "LOC_DIPLO_MAKE_DEAL_AI_ADJUST_DEAL_ANY_ANY",
    })
    ui_plan = ROOT / "art/voice/candidates/remaining-deal-ui-v1/plan.json"
    if ui_plan.exists():
        candidate_keys.update(
            x.get("original_key", x["key"])
            for x in json.loads(ui_plan.read_text(encoding="utf-8-sig"))["items"]
        )
    custom_keys = {
        x.get("Tag") for x in ET.parse(ROOT / "mod/Text/ru_RU.xml").iter()
        if x.get("Tag", "").startswith("LOC_DIPLO_")
    }
    reason_pattern = re.compile(r"LOC_DIPLO_(?:KUDO|WARNING)_LEADER_ANY_REASON_[A-Z0-9_]+")
    files, rows, dlc_reasons = [], [], collections.defaultdict(set)
    scanned = 0
    for root in (BASE, DLC):
        if not root.is_dir():
            raise FileNotFoundError(root)
        for path in root.rglob("*.xml"):
            scanned += 1
            try:
                contents = path.read_text(encoding="utf-8-sig")
            except UnicodeError:
                continue
            if root == DLC:
                for key in set(reason_pattern.findall(contents)):
                    dlc_reasons[key].add(relative(path))
            if "<DiplomacyStatements" not in contents:
                continue
            tree = ET.fromstring(contents)
            tables = list(tree.iter("DiplomacyStatements"))
            if tables:
                files.append(relative(path))
            for table in tables:
                for entry in table:
                    if entry.tag not in ("Row", "Replace"):
                        continue
                    fields = {k: entry.get(k) or entry.findtext(k) for k in (
                        "Type", "SubType", "Initiator", "Leader", "Mood",
                        "StatementText", "ReasonText",
                    )}
                    rows.append((relative(path), fields))
    # Read localized strings without relying on the DB snapshot that omitted
    # some Expansion1 rows. Do not assume any DLC is active in a saved game.
    ui_tags = collections.defaultdict(set)
    lua_scanned = 0
    for root in (BASE / "UI", DLC):
        for path in root.rglob("*.lua"):
            lua_scanned += 1
            try:
                contents = path.read_text(encoding="utf-8-sig")
            except UnicodeError:
                continue
            for key in re.findall(r'SetLeaderDialog\(\s*["\'](LOC_[A-Z0-9_]+)["\']', contents):
                ui_tags[key].add(relative(path))
    interesting = set(dlc_reasons) | candidate_keys | set(ui_tags)
    interesting.update({
        (r["StatementText"] or "").replace("$(LEADER)", "ANY").replace("$(MOOD)", "ANY")
        for _, r in rows
    })
    localizations = collections.defaultdict(list)
    russian_diplo_keys = set()
    localization_files = set()
    for root in (BASE, DLC):
        for path in root.rglob("*.xml"):
            try:
                contents = path.read_text(encoding="utf-8-sig")
            except UnicodeError:
                continue
            if "ru_RU" not in contents or "LOC_DIPLO" not in contents:
                continue
            try:
                tree = ET.fromstring(contents)
            except ET.ParseError:
                continue
            for entry in tree.iter():
                key = entry.get("Tag")
                if entry.get("Language") == "ru_RU" and key and key.startswith("LOC_DIPLO"):
                    russian_diplo_keys.add(key)
                    localization_files.add(relative(path))
                if key in interesting and entry.get("Language") == "ru_RU":
                    localizations[key].append((relative(path), entry.findtext("Text")))
    templates = collections.defaultdict(list)
    for path, row in rows:
        if row["Leader"] not in ("ANY", None) or not row["StatementText"]:
            continue
        templates[row["StatementText"]].append((path, row))
    pending = []
    for template, refs in sorted(templates.items()):
        own = template.replace("$(LEADER)", "LEADER_REMSELY_ALEXANDER_II").replace("$(MOOD)", "ANY")
        variants = {
            template.replace("$(LEADER)", "ANY").replace("$(MOOD)", "ANY"),
            template.replace("$(LEADER)", "LEADER_ANY").replace("$(MOOD)", "ANY"),
        }
        if own in custom_keys or variants & candidate_keys:
            continue
        pending.append((template, variants, refs))
    print(f"XML scanned: {scanned}; statement files: {len(files)}; source rows: {len(rows)}")
    print(f"Russian LOC_DIPLO* tags: {len(russian_diplo_keys)} in {len(localization_files)} XML files; "
          f"{sum('CHOICE' in k for k in russian_diplo_keys)} contain CHOICE; "
          f"{sum(k.endswith('_ANY_ANY') for k in russian_diplo_keys)} end in ANY_ANY.")
    print(f"Distinct generic statement templates: {len(templates)}; missing candidate/custom matches: {len(pending)}")
    print("Counts include duplicates across versions; presence is not runtime reachability.")
    for template, variants, refs in pending:
        print("\n", template, sep="")
        print("  contexts:", sorted({(r["Type"], r["SubType"], r["Initiator"], r["Mood"]) for _, r in refs}))
        for key in sorted(variants):
            for source, text in localizations.get(key, []):
                print("  ru:", key, repr(text), source)
    print(f"\nLua scanned: {lua_scanned}; direct SetLeaderDialog localization keys: {len(ui_tags)}")
    for key, paths in sorted(ui_tags.items()):
        print("\n", key, "candidate:", key in candidate_keys)
        print("  sources:", ", ".join(sorted(paths)))
        for source, text in localizations.get(key, []):
            print("  ru:", repr(text), source)
    print("  Dynamic SetLeaderDialog(szText) is fed by the resolved statement route and can be overridden by deal status.")
    print("\nDLC reason keys not in candidate plans:")
    for key, paths in sorted(dlc_reasons.items()):
        if key in candidate_keys:
            continue
        print("\n", key, sep="")
        print("  sources:", ", ".join(sorted(paths)))
        for source, text in localizations.get(key, []):
            print("  ru:", repr(text), source)
    print("\nSource files containing DiplomacyStatements:")
    for path in files:
        print(" ", path)
    db = ROOT / "reference/game-db/DebugGameplay.sqlite"
    if db.is_file():
        with sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True) as con:
            print("\nSnapshot DiplomacyStatements rows:", con.execute("SELECT count(*) FROM DiplomacyStatements").fetchone()[0])
    print("\nNot checked: dynamically installed third-party mods, game modes not present in these roots,"
          " native runtime FindTextKey resolution, active ruleset, event reachability and audible playback.")


if __name__ == "__main__":
    main()

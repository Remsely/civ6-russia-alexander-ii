"""Prepare an independent -75-component projection research variant.

This script reads the existing research prototypes and writes separate files;
it never modifies the mod or the original prototypes. It is kept for auditability
of the small mechanical changes, not for use as part of the build.
"""
from pathlib import Path


def build(source: str, replacements: list[tuple[str, str]]) -> str:
    for old, new in replacements:
        if old not in source:
            raise ValueError(f"Original prototype no longer contains {old!r}")
        source = source.replace(old, new)
    return source


def main() -> None:
    root = Path(__file__).parent
    lua = (root / "religion_city_projection.lua").read_text(encoding="utf-8")
    lua = build(lua, [
        ("-- EXPERIMENT: not imported by the mod.", "-- EXPERIMENT: independent -75 component variant; not imported by the mod."),
        ("six plot properties", "seven plot properties"),
        ("2147483647, 54, 30", "2147483647, 75, 30"),
        ("REMSELY_REL_PROTOTYPE_", "REMSELY_REL_COMPONENT75_"),
        ("{1, 2, 4, 8, 16, 32}", "{1, 2, 4, 8, 16, 32, 64}"),
        ("integer(s.home,0,60)", "integer(s.home,0,75)"),
        ("integer(s.abroad,0,30)", "integer(s.abroad,0,75)"),
        ("math.min(60,was+", "math.min(CAP,was+"),
        ("math.min(30,was+", "math.min(CAP,was+"),
    ])
    (root / "religion_city_projection_75.lua").write_text(lua, encoding="utf-8")

    sql = (root / "religion_city_projection.sql").read_text(encoding="utf-8")
    sql = build(sql, [
        ("-- EXPERIMENT ONLY.", "-- EXPERIMENT ONLY, independent -75 component variant."),
        ("six N-specific", "seven N-specific"),
        ("REMSELY_ReligionProjection", "REMSELY_ReligionComponent75Projection"),
        ("REMSELY_REL_PROTOTYPE_", "REMSELY_REL_COMPONENT75_"),
        ("LOC_DIPLO_MODIFIER_REMSELY_REL_PROTOTYPE", "LOC_DIPLO_MODIFIER_REMSELY_REL_COMPONENT75"),
        ("(1),(2),(4),(8),(16),(32)", "(1),(2),(4),(8),(16),(32),(64)"),
        ("DROP TABLE REMSELY_ReligionComponent75ProjectionRows;",
         "-- Vanilla diplomacy reasons define a Sample template for each modifier.\n"
         "-- Its presence is not proof that the resulting reason is visible in game.\n"
         "INSERT INTO ModifierStrings (ModifierId,Context,Text)\n"
         "SELECT ModifierId,'Sample','LOC_TOOLTIP_SAMPLE_DIPLOMACY_ALL'\n"
         "FROM REMSELY_ReligionComponent75ProjectionRows;\n\n"
         "DROP TABLE REMSELY_ReligionComponent75ProjectionRows;"),
    ])
    (root / "religion_city_projection_75.sql").write_text(sql, encoding="utf-8")

    text = (root / "religion_city_projection_text.xml").read_text(encoding="utf-8")
    text = build(text, [("LOC_DIPLO_MODIFIER_REMSELY_REL_PROTOTYPE", "LOC_DIPLO_MODIFIER_REMSELY_REL_COMPONENT75")])
    (root / "religion_city_projection_75_text.xml").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()

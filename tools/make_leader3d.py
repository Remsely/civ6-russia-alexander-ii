"""Wire the 3D leader asset (mod/Assets/AlexanderII.ast) into the mod, or switch back to the 2D fallback.

python tools/make_leader3d.py         # 3D: XLP + Leaders.artdef + .dep + .modinfo
python tools/make_leader3d.py --off   # 2D: empty Leader_BLP_Entry (the game shows the fallback image)

Run after tools/make_art.py (it regenerates Leaders.artdef and the .dep), then tools/make_modbuddy.py.
Modelled on vanilla Peter (SDK Assets: XLPs/Leader_Peter.xlp, ArtDefs/Leaders.artdef): one Leader-class XLP with one entry,
referenced from Leader_BLP_Entry; light rig is Peter's (vanilla package leaders/light_rigs).
The cooked BLP (Platforms/*/BLPs/leaders/...) appears only after a ModBuddy build; it is added to <Files> once it exists.
"""
import sys
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parent.parent
MOD = ROOT / "mod"
ASSET = "AlexanderII"
ENTRY = "ART_LEADER_REMSELY_ALEXANDER_II"
PACKAGE = "leaders/leader_remsely_alexander_ii"
XLP_FILE = "Leader_AlexanderII.xlp"
LIGHT_RIG = ("Peter_LightRig", "LeaderLighting", "Leader_LightRigs.xlp", "leaders/light_rigs")
BLPS = [f"Platforms/{p}/BLPs/{PACKAGE}.blp" for p in ("Windows", "MacOS")]

XLP = f"""<?xml version="1.0" encoding="UTF-8" ?>
<AssetObjects..XLP>
	<m_Version>
		<major>3</major>
		<minor>0</minor>
		<build>163</build>
		<revision>723</revision>
	</m_Version>
	<m_ClassName text="Leader"/>
	<m_PackageName text="{PACKAGE}"/>
	<m_Entries>
		<Element>
			<m_EntryID text="{ENTRY}"/>
			<m_ObjectName text="{ASSET}"/>
		</Element>
	</m_Entries>
	<m_AllowedPlatforms>
		<Element>WINDOWS</Element>
		<Element>LINUX</Element>
		<Element>MACOS</Element>
	</m_AllowedPlatforms>
</AssetObjects..XLP>
"""


def set_entry(values, param, entry, xlp_class, xlp_path, package, library):
    el = next(e for e in values if e.find("m_ParamName") is not None and e.find("m_ParamName").get("text") == param)
    for tag, val in (("m_EntryName", entry), ("m_XLPClass", xlp_class), ("m_XLPPath", xlp_path),
                     ("m_BLPPackage", package), ("m_LibraryName", library)):
        el.find(tag).set("text", val)


def patch_artdef(on: bool):
    path = MOD / "ArtDefs" / "Leaders.artdef"
    tree = etree.parse(str(path))
    values = tree.find(".//m_Fields/m_Values")
    if on:
        set_entry(values, "Leader_BLP_Entry", ENTRY, "Leader", XLP_FILE, PACKAGE, "Leader")
        name, cls, xlp, pkg = LIGHT_RIG
        set_entry(values, "Leader_Lightrig_BLP_Entry", name, cls, xlp, pkg, "LeaderLighting")
    else:
        set_entry(values, "Leader_BLP_Entry", "", "", "", "", "Leader")
        set_entry(values, "Leader_Lightrig_BLP_Entry", "", "", "Leader_LightRigs.xlp", "", "LeaderLighting")
    write(path, tree)


def patch_dep(on: bool):
    path = MOD / "RemselysAlexanderII.dep"
    tree = etree.parse(str(path))
    lib = next(e for e in tree.iter("Element") if e.find("LibraryName") is not None
               and e.find("LibraryName").get("text") == "Leader")
    deps = lib.find("PackageDependencies")
    for el in list(deps):
        deps.remove(el)
    deps.text = None
    if on:
        deps.text = "\n\t\t\t\t"
        etree.SubElement(deps, "Element", text=f"{PACKAGE}.blp").tail = "\n\t\t\t"
    write(path, tree)


def patch_modinfo(on: bool):
    path = MOD / "RemselysAlexanderII.modinfo"
    tree = etree.parse(str(path))
    files = tree.find("Files")
    wanted = [f"XLPs/{XLP_FILE}"] + [b for b in BLPS if (MOD / b).is_file()]
    for f in list(files):
        if f.text.strip() == f"XLPs/{XLP_FILE}" or f.text.strip() in BLPS:
            files.remove(f)
    if on:
        for rel in wanted:
            etree.SubElement(files, "File").text = rel
    etree.indent(tree, space="  ")
    write(path, tree, decl='<?xml version="1.0" encoding="utf-8"?>')
    return wanted if on else []


def write(path, tree, decl='<?xml version="1.0" encoding="UTF-8" ?>'):
    body = etree.tostring(tree.getroot(), encoding="unicode")
    path.write_text(decl + "\n" + body + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    on = "--off" not in sys.argv
    xlp = MOD / "XLPs" / XLP_FILE
    if on:
        if not (MOD / "Assets" / f"{ASSET}.ast").is_file():
            print(f"missing mod/Assets/{ASSET}.ast")
            return 1
        xlp.write_text(XLP, encoding="utf-8", newline="\n")
    elif xlp.exists():
        xlp.unlink()
    patch_artdef(on)
    patch_dep(on)
    files = patch_modinfo(on)
    print("3D leader", "on" if on else "off", *files)
    if on and len(files) == 1:
        print("BLPs not built yet: build in ModBuddy, copy Platforms/*/BLPs/leaders/ into mod/, re-run this script")
    return 0


if __name__ == "__main__":
    sys.exit(main())

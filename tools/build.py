"""Build the mod without ModBuddy: cook every mod/XLPs/*.xlp into mod/Platforms/{Windows,MacOS}/BLPs, then install.

python tools/build.py              # cook + tools/install.py (validate, copy to Mods)
python tools/build.py --no-install # cook only

Same cooker and arguments as ModBuddy's Civ6.targets (CookAssets): --pantry is the mod plus the SDK Assets pantries of
the art the mod requires (RequiredGameArtIDs in the .dep). The ArtDef cook is skipped on purpose: it only rewrites the
.dep from the .Art.xml, and the mod ships its own .dep (see make_modbuddy.py).
"""
import subprocess
import sys
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parent.parent
MOD = ROOT / "mod"
SDK = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization VI SDK")
ASSETS = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization VI SDK Assets")
COOKER_DIR = SDK / "AssetModTools" / "Cooker"
COOKER = COOKER_DIR / "Civ6AssetCooker_FinalRelease.exe"
# art id name -> pantries it brings (dependencies included), as in GeneratePantryPaths
PANTRIES = {
    "Civ6": ["Civ6/pantry"],
    "Shared": ["Civ6/DLC/Shared/pantry", "Civ6/pantry"],
    "Expansion1": ["Civ6/DLC/Expansion1/pantry", "Civ6/DLC/Shared/pantry", "Civ6/pantry"],
    "Expansion2": ["Civ6/DLC/Expansion2/pantry", "Civ6/DLC/Expansion1/pantry", "Civ6/DLC/Shared/pantry", "Civ6/pantry"],
}
PLATFORMS = ("Windows", "MacOS")


def pantries() -> list[str]:
    dep = etree.parse(str(MOD / "RemselysAlexanderII.dep")).getroot()
    out = []
    for e in dep.find("RequiredGameArtIDs"):
        for p in PANTRIES[e.find("name").get("text")]:
            path = str(ASSETS / p)
            if path not in out:
                out.append(path)
    return out


def cook() -> bool:
    ok = True
    extra = pantries()
    for xlp in sorted((MOD / "XLPs").glob("*.xlp")):
        for platform in PLATFORMS:
            stewpot = MOD / "Platforms" / platform / "BLPs"
            stewpot.mkdir(parents=True, exist_ok=True)
            cmd = [str(COOKER), "--absolute_paths", "--no_mt", "--mode", "XLP", "--platform", platform,
                   "--pantry", str(MOD), *extra, "--stewpot", str(stewpot), "--config", str(COOKER_DIR / "Civ6.cfg"),
                   str(xlp)]
            r = subprocess.run(cmd, cwd=COOKER_DIR, capture_output=True, text=True, errors="replace")
            log = r.stdout + r.stderr
            success = "cook completed with success" in log
            ok &= success
            print(f"{'ok  ' if success else 'FAIL'} {platform:7} {xlp.name}")
            if not success:
                print(log[-3000:])
    return ok


def main() -> int:
    if not COOKER.is_file():
        print(f"cooker not found: {COOKER}")
        return 1
    if not cook():
        return 1
    if "--no-install" in sys.argv:
        return 0
    return subprocess.call([sys.executable, str(ROOT / "tools" / "install.py")])


if __name__ == "__main__":
    sys.exit(main())

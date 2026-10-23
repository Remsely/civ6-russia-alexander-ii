"""Copy the mod (only files listed in the .modinfo) into the game's Mods folder.

python tools/install.py            # validate, then install
python tools/install.py --remove   # delete the installed copy

Override the target with CIV6_MODS_DIR. The game reads the mod list at startup, so restart it afterwards.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parent.parent
MOD = ROOT / "mod"  # the mod itself (ModBuddy project); reference/ stays outside its pantry
MODINFO = MOD / "RemselysAlexanderII.modinfo"
MODS_DIR = Path(os.environ.get("CIV6_MODS_DIR") or Path.home() / "Documents" / "My Games" / "Sid Meier's Civilization VI" / "Mods")
TARGET = MODS_DIR / "RemselysAlexanderII"


def main() -> int:
    if "--remove" in sys.argv:
        shutil.rmtree(TARGET, ignore_errors=True)
        print(f"removed {TARGET}")
        return 0
    if subprocess.call([sys.executable, str(ROOT / "tools" / "validate.py")]) != 0:
        return 1
    files = [f.text.strip() for f in etree.parse(str(MODINFO)).findall("./Files/File")]
    shutil.rmtree(TARGET, ignore_errors=True)
    for rel in [MODINFO.name, *files]:
        dst = TARGET / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(MOD / rel, dst)
    print(f"installed {len(files) + 1} files to {TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

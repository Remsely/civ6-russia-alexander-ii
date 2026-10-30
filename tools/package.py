"""Build the release archive for GitHub Releases.

python tools/package.py

Runs validate.py, then packs the .modinfo and every file from <Files> into
dist/release/RemselysAlexanderII-v<version>.zip (folder RemselysAlexanderII/ inside, ready to unpack into Mods)
and writes a .sha256 next to it. The release version (e.g. 1.0.0-alpha) is the VERSION file; the .modinfo `version` stays
an integer because the game requires it.
"""
import hashlib
import subprocess
import sys
import zipfile
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parent.parent
MOD = ROOT / "mod"  # the mod itself (ModBuddy project); reference/ stays outside its pantry
MODINFO = MOD / "RemselysAlexanderII.modinfo"
FOLDER = "RemselysAlexanderII"
OUT = ROOT / "dist" / "release"


def main() -> int:
    if subprocess.call([sys.executable, str(ROOT / "tools" / "validate.py")]) != 0:
        return 1
    tree = etree.parse(str(MODINFO))
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    files = [f.text.strip() for f in tree.findall("./Files/File")]
    OUT.mkdir(parents=True, exist_ok=True)
    archive = OUT / f"{FOLDER}-v{version}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel in [MODINFO.name, *files]:
            z.write(MOD / rel, f"{FOLDER}/{rel}")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (OUT / f"{archive.name}.sha256").write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    print(f"{archive} ({archive.stat().st_size // 1024} KB, {len(files) + 1} files)\nSHA-256: {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

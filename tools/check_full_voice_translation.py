"""Check that translated voice lines still correspond to their source texts."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VOICE = ROOT / "art" / "voice"


def read(name):
    return json.loads((VOICE / name).read_text(encoding="utf-8"))


def main():
    inventory = read("full-game-inventory.json")
    translations = read("full-game-english.json")
    source = read("full-game-english-source.json")
    expected = {str(row["number"]) for row in inventory}
    if len(expected) != len(inventory) or expected != set(translations) or expected != set(source):
        raise ValueError("Inventory, translation and fingerprint numbers differ or are duplicated")
    for row in inventory:
        number = str(row["number"])
        entry = source[number]
        digest = hashlib.sha256(row["text_ru"].encode("utf-8")).hexdigest()
        if entry != {"key": row["key"], "text_ru_sha256": digest}:
            raise ValueError(f"Russian source or key changed for voice line {number}")
        if not isinstance(translations[number], str) or not translations[number].strip():
            raise ValueError(f"English translation missing for voice line {number}")
    print(f"OK: {len(inventory)} translations match recorded source keys and text hashes")


if __name__ == "__main__":
    main()

"""Read-only inspection of diplomacy code in the locally installed GS DLL.

This prints machine instructions, not game data or an assertion that the game
behaves correctly at runtime. The mapped addresses apply only to the exact
SHA-256 below. A different game build needs an independent analysis.

Dependencies: ``python -m pip install capstone pefile``.
Example: ``python tools/experiments/audit_religion_diplomacy.py --dll PATH``.
Optional ``--offsets PATH`` supplies the function-name TSV published by
cru121/civ6-gamecore-reference at commit 05e08b4848526f6c47c9996d2649e1fb3edfaf19.
Neither the game library nor that table is redistributed by this script.
"""

from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

import capstone
import pefile


EXPECTED_SHA256 = "092abfbb2176f8df04b5212f819dc269dd83aea866ff05aaf489904a1ff7c41f"
FUNCTIONS = {
    "AI::Diplomatic::Diplomatic (constructor / archived fields)": (0x4271A0, 5485),
    "Lua::IAiDiplomacy::lAdjustBaseDiplomacy": (0x6C5690, 93),
    "AI::Diplomatic::AdjustBaseDiplomacy": (0x42B0C0, 101),
    "AI::Diplomatic::AdjustDiplomaticScore": (0x42B130, 172),
    "Lua::IAiDiplomacy::lGetDiplomaticModifiers": (0x6C56F0, 585),
    "AI::Diplomatic::GetDiplomaticModifiers": (0x430500, 1521),
    "Effects::DiplomacyBaseEffect::Initialize": (0x80BAB0, 2624),
    "Effects::DiplomacyBaseEffect::Apply": (0x9446C0, 463),
    "Player::DiplomacyBlackboard::Activate": (0x2BE1A0, 507),
    "Player::DiplomaticModifierTracker::Initialize": (0x2BF4C0, 242),
    "Player::DiplomaticModifierTracker::Update": (0x2BFC60, 166),
}
VTABLE_RVA = 0x9FC9B8
EXPECTED_VTABLE = {0x20: 0x42B130, 0x28: 0x42B0C0, 0x38: 0x430500}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dll", required=True, type=Path)
    parser.add_argument("--offsets", type=Path)
    args = parser.parse_args()
    digest = hashlib.sha256(args.dll.read_bytes()).hexdigest()
    print(f"File: {args.dll.resolve()}\nSHA-256: {digest}")
    if digest != EXPECTED_SHA256:
        raise SystemExit("Different game build: independently verify addresses before analysis.")

    symbols: dict[int, list[str]] = {}
    if args.offsets:
        for line in args.offsets.read_text(encoding="utf-8-sig").splitlines():
            row = line.split("\t")
            if len(row) >= 5 and row[1].startswith("0x") and "," not in row[1]:
                symbols.setdefault(int(row[1], 16), []).append(row[4])

    pe = pefile.PE(str(args.dll))
    for slot, expected in EXPECTED_VTABLE.items():
        pointer = struct.unpack("<Q", pe.get_data(VTABLE_RVA + slot, 8))[0]
        rva = pointer - pe.OPTIONAL_HEADER.ImageBase
        if rva != expected:
            raise SystemExit(f"Unexpected vtable slot {slot:#x}: {rva:#x} != {expected:#x}")
        print(f"AI::Diplomatic vtable +{slot:#x}: {rva:#x}")

    disassembler = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    disassembler.detail = True
    for name, (rva, size) in FUNCTIONS.items():
        print(f"\n{name} RVA={rva:#x}; {size} bytes")
        for ins in disassembler.disasm(pe.get_data(rva, size), rva):
            annotations: list[str] = []
            if ins.mnemonic in ("call", "jmp") and ins.op_str.startswith("0x"):
                annotations.extend(symbols.get(int(ins.op_str, 16), [])[:3])
            for operand in ins.operands:
                if operand.type == capstone.x86.X86_OP_MEM and operand.mem.base == capstone.x86.X86_REG_RIP:
                    target = ins.address + ins.size + operand.mem.disp
                    try:
                        raw = pe.get_data(target, 100).split(b"\0", 1)[0]
                        if 3 < len(raw) < 95 and all(32 <= c < 127 for c in raw):
                            annotations.append(repr(raw.decode("ascii")))
                    except (pefile.PEFormatError, ValueError):
                        pass
            suffix = " ; " + "; ".join(annotations) if annotations else ""
            print(f"{ins.address:08x}: {ins.mnemonic:8s} {ins.op_str}{suffix}")


if __name__ == "__main__":
    main()

"""Audit score propagation in the installed XP2 GameCore DLL (read-only).

Dependencies: python -m pip install capstone pefile
Usage: python tools/experiments/audit_diplomatic_score.py --dll PATH

The addresses and instruction assertions are specific to one SHA-256 only;
the script refuses other builds. Function names and RVAs were cross-checked
against cru121/civ6-gamecore-reference, commit 05e08b4848526f6c47c9996d2649e1fb3edfaf19.
Neither the game binary nor its contents are included in this repository.
This inspection does not measure in-game timing, explain UI or prove war.
"""

from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

import capstone
import pefile


EXPECTED_SHA256 = "092abfbb2176f8df04b5212f819dc269dd83aea866ff05aaf489904a1ff7c41f"
VTABLE_RVA = 0x9FC9B8
VTABLE_SLOTS = {
    0x20: ("AdjustDiplomaticScore", 0x42B130),
    0x28: ("AdjustBaseDiplomacy", 0x42B0C0),
    0x38: ("GetDiplomaticModifiers", 0x430500),
    0x50: ("GetDiplomaticScore", 0x430B40),
}
FUNCTIONS = {
    "AdjustBaseDiplomacy": (0x42B0C0, 101),
    "AdjustDiplomaticScore": (0x42B130, 172),
    "GetDiplomaticScore": (0x430B40, 17),
    "DiplomaticState::UpdateScore": (0x44D350, 98),
    "DiplomaticState::UpdateState": (0x44D3C0, 639),
    "Diplomatic::DoOffTurn call": (0x42DB90, 23),
    "Diplomatic::DoTurnActivate call": (0x42DFA5, 26),
}


def instructions(disassembler: capstone.Cs, pe: pefile.PE, rva: int, size: int):
    return list(disassembler.disasm(pe.get_data(rva, size), rva))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dll", required=True, type=Path)
    args = parser.parse_args()
    digest = hashlib.sha256(args.dll.read_bytes()).hexdigest()
    print(f"File: {args.dll.resolve()}\nSHA-256: {digest}")
    if digest != EXPECTED_SHA256:
        raise SystemExit("Unknown binary: audit addresses are not validated for this build")
    pe = pefile.PE(str(args.dll), fast_load=True)
    image_base = pe.OPTIONAL_HEADER.ImageBase
    for slot, (name, expected_rva) in VTABLE_SLOTS.items():
        actual_rva = struct.unpack("<Q", pe.get_data(VTABLE_RVA + slot, 8))[0] - image_base
        if actual_rva != expected_rva:
            raise SystemExit(f"Unexpected vtable slot {slot:#x}: {actual_rva:#x}")
        print(f"AI::Diplomatic vtable +{slot:#x}: {name} RVA={actual_rva:#x}")

    disassembler = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    all_instructions = {}
    for name, (rva, size) in FUNCTIONS.items():
        code = instructions(disassembler, pe, rva, size)
        all_instructions[name] = code
        print(f"\n{name} RVA={rva:#x}")
        for ins in code:
            print(f"{ins.address:08x}: {ins.mnemonic:8s} {ins.op_str}")

    def has_call(name: str, argument: str) -> bool:
        return any(i.mnemonic == "call" and i.op_str == argument for i in all_instructions[name])

    assert has_call("AdjustBaseDiplomacy", "qword ptr [rax + 0x20]")
    assert has_call("DiplomaticState::UpdateScore", "qword ptr [rax + 0x50]")
    assert has_call("Diplomatic::DoOffTurn call", "0x44d350")
    assert has_call("Diplomatic::DoTurnActivate call", "0x44d3c0")
    print("\nChecked: base adjustment -> score method; AI score -> transition update.")


if __name__ == "__main__":
    main()

"""Audit a candidate city-property diplomacy route in the local GS game DLL.

Read-only, build-specific reverse engineering, not an integration test.  Pass
the local GameCore_XP2_FinalRelease.dll as --dll and optionally an independently
obtained symbol TSV as --offsets. Game binaries are never copied into the repo.
Requires pefile and capstone. This checks object interfaces, native effect
ownership, removal semantics, and city/property collection instructions; it
does not prove runtime context availability or UI rendering.
"""
from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

import capstone
import pefile
from capstone.x86 import X86_OP_MEM, X86_REG_RIP

SHA256 = "092abfbb2176f8df04b5212f819dc269dd83aea866ff05aaf489904a1ff7c41f"
SECTIONS = {
    "City constructor: Player and Plot interface vtables": (0x929C00, 130),
    "City QueryInterface: Player and Plot GUID branches": (0x9723D0, 310),
    "City GetPlayer: owner ID lookup": (0x94DEA0, 58),
    "City GetPlot: city-centre plot lookup": (0x954550, 109),
    "Diplomacy Initialize: effect-owner Player interface": (0x80BAB0, 160),
    "Diplomacy Apply: subject Player interface": (0x80E2A0, 170),
    "Diplomacy Apply: owner blackboard and subject player ID": (0x9446C0, 463),
    "Diplomacy Remove: deactivate the subject tracker": (0x813630, 71),
    "Diplomacy Deactivate: immediate zero when ReductionTurns <= 0": (0x2BE410, 149),
    "PlotPropertyMatches Test: subject Plot interface": (0x8F5060, 194),
    "PlotPropertyMatches property-change handler": (0x96B410, 155),
    "AllCities collection: enumerate all city owners and cities": (0x8DF6F0, 391),
    "AllCapitalCities collection: filter capital flag then create City": (0x83FE70, 404),
    "SetAsCapital: publish internal capital-flag signal": (0x1356E0, 134),
    "AllCapitalCities-compatible listener: subscribe to flag signal": (0x840CC0, 336),
    "DynamicModifier metadata: pass effect the instance ID": (0x951B10, 180),
    "Diplomatic metadata: look up subject by player and instance ID": (0x8128D0, 289),
    "Blackboard activation: index tracker by subject and instance ID": (0x2BE1A0, 100),
    "Blackboard lookup: filter trackers by instance ID": (0x2BF1F0, 124),
}
CITY_VTABLES = {
    "City.Player": (0xAB5038, (0x94DEA0, 0x94DEA0, 0x9544F0)),
    "City.Plot": (0xAB5050, (0x954550, 0x954770, 0x954940)),
}
PLAYER_GUID = bytes.fromhex("494cca3b22f4ae448a10857b3ecefd3a")
PLOT_GUID = bytes.fromhex("8ba853b61d12af4389172eada2d39f84")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dll", type=Path, required=True)
    parser.add_argument("--offsets", type=Path)
    args = parser.parse_args()
    if hashlib.sha256(args.dll.read_bytes()).hexdigest() != SHA256:
        raise SystemExit("Different DLL build: independently re-check all offsets.")
    pe = pefile.PE(str(args.dll))
    if pe.get_data(0xA9A4F8, 16) != PLAYER_GUID or pe.get_data(0xA9A508, 16) != PLOT_GUID:
        raise SystemExit("Unexpected interface GUID values.")
    print(f"SHA-256: {SHA256}")
    for label, (rva, expected) in CITY_VTABLES.items():
        values = struct.unpack("<" + "Q" * len(expected), pe.get_data(rva, 8 * len(expected)))
        got = tuple(x - pe.OPTIONAL_HEADER.ImageBase for x in values)
        if got != expected:
            raise SystemExit(f"Unexpected vtable {label}: {got!r}")
        print(label, ", ".join(f"{x:#x}" for x in got))

    names: dict[int, str] = {}
    if args.offsets:
        for line in args.offsets.read_text(encoding="utf-8-sig").splitlines():
            fields = line.split("\t")
            if len(fields) >= 5 and fields[1].startswith("0x") and "," not in fields[1]:
                names[int(fields[1], 16)] = fields[4]
    cs = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    cs.detail = True
    for title, (start, size) in SECTIONS.items():
        print(f"\n{title} RVA={start:#x}")
        for ins in cs.disasm(pe.get_data(start, size), start):
            notes = []
            if ins.mnemonic in ("call", "jmp") and ins.op_str.startswith("0x"):
                notes.append(names.get(int(ins.op_str, 16), ""))
            for operand in ins.operands:
                if operand.type == X86_OP_MEM and operand.mem.base == X86_REG_RIP:
                    target = ins.address + ins.size + operand.mem.disp
                    if target == 0xA9A4F8:
                        notes.append("Player interface GUID")
                    elif target == 0xA9A508:
                        notes.append("Plot interface GUID")
            print(f"{ins.address:08x}: {ins.mnemonic:8s} {ins.op_str} {'; '.join(n for n in notes if n)}")


if __name__ == "__main__":
    main()

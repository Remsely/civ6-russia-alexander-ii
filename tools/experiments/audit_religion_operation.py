"""Inspect the installed Gathering Storm library without loading or modifying it.

Dependencies: ``python -m pip install capstone pefile``.
Usage: ``python tools/experiments/audit_religion_operation.py --dll PATH [--offsets PATH]``.
The optional offsets are the CC-BY-4.0 name/address table from cru121's
civ6-gamecore-reference, commit 05e08b4848526f6c47c9996d2649e1fb3edfaf19,
``data/old_to_new_offsets.tsv``. No game executable or bytes are distributed.
The RVAs below were checked only for the SHA-256 below: another binary must be
analysed independently. Disassembly does not establish Lua event delivery timing.

For this DLL, the XP2 handler's vtable +0xc0 selects the inspected target helper.
It checks the unit's own city first, then six directions in array order and
returns the first eligible city. Start queues UNIT_OPERATION_STARTED at
0x74d139, before religious pressure at 0x74d262, charge change at 0x74d522,
and delayed destruction at 0x74d590. This is native send order: Lua receipt,
visibility, target reconstruction, and behaviour in other builds remain untested.
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
    "Lua::IMap::GetAdjacentPlot": (0x17390, 188),
    "Map::IInstance::GetAdjacentPlot": (0x15CE0, 123),
    "SpreadReligion::GetEligibleTargetCity": (0x673560, 389),
    "XP2::SpreadReligion::Register": (0x74CFB0, 126),
    "XP2::SpreadReligion::Start": (0x74D030, 1428),
    "Reporting::Event::Send (operation event overload)": (0x5FB890, 313),
    "Cache::Dispatcher::Send": (0x7C670, 379),
}
VTABLE = 0xA44490


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dll", required=True, type=Path)
    parser.add_argument("--offsets", type=Path, help="Optional published TSV of native names and RVAs")
    args = parser.parse_args()
    digest = hashlib.sha256(args.dll.read_bytes()).hexdigest()
    print(f"File: {args.dll.resolve()}\nSHA-256: {digest}")
    if digest != EXPECTED_SHA256:
        raise SystemExit("Different binary: RVAs below are not validated for this build; aborting.")

    symbols: dict[int, list[str]] = {}
    if args.offsets:
        for line in args.offsets.read_text(encoding="utf-8-sig").splitlines():
            row = line.split("\t")
            if len(row) >= 5 and row[1].startswith("0x") and "," not in row[1]:
                symbols.setdefault(int(row[1], 16), []).append(row[4])

    pe = pefile.PE(str(args.dll))
    for name, rva in (("direction x", 0xB61670), ("direction y", 0xB61688)):
        print(f"{name}: {struct.unpack('<6i', pe.get_data(rva, 24))}")
    # RVA maps can associate multiple linker-folded functions with one address.
    # Only +0xc0 and +0xc8 are needed for this investigation.
    for slot in (0xC0, 0xC8):
        pointer = struct.unpack("<Q", pe.get_data(VTABLE + slot, 8))[0]
        rva = pointer - pe.OPTIONAL_HEADER.ImageBase
        print(f"XP2 vtable +{slot:#x}: RVA {rva:#x} {'; '.join(symbols.get(rva, []))}")
    selected_city = struct.unpack("<Q", pe.get_data(VTABLE + 0xC0, 8))[0]
    assert selected_city - pe.OPTIONAL_HEADER.ImageBase == FUNCTIONS["SpreadReligion::GetEligibleTargetCity"][0]

    disassembler = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    for name, (rva, size) in FUNCTIONS.items():
        print(f"\n{name} RVA={rva:#x}; {size} bytes (published original size)")
        for ins in disassembler.disasm(pe.get_data(rva, size), rva):
            annotation = ""
            if ins.mnemonic in ("call", "jmp") and ins.op_str.startswith("0x"):
                annotation = "; " + "; ".join(symbols.get(int(ins.op_str, 16), [])) if int(ins.op_str, 16) in symbols else ""
            if ins.address == 0x74D128:
                annotation += " ; UNIT_OPERATION_STARTED hash 0x3d4006f2"
            print(f"{ins.address:08x}: {ins.mnemonic:8s} {ins.op_str}{annotation}")


if __name__ == "__main__":
    main()

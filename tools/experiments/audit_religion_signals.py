"""Audit synchronous Lua signals used by religion-event research.

Requires capstone and pefile; pass --dll and optionally --exe. The audit refuses
other binaries because both function RVAs and instructions are build-specific.
It reads files only and never loads or runs game binaries. The output establishes
the inspected native calls, not what a particular game's Lua context observes.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import capstone
import pefile

DLL_HASH = "092abfbb2176f8df04b5212f819dc269dd83aea866ff05aaf489904a1ff7c41f"
EXE_HASH = "d1a0cfd439e7451be515f47595cfa0b6b983f56d1faf4ea434a4ce3b21491ebe"
DLL_FUNCTIONS = {
    "Unit placement, coordinate update and synchronous moved signal": (0x3B11B0, 3817),
    "OnUnitMoved Lua callback": (0x5A8C30, 187),
    "OnNewMajorityReligion Lua callback": (0x5A9120, 131),
    "Lua signal subscriptions": (0x5A9500, 3165),
    "City follower and majority recomputation": (0x14A6F0, 1271),
    "Reporting event send with city and integer payload": (0x5FB890, 313),
    "Religion spread charge change": (0x3B2A00, 96),
}
EXE_FUNCTIONS = {
    "UnitMoved event registration": (0x14D93A, 0x100),
    "Operation and city-religion event registration": (0x14F055, 0x420),
    "CityReligionChanged event translator": (0x1417C0, 0xB0),
    "CityReligionFollowersChanged event translator": (0x141870, 0xB0),
    "UnitMoved event translator": (0x156FA0, 640),
    "UnitJumped event translator, tail-calls UnitMoved": (0x156650, 598),
    "UnitChargesChanged event translator": (0x154E50, 288),
    "Lua UnitChargesChanged event subscription (event 46)": (0x3E04C0, 112),
    "Lua UnitChargesChanged dispatch callback": (0x2F0840, 79),
    "Lua UnitChargesChanged callback closure": (0x4BBB10, 331),
    "Lua UnitChargesChanged four-argument marshal": (0x15B9F0, 127),
    "UnitOperationStarted event translator": (0x157AA0, 286),
    "GameCore event buffer writer": (0x12BFF0, 507),
    "CityReligionChanged event buffer writer": (0x12F8A0, 336),
    "UnitMoved event buffer writer": (0x1268B0, 464),
    "Lua CityReligionChanged event subscription (event 103)": (0x3E1940, 113),
    "Lua CityReligionChanged dispatch callback": (0x2F08E0, 79),
    "Lua CityReligionChanged callback closure": (0x4BBDB0, 331),
    "Lua CityReligionChanged three-argument marshal": (0x15BBF0, 95),
    "GameCore buffer publication caller": (0x6D5A4, 204),
    "GameCore buffer publication loop": (0x6D2F0, 512),
    "GameCore event dispatcher": (0x5F550, 176),
    "Instrumented GameCore event dispatcher": (0x5F600, 240),
    "Pre-publication buffer filtering": (0x6D720, 1428),
    "Dependency predicate": (0x67D30, 1058),
}


DLL_CHECKS = {
    0x14A916: ("call", "0x1494e0"),  # recompute majority
    0x14A934: ("mov", "dword ptr [r14 + 8], edi"),  # store new majority
    0x14A974: ("cmp", "edi, r15d"),  # compare old majority
    0x14A979: ("cmp", "eax, r12d"),  # compare follower count
    0x14AAE1: ("mov", "r8d, edi"),  # payload = new majority
    0x14AB03: ("call", "0x5fb890"),
    0x3B1D2A: ("add", "rcx, 0x16e0"),
    0x3B1D31: ("call", "0x3afe80"),  # synchronous unit-moved signal
    0x5A917C: ("call", "0x244a0"),  # CallHook, OnNewMajorityReligion
    0x3B2A04: ("mov", "r9d, dword ptr [rcx + 0x10]"),  # old charges
    0x3B2A08: ("lea", "r8d, [r9 + rdx]"),  # new charges
    0x3B2A3C: ("mov", "dword ptr [rsp + 0x20], 0xb2176dc4"),
    0x3B2A56: ("call", "0x5fb9d0"),
}
EXE_CHECKS = {
    0x14F419: ("mov", "dword ptr [rbp + 0x10], 0x51c84cba"),
    0x14F433: ("lea", "rcx, [rip - 0xdc7a]"),  # after lookup: 0x1417c0
    0x1417F2: ("mov", "eax, dword ptr [rdx + 0x50]"),
    0x141849: ("call", "0x12f8a0"),
    0x14F076: ("lea", "rcx, [rip + 0x8a23]"),  # after lookup: 0x157aa0
    0x14D9AF: ("lea", "rcx, [rip + 0x95ea]"),  # after lookup: 0x156fa0
    0x14DA2F: ("lea", "rcx, [rip + 0x8c1a]"),  # jumped: 0x156650
    0x1568A1: ("jmp", "0x156fa0"),  # jumped -> ordinary UnitMoved
    0x14E62F: ("lea", "rcx, [rip + 0x681a]"),  # charges: 0x154e50
    0x154EA7: ("mov", "eax, dword ptr [r8 + 0x50]"),
    0x154ECF: ("mov", "eax, dword ptr [r8 + 0x54]"),
    0x3E051B: ("mov", "ecx, 0x2e"),  # event ID 46
    0x2F0861: ("lea", "rdx, [rip + 0x1cb2a8]"),  # closure 0x4bbb10
    0x4BBC1E: ("call", "0x15b9f0"),
    0x15B9F0: ("movsx", "eax, word ptr [rdx]"),
    0x15BA14: ("movd", "xmm0, dword ptr [rdx + 4]"),
    0x15BA36: ("movd", "xmm0, dword ptr [rdx + 8]"),
    0x15BA50: ("movd", "xmm0, dword ptr [rdx + 0xc]"),
    0x3E199B: ("mov", "ecx, 0x67"),  # CityReligionChanged event ID 103
    0x3E19A0: ("call", "0x9aaa0"),
    0x3E197E: ("lea", "rax, [rip - 0xf10a5]"),  # 0x2f08e0, callback
    0x2F0901: ("lea", "rdx, [rip + 0x1cb4a8]"),  # 0x4bbdb0, closure
    0x2F090B: ("call", "0xdb3890"),
    0x4BBEBE: ("call", "0x15bbf0"),
    0x15BBF0: ("movsx", "eax, word ptr [rdx]"),  # player
    0x15BC18: ("movd", "xmm0, dword ptr [rdx + 4]"),  # city
    0x15BC32: ("movd", "xmm0, dword ptr [rdx + 8]"),  # new majority
    0x12C072: ("lock xadd", "dword ptr [rsi + 0x38], edi"),
    0x12F923: ("lock xadd", "dword ptr [rsi + 0x38], edi"),
    0x126937: ("lock xadd", "dword ptr [rsi + 0x38], edi"),
    0x12F949: ("mov", "dword ptr [rbx + 4], 0x67"),
    0x12F9B6: ("mov", "dword ptr [rax + 0x38], esi"),
    0x157B10: ("mov", "dword ptr [rbp - 8], ecx"),
    0x12C152: ("mov", "dword ptr [rcx + 0x38], eax"),
    0x157059: ("mov", "dword ptr [rbp + 0x4f], edi"),
    0x126A17: ("mov", "dword ptr [rcx + 0x38], eax"),
    0x6D5FD: ("lea", "rbx, [rip + 0x125a1fc]"),  # manager at 0x12c7800
    0x6D62F: ("mov", "rcx, rbx"),
    0x6D632: ("call", "0x6d2f0"),
    0x6D33E: ("lea", "rcx, [rbx + 0x20]"),  # first buffer 0x12c7820
    0x6D474: ("call", "0x5f550"),
    0x6D442: ("call", "0x5f600"),
    0x5F5CB: ("call", "qword ptr [r8 + 0x20]"),
    0x5F5D8: ("add", "qword ptr [rdi], rcx"),  # advance only after dispatch
    0x5F6A5: ("call", "qword ptr [r8 + 0x20]"),
    0x5F6B2: ("add", "qword ptr [rdi], rcx"),
    0x6D811: ("call", "0x68160"),
    0x6D825: ("mov", "ecx, dword ptr [r13 + 0x38]"),
    0x6820E: ("call", "0x67d30"),
    0x67D30: ("mov", "eax, dword ptr [r8 + 0x38]"),
}


def audit(path: Path, expected: str, functions: dict[str, tuple[int, int]],
          checks: dict[int, tuple[str, str]]) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    print(f"{path.resolve()}\nSHA-256: {digest}")
    if digest != expected:
        raise SystemExit("Unrecognised game build; refusing to interpret these RVAs")
    pe = pefile.PE(str(path))
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    for rva, expected_instruction in checks.items():
        instruction = next(md.disasm(pe.get_data(rva, 16), rva), None)
        actual = None if instruction is None else (instruction.mnemonic, instruction.op_str)
        if actual != expected_instruction:
            raise SystemExit(f"Unexpected instruction at {rva:#x}: {actual!r}; expected {expected_instruction!r}")
    print(f"Verified {len(checks)} instruction anchors")
    for name, (rva, size) in functions.items():
        print(f"\n{name}: RVA={rva:#x}, {size} bytes")
        for i in md.disasm(pe.get_data(rva, size), rva):
            print(f"{i.address:08x}: {i.mnemonic:8s} {i.op_str}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dll", type=Path, required=True)
    parser.add_argument("--exe", type=Path)
    args = parser.parse_args()
    audit(args.dll, DLL_HASH, DLL_FUNCTIONS, DLL_CHECKS)
    if args.exe:
        audit(args.exe, EXE_HASH, EXE_FUNCTIONS, EXE_CHECKS)


if __name__ == "__main__":
    main()

"""Inspect where the current XP2 engine keeps the source of city pressure.

Read-only, build-specific audit. Does not run the game or copy game binaries.
Requires capstone and pefile; use --dll with the installed XP2 DLL. The shown
native sender does not establish Lua dispatch timing or that every cause of a
religion change uses the same input. A native argument is not itself a Lua API.
"""
from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

import capstone
import pefile


SHA256 = "4de40abf7c739f53c1f3f825863ace84dc220e5a42d87620e56fceaf3fbd4dc8"

# Calls and register assignments checked in the supplied build. In the spread
# path, lookup by unit owner produces a player object, and its ID is forwarded
# as argument 5 to AddReligiousPressure (Windows x64 ABI). That function then
# forwards it as argument 4 to RecomputeFollowers, which stores it in r13d.
CHECKS = {
    0x74D0CD: ("mov", "ecx, dword ptr [r15 + 0x128]"),
    0x74D0D4: ("call", "0x44f00"),
    0x74D0DF: ("mov", "r12, rax"),
    0x74D279: ("mov", "ebx, dword ptr [r12 + 0xd8]"),
    0x74D28F: ("mov", "dword ptr [rsp + 0x20], ebx"),
    0x74D29A: ("mov", "r8d, esi"),
    0x74D2A2: ("call", "0x1491d0"),
    0x14937C: ("mov", "r9d, dword ptr [rsp + 0xf0]"),
    0x14939C: ("jmp", "0x14a6e0"),
    0x14A701: ("mov", "r13d, r9d"),
    # Sender constructs a city object, hash, and new majority as payload. The
    # final argument of this overload is the new religion, not r13d's actor.
    0x14AAC9: ("mov", "qword ptr [rbp - 0x20], 0x51c84cba"),
    0x14AAD1: ("mov", "r8d, edi"),
    0x14AAEE: ("mov", "word ptr [rbp + 0x32], r15w"),
    0x14AAF3: ("call", "0x5fb8c0"),
    0x14AB29: ("cmp", "r13d, -1"),
    0x14AB61: ("mov", "rcx, qword ptr [rbx + 0x6e0]"),
    0x14AB68: ("mov", "edx, r13d"),
    0x14AB6B: ("call", "0x2af610"),
}


def city_event_payload(pe: pefile.PE, pressure_source: int) -> tuple[int, ...]:
    """Run the real reporting block with a synthetic city and capture its arguments."""
    from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_64, Uc
    from unicorn.x86_const import (
        UC_X86_REG_R8, UC_X86_REG_R13, UC_X86_REG_R14, UC_X86_REG_RBP,
        UC_X86_REG_RCX, UC_X86_REG_RDI, UC_X86_REG_RDX, UC_X86_REG_RSP,
    )

    start, end, sender = 0x14AABC, 0x14AAF8, 0x5FB8C0
    memory = 0x800000
    uc = Uc(UC_ARCH_X86, UC_MODE_64)
    uc.mem_map(start & ~0xFFF, 0x1000)
    uc.mem_write(start, pe.get_data(start, end - start))
    uc.mem_map(sender & ~0xFFF, 0x1000)
    uc.mem_write(sender, b"\xc3")  # Return normally after recording arguments.
    uc.mem_map(memory, 0x1000)
    city = memory + 0x100
    uc.mem_write(memory, struct.pack("<Q", city))
    uc.mem_write(city + 0xA8, struct.pack("<I", 44))  # City ID
    uc.mem_write(city + 0xD8, struct.pack("<I", 3))  # Owner ID
    for register, value in (
        (UC_X86_REG_R14, memory), (UC_X86_REG_R13, pressure_source & 0xFFFFFFFF),
        (UC_X86_REG_RDI, 5), (UC_X86_REG_RBP, memory + 0x400),
        (UC_X86_REG_RSP, memory + 0xE00),
    ):
        uc.reg_write(register, value)

    payloads = []

    def capture(emu, _address, _size, _data):
        identifier = emu.reg_read(UC_X86_REG_RCX)
        descriptor = emu.mem_read(emu.reg_read(UC_X86_REG_RDX), 8)
        owner, object_type, city_id = struct.unpack("<HHI", descriptor)
        religion = emu.reg_read(UC_X86_REG_R8)
        payloads.append((identifier, owner, object_type, city_id, religion))

    uc.hook_add(UC_HOOK_CODE, capture, begin=sender, end=sender)
    uc.emu_start(start, end, count=40)
    assert len(payloads) == 1, payloads
    return payloads[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dll", required=True, type=Path)
    parser.add_argument("--emulate", action="store_true", help="compare the native sender with and without a player source (requires Unicorn)")
    args = parser.parse_args()
    path = args.dll
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    print(f"{path.resolve()}\nSHA-256: {digest}")
    if digest != SHA256:
        raise SystemExit("Unrecognised game DLL; refusing to interpret RVAs")
    pe = pefile.PE(data=data)
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    for address, expected in CHECKS.items():
        instruction = next(decoder.disasm(pe.get_data(address, 16), address), None)
        actual = None if instruction is None else (instruction.mnemonic, instruction.op_str)
        if actual != expected:
            raise SystemExit(f"Unexpected instruction at {address:#x}: {actual!r}; expected {expected!r}")
    print(f"PASS: {len(CHECKS)} actor propagation, event-sender and diplomacy instruction anchors")
    print("The city event sender and the separate native actor use different arguments.")
    print("No Lua actor API, asynchronous delivery order or passive-spread source is proved.")
    if args.emulate:
        unit = city_event_payload(pe, pressure_source=7)
        unattributed = city_event_payload(pe, pressure_source=-1)
        assert unit == unattributed == (0x51C84CBA, 3, 2, 44, 5), (unit, unattributed)
        print(f"PASS: player source 7 and no player source emit the same city event: {unit}")


if __name__ == "__main__":
    main()

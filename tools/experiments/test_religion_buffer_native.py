"""Execute the EXE's event-dependency predicate on controlled event data.

Requires pefile and unicorn. The program never loads or runs the game. It copies
one small code range from a recognised EXE into an isolated Unicorn emulator.
The inputs are synthetic; passing this test proves neither real event flags nor
that a given dependency situation occurs during a game.
"""
from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_64, Uc
from unicorn.x86_const import UC_X86_REG_R8, UC_X86_REG_R9, UC_X86_REG_RAX, UC_X86_REG_RCX, UC_X86_REG_RDX, UC_X86_REG_RSP

EXPECTED = "d1a0cfd439e7451be515f47595cfa0b6b983f56d1faf4ea434a4ce3b21491ebe"
CODE = 0x60000
FUNCTION = 0x67D30
RETURN = 0x58000
STACK = 0x400000
PAYLOAD = 0x500000


def evaluate(code: bytes, older_flags: int, older_unit: int) -> bool:
    machine = Uc(UC_ARCH_X86, UC_MODE_64)
    machine.mem_map(CODE, 0x10000)
    machine.mem_write(CODE, code)
    machine.mem_map(RETURN, 0x1000)
    machine.mem_map(STACK, 0x2000)
    machine.mem_map(PAYLOAD, 0x2000)
    candidate = bytearray(b"\xff" * 0x40)
    older = bytearray(b"\xff" * 0x40)
    for data, unit in ((candidate, 17), (older, older_unit)):
        struct.pack_into("<ii", data, 0, -1, -1)
        struct.pack_into("<HHi", data, 8, 3, 1, unit)
        struct.pack_into("<i", data, 0x30, 0)
    struct.pack_into("<I", candidate, 0x38, 0)
    struct.pack_into("<I", older, 0x38, older_flags)
    machine.mem_write(PAYLOAD, bytes(candidate))
    machine.mem_write(PAYLOAD + 0x1000, bytes(older))
    rsp = STACK + 0x1000
    machine.mem_write(rsp, struct.pack("<Q", RETURN))
    machine.reg_write(UC_X86_REG_RSP, rsp)
    machine.reg_write(UC_X86_REG_RCX, 0)
    machine.reg_write(UC_X86_REG_RDX, PAYLOAD)
    machine.reg_write(UC_X86_REG_R8, PAYLOAD + 0x1000)
    machine.reg_write(UC_X86_REG_R9, 1)
    machine.hook_add(UC_HOOK_CODE, lambda uc, address, size, data: uc.emu_stop() if address == RETURN else None)
    machine.emu_start(FUNCTION, RETURN + 1, count=10000)
    return bool(machine.reg_read(UC_X86_REG_RAX) & 0xFF)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    args = parser.parse_args()
    if hashlib.sha256(args.exe.read_bytes()).hexdigest() != EXPECTED:
        raise SystemExit("Unrecognised EXE; refusing to execute these RVAs")
    pe = pefile.PE(str(args.exe))
    code = pe.get_data(CODE, 0x10000)
    cases = [(0, 17, False), (1, 17, True), (1, 18, False), (2, 18, True)]
    for flags, unit, expected in cases:
        actual = evaluate(code, flags, unit)
        if actual != expected:
            raise AssertionError((flags, unit, expected, actual))
        print(f"older_flags={flags}, older_unit={unit}: dependent={actual}")


if __name__ == "__main__":
    main()

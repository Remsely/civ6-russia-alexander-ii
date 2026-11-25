"""Exercise the current DX12 event-dependency predicate in isolation.

Usage: python tools/experiments/test_religion_buffer_dx12.py --exe PATH
Requires capstone, pefile and unicorn. The game executable is only read; Unicorn runs
one code range against synthetic metadata.  This does not prove that the
blocking record or enabled dependency filter occur in a particular game.
"""
from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

import capstone
import pefile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_64
from unicorn.x86_const import (
    UC_X86_REG_R8, UC_X86_REG_R9, UC_X86_REG_RAX, UC_X86_REG_RCX,
    UC_X86_REG_RDX, UC_X86_REG_RSP,
)

SHA256 = "9d5c0ce047493126a3b0606cabc7f8b03e203c19cf107588784647005045bc39"
CODE, FUNCTION = 0x60000, 0x68A60
RETURN, STACK, PAYLOAD = 0x58000, 0x400000, 0x500000


def record(unit: int | None, flags: int) -> bytes:
    data = bytearray(b"\xff" * 0x40)
    struct.pack_into("<ii", data, 0, -1, -1)
    if unit is not None:
        struct.pack_into("<HHi", data, 8, 3, 1, unit)
    struct.pack_into("<I", data, 0x30, 0)
    struct.pack_into("<I", data, 0x38, flags)
    return bytes(data)


def dependent(code: bytes, candidate: bytes, older: bytes) -> bool:
    cpu = Uc(UC_ARCH_X86, UC_MODE_64)
    for address, size in ((CODE, 0x10000), (RETURN, 0x1000),
                          (STACK, 0x2000), (PAYLOAD, 0x2000)):
        cpu.mem_map(address, size)
    cpu.mem_write(CODE, code)
    cpu.mem_write(PAYLOAD, candidate)
    cpu.mem_write(PAYLOAD + 0x1000, older)
    cpu.mem_write(STACK + 0x1000, struct.pack("<Q", RETURN))
    for register, value in (
        (UC_X86_REG_RSP, STACK + 0x1000), (UC_X86_REG_RCX, 0),
        (UC_X86_REG_RDX, PAYLOAD), (UC_X86_REG_R8, PAYLOAD + 0x1000),
        (UC_X86_REG_R9, 1),
    ):
        cpu.reg_write(register, value)
    cpu.emu_start(FUNCTION, RETURN, count=10000)
    return bool(cpu.reg_read(UC_X86_REG_RAX) & 0xFF)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", required=True, type=Path)
    path = parser.parse_args().exe
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SHA256:
        raise SystemExit("Unrecognised DX12 executable; refusing build-specific RVAs")
    pe = pefile.PE(data=raw)
    code = pe.get_data(CODE, 0x10000)
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    instruction = next(decoder.disasm(pe.get_data(FUNCTION, 16), FUNCTION), None)
    if instruction is None or (instruction.mnemonic, instruction.op_str) != ("mov", "eax, dword ptr [r8 + 0x38]"):
        raise SystemExit("Unexpected dependency predicate entry")

    # This synthetic older record identifies the same unit and has flag 1.
    # Operation/charge metadata identifies that unit, city metadata does not;
    # the three candidate records all have flags zero in the observed DX12
    # translators.  The predicate returns a dependency for the unit records
    # but not the city record.  This alone does not prove the older record can
    # occur in a particular game or that the full filter will reorder them.
    older = record(17, 1)
    outcomes = {
        "operation": dependent(code, record(17, 0), older),
        "city": dependent(code, record(None, 0), older),
        "charges": dependent(code, record(17, 0), older),
    }
    assert outcomes == {"operation": True, "city": False, "charges": True}, outcomes
    for name, result in outcomes.items():
        print(f"{name}: dependency={result}")
    print("PASS: predicate distinguishes unit records from city record")
    print("Synthetic input only: actual flagged records, enabled filtering and reordering are unproved")


if __name__ == "__main__":
    main()

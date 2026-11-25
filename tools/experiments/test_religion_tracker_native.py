"""Emulate a native diplomacy-tracker update without running the game.

Requires ``unicorn`` and ``pefile``; no game bytes are distributed. This is a
micro-test of one function from one build, not an end-to-end game test. The
tracker input layout is derived from disassembly and the test sets it directly;
it does not emulate the effect's creation, event routing, save/load or AI.
"""

from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

import pefile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_64
from unicorn.x86_const import UC_X86_REG_R8, UC_X86_REG_R9, UC_X86_REG_RCX, UC_X86_REG_RDX, UC_X86_REG_RSP

SHA256 = "092abfbb2176f8df04b5212f819dc269dd83aea866ff05aaf489904a1ff7c41f"
UPDATE_RVA, UPDATE_SIZE = 0x2BFC60, 166
INITIALIZE_RVA, INITIALIZE_SIZE = 0x2BF4C0, 242
CODE, RETURN = 0x100000, 0x100F00
STACK, TRACKER = 0x200000, 0x300000


def run(dll: Path, initial: int) -> list[int]:
    if hashlib.sha256(dll.read_bytes()).hexdigest() != SHA256:
        raise SystemExit("Different game build: verify function and object layout before testing.")
    pe = pefile.PE(str(dll))
    cpu = Uc(UC_ARCH_X86, UC_MODE_64)
    for address in (CODE, STACK, TRACKER):
        cpu.mem_map(address, 0x1000)
    cpu.mem_write(CODE, pe.get_data(UPDATE_RVA, UPDATE_SIZE))

    def put(offset: int, value: int) -> None:
        cpu.mem_write(TRACKER + offset, struct.pack("<i", value))

    def get(offset: int) -> int:
        return struct.unpack("<i", cpu.mem_read(TRACKER + offset, 4))[0]

    # FixedPointT<8>, inactive tracker: decay by one point each 10 updates.
    put(4, initial * 256)
    put(0x20, initial * 256)
    put(0x24, 0)
    put(0x28, 0)
    put(0x2C, 256)
    put(0x30, 10)
    values = [get(4) // 256]
    for _ in range(10 * (abs(initial) + 1)):
        cpu.mem_write(STACK + 0x800, struct.pack("<Q", RETURN))
        cpu.reg_write(UC_X86_REG_RSP, STACK + 0x800)
        cpu.reg_write(UC_X86_REG_RCX, TRACKER)
        cpu.emu_start(CODE, RETURN)
        values.append(get(4) // 256)
    return values


def check_active_reinitialization(dll: Path, initial: int) -> None:
    """Run real Initialize+Update with an already-active tracker.

    Only the string assignment is stubbed: it stores the reason text and does
    not participate in score arithmetic. Inputs are manually set to the simple
    effect's no-accumulation defaults; this does not emulate its calling code.
    """
    pe = pefile.PE(str(dll))
    cpu = Uc(UC_ARCH_X86, UC_MODE_64)
    for address in (0x2BF000, 0x993000, STACK, TRACKER, 0x100000):
        cpu.mem_map(address, 0x1000)
    cpu.mem_write(INITIALIZE_RVA, pe.get_data(INITIALIZE_RVA, INITIALIZE_SIZE))
    cpu.mem_write(UPDATE_RVA, pe.get_data(UPDATE_RVA, UPDATE_SIZE))
    cpu.mem_write(0x993700, b"\xc3")  # String::Assign, not score arithmetic.

    def put32(address: int, value: int) -> None:
        cpu.mem_write(address, struct.pack("<i", value))

    def put64(address: int, value: int) -> None:
        cpu.mem_write(address, struct.pack("<Q", value))

    # One existing relationship and constant InitialValue/MaxValue.
    cpu.mem_write(TRACKER, b"\x01")
    put32(TRACKER + 4, initial * 256)
    put32(TRACKER + 0x100, initial * 256)
    put32(TRACKER + 0x104, initial * 256)
    put32(TRACKER + 0x108, 0)
    put32(TRACKER + 0x10C, -256)
    for _ in range(100):
        rsp = STACK + 0x800
        put64(rsp, RETURN)
        put32(rsp + 0x28, 0)  # IncrementTurns
        put32(rsp + 0x30, 10)  # ReductionTurns: irrelevant to active tracker
        put64(rsp + 0x38, TRACKER + 0x10C)
        put64(rsp + 0x40, TRACKER + 0x120)  # ignored by the text stub
        put32(rsp + 0x48, 0)
        cpu.reg_write(UC_X86_REG_RSP, rsp)
        cpu.reg_write(UC_X86_REG_RCX, TRACKER)
        cpu.reg_write(UC_X86_REG_RDX, TRACKER + 0x100)
        cpu.reg_write(UC_X86_REG_R8, TRACKER + 0x104)
        cpu.reg_write(UC_X86_REG_R9, TRACKER + 0x108)
        cpu.emu_start(INITIALIZE_RVA, RETURN)
        value = struct.unpack("<i", cpu.mem_read(TRACKER + 4, 4))[0]
        assert value == initial * 256


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dll", type=Path, required=True)
    args = parser.parse_args()
    # Vanilla's configured decay applies to -9; the mod's -12 does not define
    # the same decay arguments and must not be inferred from this test.
    for initial in (-9,):
        values = run(args.dll, initial)
        assert all(initial <= value <= 0 for value in values)
        for n in range(abs(initial) + 1):
            assert values[n * 10] == initial + n
        assert values[-1] == 0
        print(f"PASS {initial}: native inactive tracker fades toward zero every 10 updates")
    for initial in (-9, -12):
        check_active_reinitialization(args.dll, initial)
        print(f"PASS {initial}: 100 native active reinitializations do not accumulate")
    print("Limitations: controlled object layout only; activation, reload and game event timing untested.")


if __name__ == "__main__":
    main()

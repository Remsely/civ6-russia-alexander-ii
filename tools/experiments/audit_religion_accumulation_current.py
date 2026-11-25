"""Execute selected current-build diplomacy-effect instructions with stubs.

The executable code is read from the locally installed Gathering Storm DLL;
none is distributed here. This is an isolated unit experiment, not a test of
when modifiers activate, database loading, persistence, or a real game. The
lookup stub returns a fixed current score on both of the native lookups.

Dependencies: pefile and unicorn. Pass the path to GameCore_XP2_FinalRelease.dll.
"""
from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

import pefile
import capstone
from unicorn import Uc, UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_64
from unicorn.x86_const import (
    UC_X86_REG_R8, UC_X86_REG_R9, UC_X86_REG_RAX, UC_X86_REG_RCX,
    UC_X86_REG_RDX, UC_X86_REG_RSP,
)

SHA256 = "4de40abf7c739f53c1f3f825863ace84dc220e5a42d87620e56fceaf3fbd4dc8"
APPLY, ACCUMULATE = 0x944700, 0x942A80
LOOKUP, ACTIVATE, GET_BLACKBOARD = 0x2BEB60, 0x2BDB10, 0x72A960

# These checked instructions verify the selected effect's essential branches,
# double lookup, and activation call in the exact DLL before emulating. This
# is a build-specific isolated test, not a proof of event or tracker timing.
ANCHORS = {
    0x94470D: ("cmp", "byte ptr [rcx + 0x48], 0"),
    0x944772: ("call", "0x2beb60"),
    0x94477F: ("sar", "edx, 8"),
    0x944782: ("add", "edx, dword ptr [r14 + 0x30]"),
    0x944786: ("call", "0x942a80"),
    0x9447C1: ("call", "0x2beb60"),
    0x944821: ("call", "0x72a960"),
    0x944886: ("call", "0x2bdb10"),
    0x942AB5: ("call", "0x2beb60"),
    0x942AC1: ("sar", "ecx, 8"),
    0x942AC4: ("add", "ecx, ebx"),
}


def emulate(pe: pefile.PE, old: int, initial: int, maximum: int, accumulates: bool):
    cpu = Uc(UC_ARCH_X86, UC_MODE_64)
    for address, size in ((0x940000, 0x5000), (0x2BE000, 0x1000),
                          (0x2BD000, 0x1000), (0x72A000, 0x1000),
                          (0x100000, 0x10000), (0x200000, 0x10000)):
        cpu.mem_map(address, size)
    cpu.mem_write(APPLY, pe.get_data(APPLY, 463))
    cpu.mem_write(ACCUMULATE, pe.get_data(ACCUMULATE, 114))
    for address in (LOOKUP, ACTIVATE, GET_BLACKBOARD, 0x100100, 0x100200, 0x100300):
        cpu.mem_write(address, b"\xc3")

    def put64(addr, value): cpu.mem_write(addr, struct.pack("<Q", value))
    def put32(addr, value): cpu.mem_write(addr, struct.pack("<i", value))
    def get32(addr): return struct.unpack("<i", bytes(cpu.mem_read(addr, 4)))[0]

    effect, player, blackboard, target, target_obj, vtable, current = (
        0x200000, 0x202000, 0x203000, 0x204000, 0x205000, 0x206000, 0x207000)
    put64(effect, vtable)
    put64(vtable + 0x78, 0x100100)
    put64(vtable + 0x68, 0x100200)
    put64(effect + 0x28, player)
    put64(player + 0x6E0, blackboard)
    put64(target, target_obj)
    put32(target_obj + 0xD8, 3)
    put32(current, old * 256)
    put32(effect + 0x30, initial)
    put32(effect + 0x34, maximum)
    put32(effect + 0x10, 0)
    put32(effect + 0x20, 4)
    cpu.mem_write(effect + 0x48, bytes([accumulates]))
    observed = []
    lookups = []

    def hook(uc, address, size, user):
        if address == LOOKUP:
            sp = uc.reg_read(UC_X86_REG_RSP)
            lookups.append((uc.reg_read(UC_X86_REG_RCX), uc.reg_read(UC_X86_REG_R8) & 0xFFFFFFFF,
                            uc.reg_read(UC_X86_REG_R9) & 0xFFFFFFFF, get32(sp + 0x28)))
            uc.reg_write(UC_X86_REG_RAX, current)
        elif address == GET_BLACKBOARD:
            uc.reg_write(UC_X86_REG_RAX, 0x208000)
        elif address == 0x100100:
            uc.reg_write(UC_X86_REG_RAX, 0)
        elif address == ACTIVATE:
            sp = uc.reg_read(UC_X86_REG_RSP)
            initial_ptr = uc.reg_read(UC_X86_REG_R9)
            maximum_ptr = struct.unpack("<Q", bytes(uc.mem_read(sp + 0x28, 8)))[0]
            observed.append((get32(initial_ptr) // 256, get32(maximum_ptr) // 256))

    cpu.hook_add(UC_HOOK_CODE, hook)
    # Windows x64 ABI: RSP is 8 mod 16 on function entry, with 32 bytes of
    # caller shadow space available after the return address.
    sp = 0x20F008
    put64(sp, 0x100300)
    cpu.reg_write(UC_X86_REG_RSP, sp)
    cpu.reg_write(UC_X86_REG_RCX, effect)
    cpu.reg_write(UC_X86_REG_RDX, target)
    cpu.reg_write(UC_X86_REG_R8, 0)
    cpu.emu_start(APPLY, 0x100300, count=10000)
    assert lookups, "Expected at least one native current-score lookup"
    assert all(item == (blackboard + 0x12C0, 3, 0xFFFFFFFF, 4) for item in lookups), lookups
    assert len(lookups) == (3 if accumulates else 1), lookups
    return observed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dll", required=True, type=Path)
    args = parser.parse_args()
    if hashlib.sha256(args.dll.read_bytes()).hexdigest() != SHA256:
        raise SystemExit("Different game build: independently inspect addresses before testing.")
    pe = pefile.PE(str(args.dll))
    disassembler = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    for address, expected in ANCHORS.items():
        instruction = next(disassembler.disasm(pe.get_data(address, 16), address), None)
        actual = None if instruction is None else (instruction.mnemonic, instruction.op_str)
        if actual != expected:
            raise SystemExit(f"Unexpected instruction at {address:#x}: {actual!r}; expected {expected!r}")
    print(f"Verified {len(ANCHORS)} anchors for DLL {SHA256}")
    cases = ((0, -6), (-6, -18), (-18, -42), (-42, -90), (-75, -156))
    for current, expected in cases:
        result = emulate(pe, current, -6, -54, True)
        assert result == [(expected, expected)], (current, result)
        print(f"current={current}, initial=-6, configured max=-54 -> activation={result}")
    assert emulate(pe, 0, -6, -54, False) == [(-6, -54)]
    assert emulate(pe, -6, -3, -75, True) == [(-15, -15)]
    assert emulate(pe, 3, 2, 30, True) == [(8, 8)]
    print("PASS: native active accumulation overwrote the configured limit in this model")
    print("Controlled lookup only; game timing and modifier reactivation remain untested.")


if __name__ == "__main__":
    main()

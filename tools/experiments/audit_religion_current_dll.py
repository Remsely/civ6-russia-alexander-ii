"""Read-only, build-specific audit of the loaded XP2 religion code.

Run with --dll PATH. Requires capstone and pefile, does not load game code.
The audit verifies only the listed anchors; event delivery, save/load and other
builds/platforms remain separate questions.
"""
import argparse
import hashlib
import struct
from pathlib import Path

import capstone
import pefile

SHA256 = "4de40abf7c739f53c1f3f825863ace84dc220e5a42d87620e56fceaf3fbd4dc8"
VTABLE, TARGET = 0xA444F0, 0x6735A0
CHECKS = {
    0x74D046: ("mov", "dword ptr [rbx + 0xc], 0x5eea3a1a"),
    0x74D0F5: ("call", "qword ptr [rbx + 0xc0]"),
    0x74D155: ("mov", "dword ptr [rbp + 0x128], 0x3d4006f2"),
    0x74D179: ("call", "0x5fb8c0"),
    0x74D2A2: ("call", "0x1491d0"),
    0x74D562: ("call", "0x3b22c0"),
    0x74D5D0: ("call", "0x34cca0"),
    0x6735E9: ("cmp", "eax, dword ptr [rbp + 0x128]"),
    0x673610: ("cmp", "byte ptr [rbp + 0xa25], 0"),
    0x6736E6: ("cmp", "byte ptr [rbp + 0xa25], 0"),
    0x673700: ("cmp", "rdi, 6"),
    0x5A8D06: ("call", "0x244a0"),
    0x5A91BC: ("call", "0x244a0"),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dll", required=True, type=Path)
    path = parser.parse_args().dll
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    print(f"{path.resolve()}\nSHA-256: {digest}")
    if digest != SHA256:
        raise SystemExit("Unexpected DLL; refusing to interpret build-specific addresses")
    pe = pefile.PE(data=raw)
    pointer = struct.unpack("<Q", pe.get_data(VTABLE + 0xC0, 8))[0]
    assert pointer - pe.OPTIONAL_HEADER.ImageBase == TARGET, "unexpected target vtable slot"
    dis = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    for address, expected in CHECKS.items():
        instruction = next(dis.disasm(pe.get_data(address, 16), address), None)
        actual = None if instruction is None else (instruction.mnemonic, instruction.op_str)
        if actual != expected:
            raise SystemExit(f"Unexpected instruction at {address:#x}: {actual!r}, expected {expected!r}")
    assert 0x74D0F5 < 0x74D179 < 0x74D2A2 < 0x74D562 < 0x74D5D0
    print(f"Verified {len(CHECKS)} instruction anchors and vtable +0xc0 = {TARGET:#x}.")
    print("Confirmed native call order: target selection -> operation event -> pressure -> charge -> destruction call.")
    print("Lua event delivery, state timing, save/load and non-Windows builds are NOT verified.")


if __name__ == "__main__":
    main()

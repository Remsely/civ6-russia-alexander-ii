"""Read-only audit of an installed Civilization VI Windows executable.

Dependencies: ``python -m pip install capstone pefile``.
Usage: ``python tools/experiments/audit_religion_event_delivery.py --exe PATH``.

This disassembles only a single previously inspected executable SHA-256.
Other builds, platforms and configurations must be investigated independently.
The listing shows registration of UNIT_OPERATION_STARTED, its translator and
the event-buffer writer. It does not claim to prove gameplay Lua delivery order.
No game executable is distributed, loaded or modified.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import capstone
import pefile

EXPECTED_SHA256 = "d1a0cfd439e7451be515f47595cfa0b6b983f56d1faf4ea434a4ce3b21491ebe"

# Entry 68 / 0x44 corresponds to UNIT_OPERATION_STARTED in the published
# engine-event research by cru121, commit 05e08b4848526f6c47c9996d2649e1fb3edfaf19.
REGISTRATION_START = 0x14F055
FUNCTIONS = {
    "registration excerpt": (REGISTRATION_START, 0x38),
    "event translator": (0x157AA0, 286),
    "event buffer writer": (0x12BFF0, 507),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", required=True, type=Path)
    args = parser.parse_args()
    digest = hashlib.sha256(args.exe.read_bytes()).hexdigest()
    print(f"File: {args.exe.resolve()}\nSHA-256: {digest}")
    if digest != EXPECTED_SHA256:
        raise SystemExit("Different executable: published RVAs are not verified for this build.")

    pe = pefile.PE(str(args.exe))
    for library in pe.DIRECTORY_ENTRY_IMPORT:
        for item in library.imports:
            if item.address - pe.OPTIONAL_HEADER.ImageBase == 0xF97728:
                print(f"IAT 0xf97728: {library.dll!r}!{item.name!r}")

    disassembler = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    for name, (rva, size) in FUNCTIONS.items():
        print(f"\n{name}: RVA {rva:#x}, {size} bytes")
        for instruction in disassembler.disasm(pe.get_data(rva, size), rva):
            print(f"{instruction.address:08x}: {instruction.mnemonic:8s} {instruction.op_str}")


if __name__ == "__main__":
    main()

"""Inspect capital collection and UnitJumped emission in a local GS DLL.

Reads one SHA-pinned game build; does not copy the binary or execute the game.
Requires pefile and capstone. This is not an event-delivery or reload test.
"""
from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

import capstone
import pefile


SHA256 = '092abfbb2176f8df04b5212f819dc269dd83aea866ff05aaf489904a1ff7c41f'
SECTIONS = {
    'AllCapitalCities::GetItems': (0x83FE70, 404),
    'AllCapitalCities::OnInitialize': (0x840CC0, 336),
    'CityIsOwnerCapitalContinent::OnInitialize': (0x8A5750, 315),
    'capital-change callback thunk': (0x97FA30, 18),
    'CityIsOwnerCapitalContinent::OnCapitalChanged': (0x961300, 114),
    'SimpleCollection::Invalidate': (0x95C080, 124),
    'Exports::City::IsCapital': (0x58DB50, 26),
    'Unit::Placement::Set entry': (0x3B11B0, 0xF9),
    'Unit::Placement::Set jump event': (0x3B1963, 0xB2),
    'Unit::Placement::Set teleported event': (0x3B1AEA, 0x2B),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dll', required=True, type=Path)
    args = parser.parse_args()
    if hashlib.sha256(args.dll.read_bytes()).hexdigest() != SHA256:
        raise SystemExit('Different build: offsets and assumptions need independent validation.')
    pe = pefile.PE(str(args.dll))
    base = pe.OPTIONAL_HEADER.ImageBase
    tables = {
        'AllCapitalCities vtable excerpt': (0xA7E980, (0x83FE70, 0x891830, 0x891D30, 0x840CC0)),
        'Capital-change callback vtable excerpt': (0xAB81A8, (0x97BEA0, 0x97BEA0, 0x97FA30)),
        'AllCapitalCities callback vtable excerpt': (0xAB7458, (0x97B5F0, 0x97B5F0, 0x980620)),
    }
    for name, (rva, expected) in tables.items():
        actual = tuple(x-base for x in struct.unpack('<' + 'Q'*len(expected), pe.get_data(rva, 8*len(expected))))
        assert actual == expected, (name, actual)
        print(f'{name} @{rva:#x}: {", ".join(hex(x) for x in actual)}')
    disassembler = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    for name, (rva, size) in SECTIONS.items():
        print(f'\n{name} @{rva:#x}:')
        for ins in disassembler.disasm(pe.get_data(rva, size), rva):
            print(f'{ins.address:08x}: {ins.mnemonic:8s} {ins.op_str}')
    print('\nStatic inspection only: live event order, delivery, uniqueness and save/load remain untested.')


if __name__ == '__main__':
    main()

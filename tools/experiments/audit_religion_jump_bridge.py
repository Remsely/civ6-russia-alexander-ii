"""Verify the Windows EXE registration and jump-to-movement translator path.

This is read-only static inspection of one hash-pinned executable, not a game
runtime, an event-delivery test, or a guarantee of callback ordering in Lua.
Requires pefile and capstone; game code is not included in the repository.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import capstone
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP
import pefile

SHA256 = 'd1a0cfd439e7451be515f47595cfa0b6b983f56d1faf4ea434a4ce3b21491ebe'
SECTIONS = {
    'registration: hash search and insertion to translator': (0x14D9D0, 0x6A),
    'jump translator: initial data read': (0x156650, 0x90),
    'jump translator: enqueue and tail jump': (0x156847, 0x5F),
    'move translator: initial data read': (0x156FA0, 0x85),
    'move translator: enqueue': (0x1571C7, 0x4F),
    'UNIT_JUMPED writer event header': (0x1262B7, 0x18),
    'UNIT_MOVED writer event header': (0x126957, 0x18),
}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--exe', type=Path, required=True)
    args = p.parse_args()
    if hashlib.sha256(args.exe.read_bytes()).hexdigest() != SHA256:
        raise SystemExit('Different executable build: independently re-check all offsets')
    pe = pefile.PE(str(args.exe))
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    checked = {}
    for name, (start, size) in SECTIONS.items():
        print(f'\n{name}:')
        for ins in md.disasm(pe.get_data(start, size), start):
            checked[ins.address] = ins
            print(f'{ins.address:08x}: {ins.mnemonic:8s} {ins.op_str}')
    ins = checked[0x14DA1F]
    assert ins.mnemonic == 'mov' and ins.operands[1].type == X86_OP_IMM and ins.operands[1].imm == 0xCC6F2070
    assert checked[0x14D9D0].mnemonic == 'cmp' and checked[0x14D9D0].operands[1].imm == 0xCC6F2070
    assert checked[0x14D9FC].mnemonic == 'lea' and checked[0x14D9FC].op_str == 'r9, [rbp - 0x10]'
    assert checked[0x14DA26].mnemonic == 'call' and checked[0x14DA26].operands[0].imm == 0x4DFB70
    ins = checked[0x14DA2F]
    op = ins.operands[1]
    assert ins.mnemonic == 'lea' and op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP
    assert ins.address + ins.size + op.mem.disp == 0x156650
    assert checked[0x14DA36].mnemonic == 'mov' and checked[0x14DA36].op_str == 'qword ptr [rax + 0x28], rcx'
    for address in (0x1566C7, 0x15700E):
        assert checked[address].mnemonic == 'mov' and checked[address].op_str == 'rax, qword ptr [rdx + 0x48]'
    assert checked[0x156863].mnemonic == 'call' and checked[0x156863].operands[0].imm == 0x126210
    assert checked[0x1568A1].mnemonic == 'jmp' and checked[0x1568A1].operands[0].imm == 0x156FA0
    assert checked[0x1571E3].mnemonic == 'call' and checked[0x1571E3].operands[0].imm == 0x1268B0
    for address, expected in ((0x1262BD, 326), (0x12695D, 23)):
        ins = checked[address]
        assert ins.mnemonic == 'mov' and ins.operands[1].imm == expected
    print('\nPASS: hash registration and tail call to the regular movement translator')
    print('Both translators read the same +0x48 field from the original event pointer.')
    print('Intermediate external calls and real Lua callback order remain unverified.')


if __name__ == '__main__':
    main()

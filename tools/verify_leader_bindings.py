"""Check the cooked leader's render-node bone palettes against its actual FGX.

The FGX file mesh collection and Model.MeshBindings need not have the same order.
Checking just FGX vertices misses the mismatch introduced by a differently ordered
GEO/AST. This reads the BLP's reflection metadata and checks the cooked palettes.
Supported input: the SDK's CIVBLP v2 packages, including their zeroed outer header.
No BLP bytes are modified. The reader deliberately rejects unfamiliar layouts.
"""
import argparse
import json
import re
import struct
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BLP = ROOT / 'mod/Platforms/Windows/BLPs/leaders/leader_remsely_alexander_ii.blp'
SCALARS = {'uint8': 'B', 'uint16': 'H', 'uint32': 'I', 'uint64': 'Q',
           'int32': 'i', 'float': 'f', 'bool': '?'}


class CookedPackage:
    def __init__(self, path):
        with Path(path).open('rb') as f:
            header = f.read(28)
            if header[:8] != b'CIVBLP\x02\0':
                raise ValueError('expected SDK CIVBLP version 2')
            package_start, package_size = struct.unpack_from('<II', header, 8)
            end = package_start + package_size
            if not 0 < end < 64 * 1024 * 1024:
                raise ValueError('unexpected BLP metadata size')
            f.seek(0)
            self.data = f.read(end)
        if len(self.data) != end:
            raise ValueError('truncated BLP metadata')
        # The beginning of the v2 package is zeroed. The nested TypeInfoStripe
        # retains its header tail, allocation table and reflection records.
        root = self.data.index(b'TypeInfoStripe\0', package_start)
        start = root - 0x58
        temp, size = self.unpack('II', root - 56)
        link, = self.unpack('I', root - 32)
        if self.unpack('IIII', root - 16) != (16, 48, 40, 16):
            raise ValueError('unrecognized type-package header')
        if not 0 < link < size or (size - link) % 40:
            raise ValueError('invalid type allocation table')
        block = root + len(b'TypeInfoStripe\0')
        nested_end = start + temp + size
        if not block < start + temp < nested_end < end:
            raise ValueError('invalid type-package boundaries')
        self.alloc = [self.allocation(o, block, start + temp)
                      for o in range(start + temp + link, nested_end, 40)]
        self.types = {}
        for a in self.alloc:
            if self.string(a['type']) != 'TypeInfoStripe::TypeVersion':
                continue
            if a['size'] != a['count'] * 56:
                raise ValueError('unexpected TypeVersion size')
            for i in range(a['count']):
                at = a['at'] + 56 * i
                name, _, fields = self.unpack('QQQ', at)
                _, byte_size, flags = self.unpack('III', at + 40)
                fs = []
                if fields:
                    fa = self.alloc[fields - 1]
                    if fa['size'] != fa['count'] * 24:
                        raise ValueError('unexpected FieldVersion size')
                    for j in range(fa['count']):
                        fn, ft, _, offset = self.unpack('QQII', fa['at'] + 24 * j)
                        fs.append((self.string(fn), self.string(ft), offset))
                self.types[self.string(name)] = {'size': byte_size, 'flags': flags, 'fields': fs}
        if 'LeaderPackageEntryV2' not in self.types:
            raise ValueError('not a reflected leader package')

        # Find the main table independently of mesh count/order. Ten consecutive
        # allocation records identify it; all remaining entries are then checked.
        def valid(at):
            stripe, off, sz, count, _, tp = self.unpack('QIII4xQQ', at)
            return stripe in (0, 1) and 0 < count <= sz < end and off < end and 0 < tp < 10000

        table = next((o for o in range(nested_end, end - 400)
                      if all(valid(o + 40 * j) for j in range(10))), None)
        if table is None:
            raise ValueError('main BLP allocation table not found')
        records = []
        for o in range(table, end - 39, 40):
            if not valid(o):
                break
            records.append(self.allocation(o, 0, 0))
        # The char type describes itself. Its string locates the temp stripe;
        # unlike fixed byte offsets, this survives changed assets and timelines.
        chars = [a for i, a in enumerate(records)
                 if a['stripe'] == 1 and a['size'] == a['count'] == 5 and a['type'] == i + 1]
        if len(chars) != 1:
            raise ValueError('ambiguous main char type')
        temp = self.data.index(b'char\0', nested_end, table) - chars[0]['offset']
        self.alloc = records
        for a in self.alloc:
            a['at'] = (nested_end if a['stripe'] == 0 else temp) + a['offset']
            if not nested_end <= a['at'] < a['at'] + a['size'] <= table:
                raise ValueError('allocation outside main data stripes')
        for a in self.alloc:
            self.string(a['type'])  # validate every type-name pointer

    def unpack(self, fmt, at):
        return struct.unpack_from('<' + fmt, self.data, at)

    def allocation(self, at, block, temp):
        stripe, _, _, _, offset, size, count = self.unpack('BB4sHIII', at)
        tp, = self.unpack('Q', at + 32)
        return {'stripe': stripe, 'offset': offset, 'size': size, 'count': count,
                'type': tp, 'at': (block if stripe == 0 else temp) + offset}

    def string(self, pointer):
        if not pointer:
            return ''
        a = self.alloc[pointer - 1]
        raw = self.data[a['at']:a['at'] + a['size']]
        if not raw.endswith(b'\0'):
            raise ValueError('unterminated global string')
        return raw.rstrip(b'\0').decode('ascii')

    def size_of(self, name):
        if name in self.types:
            return self.types[name]['size']
        if name in SCALARS:
            return struct.calcsize('<' + SCALARS[name])
        array = re.fullmatch(r'(.+)\[(\d+)\]', name)
        if array:
            return self.size_of(array[1]) * int(array[2])
        raise ValueError('unknown type size: ' + name)

    def value(self, at, name):
        if name in SCALARS:
            return self.unpack(SCALARS[name], at)[0]
        if name.startswith('String::BasicT'):
            ptr, = self.unpack('Q', at)
            if not ptr:
                return ''
            a = self.alloc[ptr - 1]
            _, length = self.unpack('II', a['at'])
            if length + 8 > a['size']:
                raise ValueError('string exceeds allocation')
            return self.data[a['at'] + 8:a['at'] + 8 + length].decode('ascii')
        if name in ('String::Global', 'const char*'):
            return self.string(self.unpack('Q', at)[0])
        if name.startswith(('BLP::BLPVector<', 'Types::Vector<')):
            ptr, = self.unpack('Q', at)
            count, = self.unpack('I', at + 16)
            if not count:
                return []
            a = self.alloc[ptr - 1]
            if not ptr or count > a['count'] or a['size'] % a['count']:
                raise ValueError('invalid vector allocation')
            step = a['size'] // a['count']
            return [self.value(a['at'] + i * step, self.string(a['type'])) for i in range(count)]
        if name.startswith(('ptr64<', 'PackagePtr64<', 'Ptr64Support::Storage<')) or name.endswith('*'):
            return {'pointer': self.unpack('Q', at)[0]}
        array = re.fullmatch(r'(.+)\[(\d+)\]', name)
        if array:
            return [self.value(at + i * self.size_of(array[1]), array[1]) for i in range(int(array[2]))]
        if name not in self.types:
            raise ValueError('unknown reflected type: ' + name)
        return {field: self.value(at + offset, kind) for field, kind, offset in self.types[name]['fields']}

    def objects(self, name):
        return [self.value(a['at'] + i * self.size_of(name), name)
                for a in self.alloc if self.string(a['type']) == name for i in range(a['count'])]


def verify(blp, info):
    package = CookedPackage(blp)
    leaders = package.objects('LeaderPackageEntryV2')
    models = package.objects('Granny::PackageModel')
    model = next(m for m in models if m['m_ModelName'] == info['model'])
    bones = model['m_ModelSkeleton']['m_BoneNames']
    errors = []
    if bones != info['bones']:
        errors.append('cooked skeleton order differs from FGX')
    for leader in leaders:
        behavior = leader['behavior_desc']
        palette = behavior['m_MeshBindingBoneIDs']
        for field in ('m_RenderNodes', 'm_UnwrappedNodes', 'm_ShadowNodes'):
            nodes = leader[field]
            if not nodes:
                continue
            if len(nodes) != len(info['meshes']):
                errors.append(f'{field}: unexpected mesh count {len(nodes)}')
                continue
            for mesh, node in zip(info['meshes'], nodes):
                start, count = node['bone_transform_index'], node['bone_transform_count']
                actual = [bones[i] for i in palette[start:start + count]]
                if node['n_prims'] != mesh['tris'] or actual != mesh['bound']:
                    errors.append(f"{field}/{mesh['name']}: expected {mesh['bound']}, got {actual}")
    if not leaders:
        errors.append('no leader entry')
    if errors:
        raise ValueError('\n'.join(errors))
    print(f'bindings OK: {Path(blp).parents[2].name}, {len(info["meshes"])} meshes, '
          f'{sum(m["bound_bones"] for m in info["meshes"])} bone bindings')


def verify_current():
    """Read the current FGX through the SDK, then check both cooked platforms."""
    with tempfile.TemporaryDirectory(prefix='alexander-bindings-') as directory:
        info_path = Path(directory) / 'fgx.json'
        command = ['powershell', '-NoProfile', '-STA', '-ExecutionPolicy', 'Bypass', '-File',
                   str(ROOT / 'tools/fgx_info.ps1'), '-Fgx', str(ROOT / 'mod/Geometries/AlexanderII.fgx'),
                   '-Out', str(info_path)]
        subprocess.run(command, check=True)
        info = json.loads(info_path.read_text(encoding='utf-8-sig'))
        for platform in ('Windows', 'MacOS'):
            verify(ROOT / 'mod/Platforms' / platform / 'BLPs/leaders/leader_remsely_alexander_ii.blp', info)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--blp', type=Path, default=DEFAULT_BLP)
    parser.add_argument('--fgx-info', type=Path, default=ROOT / 'art/build/export/AlexanderII_fgx.json')
    args = parser.parse_args()
    try:
        verify(args.blp, json.loads(args.fgx_info.read_text(encoding='utf-8-sig')))
    except (ValueError, IndexError, KeyError, StopIteration, struct.error) as error:
        print('FAIL: cooked leader bindings:', error)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

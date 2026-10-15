"""Run the Blender-side checks in tools/blender/ in background Blender and print their result.

    python tools/blend.py audit art/3d/alexander_leader.blend [--scene Human] [--json out.json] [--full]
    python tools/blend.py audit --fbx art/3d/test/LEAD_REMSELY_TEST.fbx
    python tools/blend.py render art/3d/alexander_leader.blend [--scene Human] [--out shot.png] [--frame N] ...

Blender: env BLENDER or the default 4.5 install. Exit code 1 if the audit found errors.
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLENDER = os.environ.get('BLENDER', r'C:\Program Files\Blender Foundation\Blender 4.5\blender.exe')
SCRIPTS = {'audit': 'audit.py', 'render': 'render_leader.py'}


def run(cmd, rest):
    blend = None
    if rest and rest[0].lower().endswith('.blend'):
        blend, rest = rest[0], rest[1:]
    args = [BLENDER, '-b'] + ([blend] if blend else []) + [
        '--python-exit-code', '1', '--python', os.path.join(ROOT, 'tools', 'blender', SCRIPTS[cmd]), '--'] + rest
    p = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=ROOT)
    return p.returncode, p.stdout + p.stderr


def between(out, begin, end):
    if begin not in out or end not in out:
        return None
    return out.split(begin, 1)[1].split(end, 1)[0]


def audit_summary(rep):
    print('%s [%s] Blender %s, %d meshes, %d tris' % (rep['file'], rep['scene'], rep['blender'],
                                                     len(rep['meshes']), rep['tris_total']))
    if 'bbox' in rep:
        print('bbox size', rep['bbox']['size'], 'min', rep['bbox']['min'])
    for a in rep['armatures']:
        print('armature %s: %d bones (%d deform), action %s' % (a['object'], a['bones'], a['deform_bones'], a['action']))
    print('%-16s %7s %6s %4s %-24s %s' % ('mesh', 'tris', 'bones', 'uv', 'materials', 'influences'))
    for m in rep['meshes']:
        mats = ','.join(x or '-' for x in m['materials'])
        print('%-16s %7d %6s %4d %-24s %s%s' % (m['object'][:16], m['tris_evaluated'], m.get('bones_used', '-'),
                                               len(m['uv_layers']), mats[:24], m.get('influences_histogram', '-'),
                                               '  (hidden)' if m['hidden_render'] else ''))
    for i in rep['images']:
        print('image %-28s %dx%d%s' % (i['name'][:28], *i['size'], '  MISSING' if i['missing'] else ''))
    for e in rep['errors']:
        print('ERROR  ', e)
    for w in rep['warnings']:
        print('warning', w)
    print('%d errors, %d warnings' % (len(rep['errors']), len(rep['warnings'])))


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in SCRIPTS:
        sys.exit(__doc__)
    cmd, rest = sys.argv[1], sys.argv[2:]
    full = '--full' in rest
    rest = [a for a in rest if a != '--full']
    code, out = run(cmd, rest)
    if cmd == 'audit':
        body = between(out, 'AUDIT_BEGIN', 'AUDIT_END')
        if body is None:
            sys.exit(out)
        rep = json.loads(body)
        print(body) if full else audit_summary(rep)
        sys.exit(1 if rep['errors'] else 0)
    body = between(out, 'RENDER_BEGIN', 'RENDER_END')
    if body is None or code:
        sys.exit(out)
    print(body.strip())


if __name__ == '__main__':
    main()

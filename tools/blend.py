"""Run the Blender-side checks in tools/blender/ in background Blender and print their result.

    python tools/blend.py audit art/3d/alexander_leader.blend [--scene Human] [--json out.json] [--full]
    python tools/blend.py audit --fbx art/3d/test/LEAD_REMSELY_TEST.fbx
    python tools/blend.py render art/3d/alexander_leader.blend [--scene Human] [--out shot.png] [--frame N] ...
    python tools/blend.py render art/3d/alexander_leader.blend --scene Human --views full0,full45,full90,full180,head0,head45,head90
        (turntable views, plus <out stem>_sheet.png with all of them: one row of full views, one of head views;
         the view 'ref' also gives <out stem>_refcmp.png - the model over alexander_ii_full.png, outline in cyan)

    python tools/blend.py clash art/3d/alexander_leader.blend --scene Human [--motion test --frames 20,40,70]
        (pairs of meshes that run through each other: crossing triangles at rest and at the frames)
    render ... --motion idle|test --frames 1,40,80 - the views at frames of a motion (tools/blender/motion.py: the body
        keyed, the loose pieces swinging on their springs)

Blender: env BLENDER or the default 4.5 install. Exit code 1 if the audit found errors.
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLENDER = os.environ.get('BLENDER', r'C:\Program Files\Blender Foundation\Blender 4.5\blender.exe')
SCRIPTS = {'audit': 'audit.py', 'render': 'render_leader.py', 'clash': 'clash.py'}


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
    if cmd == 'clash':
        body = between(out, 'CLASH_BEGIN', 'CLASH_END')
        sys.exit(out if body is None or code else print(body.strip()))
    body = between(out, 'RENDER_BEGIN', 'RENDER_END')
    if body is None or code:
        sys.exit(out)
    lines = body.strip().splitlines()
    print('\n'.join(lines))
    shots = [l for l in lines if l.lower().endswith('.png')]
    for ref in [p for p in shots if p.endswith('_ref.png')]:
        print(overlay(ref))
    shots = [p for p in shots if not p.endswith('_ref.png')]
    if len(shots) > 1:
        print(sheet(shots))


def overlay(path):
    """The 'ref' view next to alexander_ii_full.png and over it (the model's outline in cyan): <stem>_refcmp.png."""
    from PIL import Image, ImageChops, ImageFilter
    ref = Image.open(os.path.join(ROOT, 'art', 'source', 'alexander_ii_full.png')).convert('RGB')
    raw = Image.open(path).resize(ref.size)
    if raw.mode == 'RGBA':  # rendered with --transparent: the alpha is the outline
        mask = raw.getchannel('A').point(lambda v: 255 if v > 127 else 0)
        shot = Image.new('RGB', ref.size, (40, 40, 46)); shot.paste(raw, (0, 0), raw)
    else:
        shot = raw.convert('RGB')
        bg = shot.getpixel((2, 2))
        mask = ImageChops.difference(shot, Image.new('RGB', shot.size, bg)).convert('L').point(lambda v: 255 if v > 6 else 0)
    edge = mask.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.MaxFilter(3))
    over = Image.blend(ref, shot, 0.5)
    over.paste(Image.new('RGB', ref.size, (0, 255, 255)), (0, 0), edge)
    ref_edge = ref.copy(); ref_edge.paste(Image.new('RGB', ref.size, (0, 255, 255)), (0, 0), edge)
    out = Image.new('RGB', (ref.width * 3, ref.height))
    for i, im in enumerate((ref_edge, shot, over)):
        out.paste(im, (i * ref.width, 0))
    dst = path[:-len('_ref.png')] + '_refcmp.png'
    out.save(dst)
    return dst


def sheet(paths):
    """All views on one picture: a row per kind (full, head), in the order given."""
    from PIL import Image
    rows = {}
    for p in paths:
        rows.setdefault(os.path.basename(p).rsplit('_', 1)[1][:4], []).append(Image.open(p))
    rows = list(rows.values())
    w = max(sum(i.width for i in r) for r in rows)
    out = Image.new('RGB', (w, sum(max(i.height for i in r) for r in rows)))
    y = 0
    for r in rows:
        x = 0
        for i in r:
            out.paste(i, (x, y)); x += i.width
        y += max(i.height for i in r)
    path = paths[0].rsplit('_', 1)[0] + '_sheet.png'
    out.save(path)
    return path


if __name__ == '__main__':
    main()

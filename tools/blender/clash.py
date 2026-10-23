# Which pieces of the leader run through each other: for every pair of rendered meshes, the number of their triangles
# that cross (BVH overlap of the deformed meshes), in the rest pose and at frames of a motion (tools/blender/motion.py).
# python tools/blend.py clash art/3d/alexander_leader.blend [--scene Human] [--motion test --frames 20,40,70]
# Pairs that are meant to touch (a button sewn on, the head's neck inside the collar) still show here when they
# cross: read the counts against the rest pose - a pair that grows in motion is the one to fix.
import bpy, os, sys, argparse
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser(prog='clash.py')
ap.add_argument('--scene')
ap.add_argument('--motion')
ap.add_argument('--frames', default='')
ap.add_argument('--min', type=int, default=1, help='report pairs with at least this many crossing triangles')
args = ap.parse_args(argv)

sc = bpy.data.scenes[args.scene] if args.scene else bpy.context.scene
if bpy.context.window:
    bpy.context.window.scene = sc
rig = next((o for o in sc.objects if o.type == 'ARMATURE'), None)
if args.motion and rig:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import motion
    motion.apply(sc, rig, args.motion)
meshes = [o for o in sc.objects if o.type == 'MESH' and not o.hide_render]


def trees():
    dg = bpy.context.evaluated_depsgraph_get()
    out = {}
    for o in meshes:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        me.transform(o.matrix_world)
        out[o.name] = BVHTree.FromPolygons([v.co.copy() for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
        ev.to_mesh_clear()
    return out


frames = [None] + [int(f) for f in args.frames.split(',') if f]
table = {}
for f in frames:
    if f is not None:
        sc.frame_set(f)
    t = trees()
    names = sorted(t)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            n = len(t[a].overlap(t[b]))
            if n:
                table.setdefault((a, b), {})[f] = n
print('CLASH_BEGIN')
cols = ['rest'] + ['f%d' % f for f in frames[1:]]
print('%-44s ' % 'pair' + ' '.join('%6s' % c for c in cols))
for (a, b), row in sorted(table.items(), key=lambda kv: -max(kv[1].values())):
    if max(row.values()) < args.min:
        continue
    print('%-44s ' % (a + ' x ' + b)[:44] + ' '.join('%6d' % row.get(f, 0) for f in frames))
print('CLASH_END')

# Stress test of the leader in motion: a motion from tools/blender/motion.py (the stress_* ones take one joint or a
# few to the ends of their range) played on the rig, and at its check frames (or --frames) what went wrong measured
# against the rest pose:
#   stretch - edges of a mesh longer / shorter than at rest (skin and cloth torn or pinched at a joint; a rigid piece -
#             buckle, sabre, epaulette, button - should not change at all);
#   flips   - triangles turned inside out (a joint folding through itself): its normal against the rest normal carried
#             by its own vertices' bones;
#   layers  - a piece that lay on another at rest (within LAYER_NEAR of it: a button on the tunic, the neck inside the
#             collar, a cuff over the wrist) crossed to its other side, or lifted off it / sunk into it; each vertex is
#             followed on the triangle of the other mesh it was nearest at rest;
#   clash   - pairs of meshes whose triangles cross, against the rest pose (meshes that came together from apart: an arm
#             through the side, the fringe through the sleeve). The tunic and the trousers count as separate meshes
#             here and in 'layers' (one object: their crossing would not show).
# python tools/blend.py stress art/3d/alexander_leader.blend --scene Human --motion stress_arm_l_side [--frames 13,21]
#        [--save baked.blend]   (the motion keyed and its loose pieces baked: render it with --frames, no --motion)
import bpy, os, sys, argparse
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

LAYER_NEAR = 0.015   # m: what lies this close to another mesh at rest is held to stay on its side of it
LAYER_EPS = 0.0005   # m: ... if it was this clearly on one side, and counts as through when this far on the other
LAYER_KEPT = 0.04    # m: ... while it stays this near the point it lay over (else they only came apart: a hand off the hilt)
LIFT = 0.008         # m: a piece this much further off than at rest has lifted off (or sunk into) what it lay on
STRETCH = (0.75, 1.30)  # edge length against rest, outside this: torn / pinched (skin and cloth) ...
STRETCH_MM = 0.004      # ... if longer / shorter by this much as well
RIGID = ('Buckle', 'Buttons', 'Orders', 'Spur_', 'Sole_', 'Eyes', 'CuffButtons_')
RIGID_STRETCH = 0.02  # ... a rigid piece's edges should not change by more than this share
FLIP_AREA = 1e-6        # m2: triangles smaller than this (a sliver in a crease) are not checked for turning over
SLIDE = ('Eyes', 'Eyelids')  # spheres turning in place under the skin: they slide by it, not followed in 'layers'

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser(prog='stress.py')
ap.add_argument('--scene')
ap.add_argument('--motion', required=True)
ap.add_argument('--frames', default='')
ap.add_argument('--save')
ap.add_argument('--top', type=int, default=4, help='worst places shown per finding')
args = ap.parse_args(argv)

sc = bpy.data.scenes[args.scene] if args.scene else bpy.context.scene
if bpy.context.window:
    bpy.context.window.scene = sc
rig = next(o for o in sc.objects if o.type == 'ARMATURE')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import motion  # noqa: E402

meshes = [o for o in sc.objects if o.type == 'MESH' and not o.hide_render]


def state():
    """name -> (world vertices, triangles); the uniform split into its layers."""
    dg = bpy.context.evaluated_depsgraph_get()
    out = {}
    for o in meshes:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        me.calc_loop_triangles()
        co = np.zeros(len(me.vertices) * 3); me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3) @ np.array(ev.matrix_world)[:3, :3].T + np.array(ev.matrix_world)[:3, 3]
        tri = np.zeros(len(me.loop_triangles) * 3, np.int32); me.loop_triangles.foreach_get('vertices', tri)
        tri = tri.reshape(-1, 3)
        out[o.name] = (co, tri)
        ev.to_mesh_clear()
    return out


def layers_of(name, co, tri, part):
    """The object's triangles split into the layers it stands for: the uniform's tunic ('part' 0) and trousers."""
    if name != 'Uniform' or part is None:
        return {name: tri}
    tunic = part[TRI_POLY[name]] == 0
    return {'Uniform.tunic': tri[tunic], 'Uniform.trousers': tri[~tunic]}


def bvh(co, tri):
    return BVHTree.FromPolygons([Vector(c) for c in co], tri.tolist(), all_triangles=True)


def tri_normals(co, tri):
    n = np.cross(co[tri[:, 1]] - co[tri[:, 0]], co[tri[:, 2]] - co[tri[:, 0]])
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)


def bone_of(o, idx):
    names = [g.name for g in o.vertex_groups]
    best, w = '-', 0
    for g in o.data.vertices[int(idx)].groups:
        if g.weight > w:
            best, w = names[g.group], g.weight
    return best


def where(p):
    return '(%.3f, %.3f, %.3f)' % tuple(p)


# ---------------------------------------------------------------- the rest pose
for pb in rig.pose.bones:
    pb.matrix_basis.identity()
rig.animation_data_clear()
bpy.context.view_layer.update()
REST = state()
TRI_POLY = {}
PART = {}
for o in meshes:
    me = o.data
    me.calc_loop_triangles()
    tp = np.zeros(len(me.loop_triangles), np.int32); me.loop_triangles.foreach_get('polygon_index', tp)
    TRI_POLY[o.name] = tp
    if 'part' in me.attributes:
        pa = np.zeros(len(me.polygons), np.int32); me.attributes['part'].data.foreach_get('value', pa)
        PART[o.name] = pa
EDGES = {}
for o in meshes:
    e = np.zeros(len(o.data.edges) * 2, np.int32); o.data.edges.foreach_get('vertices', e)
    e = e.reshape(-1, 2)
    co = REST[o.name][0]
    l0 = np.linalg.norm(co[e[:, 0]] - co[e[:, 1]], axis=1)
    EDGES[o.name] = (e[l0 > 1e-5], l0[l0 > 1e-5])  # not the zero-length ones (welded seams)
# per vertex: its weights as (bone index, weight) arrays, for the rest normals carried along (flips)
BONES = [b.name for b in rig.data.bones]
WEIGHTS = {}
for o in meshes:
    names = [g.name for g in o.vertex_groups]
    bi = np.zeros((len(o.data.vertices), 8), np.int32); bw = np.zeros((len(o.data.vertices), 8))
    for v in o.data.vertices:
        gs = sorted(((g.weight, names[g.group]) for g in v.groups if names[g.group] in BONES and g.weight > 0),
                    reverse=True)[:8]
        tot = sum(w for w, _ in gs) or 1.0
        for k, (w, n) in enumerate(gs):
            bi[v.index, k] = BONES.index(n); bw[v.index, k] = w / tot
    WEIGHTS[o.name] = (bi, bw)

# layer pairs: every vertex of a mesh near another mesh, held on its nearest triangle there
LAYERS = {}
for o in meshes:
    co, tri = REST[o.name]
    for lname, ltri in layers_of(o.name, co, tri, PART.get(o.name)).items():
        LAYERS.setdefault(o.name, {})[lname] = ltri
pairs = []
for a in meshes:
    if a.name in SLIDE:
        continue
    aco = REST[a.name][0]
    for b in meshes:
        bco = REST[b.name][0]
        for lb, ltri in LAYERS[b.name].items():
            if not len(ltri) or b.name in SLIDE:
                continue
            if a is b:
                # within the uniform: only one layer's vertices over another
                if a.name != 'Uniform':
                    continue
            lo, hi = bco[ltri.ravel()].min(0) - LAYER_NEAR, bco[ltri.ravel()].max(0) + LAYER_NEAR
            cand = np.where(np.all((aco > lo) & (aco < hi), axis=1))[0]
            if a is b:
                own = np.zeros(len(aco), bool); own[ltri.ravel()] = True
                cand = cand[~own[cand]]
            if not len(cand):
                continue
            t = bvh(bco, ltri)
            nrm = tri_normals(bco, ltri)
            idx, ti, hp = [], [], []
            for i in cand:
                hit = t.find_nearest(Vector(aco[i]), LAYER_NEAR)
                if hit[0] is not None:
                    idx.append(i); ti.append(hit[2]); hp.append(hit[0])
            if not idx:
                continue
            idx, ti, hp = np.array(idx), np.array(ti), np.array(hp)
            tv = bco[ltri[ti]]  # barycentric of the nearest points
            v0, v1, v2 = tv[:, 1] - tv[:, 0], tv[:, 2] - tv[:, 0], hp - tv[:, 0]
            d00, d01, d11 = (v0 * v0).sum(1), (v0 * v1).sum(1), (v1 * v1).sum(1)
            d20, d21 = (v2 * v0).sum(1), (v2 * v1).sum(1)
            den = d00 * d11 - d01 * d01
            den[np.abs(den) < 1e-18] = 1e-18
            bv, bw_ = (d11 * d20 - d01 * d21) / den, (d00 * d21 - d01 * d20) / den
            bary = np.c_[1 - bv - bw_, bv, bw_]
            d0 = ((aco[idx] - hp) * nrm[ti]).sum(1)
            keep = np.abs(d0) > LAYER_EPS
            for la, sel in ((a.name, keep),) if a.name != 'Uniform' else (
                    (n, keep & np.isin(idx, tr.ravel())) for n, tr in LAYERS['Uniform'].items() if n != lb):
                if sel.any():
                    pairs.append(dict(a=a.name, la=la, b=b.name, lb=lb, idx=idx[sel], tri=ltri[ti[sel]],
                                      bary=bary[sel], d0=d0[sel]))
print('layer pairs: %d (%d vertices)' % (len(pairs), sum(len(p['idx']) for p in pairs)))


def rest_clash(st):
    trees = {}
    for o in meshes:
        co, tri = st[o.name]
        for ln, lt in layers_of(o.name, co, tri, PART.get(o.name)).items():
            if len(lt):
                trees[ln] = bvh(co, lt)
    names = sorted(trees)
    out = {}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            n = len(trees[a].overlap(trees[b]))
            if n:
                out[(a, b)] = n
    return out


CLASH0 = rest_clash(REST)

# ---------------------------------------------------------------- the motion
last = motion.apply(sc, rig, args.motion)
m = motion.MOTIONS[args.motion]
frames = [int(f) for f in args.frames.split(',') if f] or m.get('check') or list(range(1, last + 1, 10))
if args.save:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args.save), copy=True, compress=True)
    print('saved', args.save)

mats_rest = {b.name: np.array(b.matrix_local) for b in rig.data.bones}
summary = {}


def note(kind, key, val, text):
    """Keeps the worst of each finding over the frames."""
    k = (kind, key)
    if k not in summary or val > summary[k][0]:
        summary[k] = (val, text)


print('STRESS_BEGIN')
print('motion %s, %d frames, checked at %s; the poses reached at %s' % (
    args.motion, last, ','.join(map(str, frames)), ','.join(map(str, m.get('arrive', [])))))
for f in frames:
    sc.frame_set(f)
    st = state()
    # bone matrices: rest -> posed (armature space)
    skin = np.array([np.array(rig.pose.bones[n].matrix) @ np.linalg.inv(mats_rest[n]) for n in BONES])
    lines = []
    for o in meshes:
        co, tri = st[o.name]
        e, l0 = EDGES[o.name]
        if len(e):
            l1 = np.linalg.norm(co[e[:, 0]] - co[e[:, 1]], axis=1)
            r = l1 / l0
            rigid = o.name.startswith(RIGID)
            lo, hi = (1 - RIGID_STRETCH, 1 + RIGID_STRETCH) if rigid else STRETCH
            # by a share and (but for a rigid piece) by a length that shows: a crease's 2 mm edge opening to 6 is none
            bad = np.where(((r < lo) | (r > hi)) & (rigid | (np.abs(l1 - l0) > STRETCH_MM)))[0]
            if len(bad):
                worst = bad[np.argsort(-np.abs(np.log(r[bad])))][:args.top]
                txt = '%s: %d edges stretched %.2f..%.2f, worst at %s' % (
                    o.name, len(bad), r.min(), r.max(),
                    '; '.join('%s x%.2f %s' % (where(co[e[i, 0]]), r[i], bone_of(o, e[i, 0])) for i in worst))
                lines.append('  stretch ' + txt)
                note('stretch', o.name, float(np.abs(np.log(r[bad])).max()), 'f%d %s' % (f, txt))
        # flips: the rest normal carried by the triangle's own vertices' skinning
        rco, _ = REST[o.name]
        bi, bw = WEIGHTS[o.name]
        if len(tri) and bw.any():
            n0 = tri_normals(rco, tri)
            M = np.einsum('vk,vkij->vij', bw, skin[bi])[:, :3, :3]   # per vertex, the blended 3x3
            Mt = M[tri].mean(1)
            carried = np.einsum('tij,tj->ti', Mt, n0)
            n1 = tri_normals(co, tri)
            dot = np.einsum('ti,ti->t', carried, n1) / np.maximum(np.linalg.norm(carried, axis=1), 1e-12)
            area = np.linalg.norm(np.cross(co[tri[:, 1]] - co[tri[:, 0]], co[tri[:, 2]] - co[tri[:, 0]]), axis=1) / 2
            flip = np.where((dot < -0.2) & (area > FLIP_AREA))[0]  # (a sliver's normal is noise)
            if len(flip):
                c = co[tri[flip]].mean(1)
                txt = '%s: %d triangles inside out, at %s' % (o.name, len(flip), '; '.join(
                    '%s %s' % (where(c[i]), bone_of(o, tri[flip[i], 0])) for i in range(min(args.top, len(flip)))))
                lines.append('  flips   ' + txt)
                note('flips', o.name, float(len(flip)), 'f%d %s' % (f, txt))
    for p in pairs:
        aco = st[p['a']][0]
        bco = st[p['b']][0]
        tv = bco[p['tri']]
        pt = np.einsum('tk,tki->ti', p['bary'], tv)
        nrm = tri_normals(bco, p['tri'])
        d1 = np.einsum('ti,ti->t', aco[p['idx']] - pt, nrm)
        d0 = p['d0']
        # still by the point it lay over (a hand taken off the hilt is not through it)
        near = np.linalg.norm(aco[p['idx']] - pt, axis=1) < LAYER_KEPT
        through = np.where(near & (np.sign(d0) != np.sign(d1)) & (np.abs(d1) > LAYER_EPS))[0]
        # lifted off (further from it on its own side) - only of what touched it (within 3 mm at rest)
        touch = np.abs(d0) < 0.003
        lift = np.where(near & touch & (np.sign(d0) == np.sign(d1)) & (np.abs(d1) - np.abs(d0) > LIFT))[0]
        key = '%s over %s' % (p['la'], p['lb'])
        if len(through):
            depth = np.abs(d1[through])
            w = through[np.argsort(-depth)][:args.top]
            txt = '%s: %d verts through (deepest %.1f mm) at %s' % (key, len(through), depth.max() * 1000, '; '.join(
                '%s %s' % (where(aco[p['idx'][i]]), bone_of(bpy.data.objects[p['a']], p['idx'][i])) for i in w))
            lines.append('  through ' + txt)
            note('through', key, float(depth.max()) * len(through) ** 0.5, 'f%d %s' % (f, txt))
        if len(lift):
            gap = np.abs(d1[lift]) - np.abs(d0[lift])
            w = lift[np.argsort(-gap)][:args.top]
            txt = '%s: %d verts lifted off (most %.1f mm) at %s' % (key, len(lift), gap.max() * 1000, '; '.join(
                '%s %s' % (where(aco[p['idx'][i]]), bone_of(bpy.data.objects[p['a']], p['idx'][i])) for i in w))
            lines.append('  lifted  ' + txt)
            note('lifted', key, float(gap.max()), 'f%d %s' % (f, txt))
    cl = rest_clash(st)
    for k, n in sorted(cl.items(), key=lambda kv: -kv[1]):
        n0 = CLASH0.get(k, 0)
        if n > n0 * 1.3 + 8:
            txt = '%s x %s: %d crossing triangles (rest %d)' % (k[0], k[1], n, n0)
            lines.append('  clash   ' + txt)
            note('clash', k, float(n - n0), 'f%d %s' % (f, txt))
    print('frame %d: %s' % (f, 'clean' if not lines else ''))
    for ln in lines:
        print(ln)
print('WORST')
for (kind, key), (val, txt) in sorted(summary.items(), key=lambda kv: (kv[0][0], -kv[1][0])):
    print('  %-8s %s' % (kind, txt))
print('STRESS_END')

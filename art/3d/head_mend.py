# The head's shape mended in place, its UVs and the rest of its mesh untouched (build_head.py is not repeatable, so the
# head is never rebuilt):
#   blender -b art/3d/alexander_rest.blend --python art/3d/head_mend.py            (both blends, once)
#   blender -b art/3d/alexander_rest.blend --python art/3d/head_mend.py -- DIR    (both so changed, saved in DIR)
# 1. his left upper lid's fold lowered: the generation set his left eyeball 3.3 mm lower than his right one under a
#    brow as high, so the lid showed 10.5 mm tall between the lash line and the fold under the brow (the portrait's:
#    ~5 mm, a crease and over it a sunk band up to the brow; his right one's is under its brow's overhang): it read as
#    swollen. The skin over the lid lowered: the fold FOLD_DROP lower, fading out up to the brow (its foot ~3 mm lower;
#    brought out to the overhang instead, a box on the lid; the lid's upper part sunk in, no change seen); the
#    opening stays.
# 2. the lower lip pushed back LIP_BACK (it stood 5.5 mm out of the groove under it, a roll under the moustache: the
#    portrait's lip is a narrow band under the moustache's ends), the upper lip in the moustache's gap UPPER_LIP.
# 3. faces folded over their neighbours (the decimation's slivers: by the hair's edge on his right temple, under his
#    left ear by the beard, on the ears' rims - spikes, white and dark flecks in the light) relaxed flat;
# 4. ... and the spiky patches there smoothed; on the leader also the faces its pose folded (under his left jaw);
# 6. faces through each other (where the ears and the beard's back ends were joined on) parted.
# alexander_leader.blend's head is the portrait's pose: per vertex the same move turned as the head there is round it
# (a fit over each moved part). After it, head_touchup.py again (its masks are by the surface's place).
import bpy, math, os, sys
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

HERE = os.path.dirname(os.path.abspath(__file__))
REST = os.path.join(HERE, 'alexander_rest.blend')
LEADER = os.path.join(HERE, 'alexander_leader.blend')
MARK = 'head_mended'              # the Head object's property once done
FOLD_X = np.arange(-26.0, 26.1, 0.5)  # mm across his left eye (out from the nose) the fold is found at
FOLD_Z = (9.0, 25.0)              # ... between these mm over the ball's middle: where the face steps out most steeply
FOLD_DROP = 5.0                   # mm: the fold this much lower at the lid's middle ...
FOLD_EDGE = (14.0, 24.0)          # ... fading out between these mm across, past the corners (inside them, a sag)
DROP_FROM = 1.5                   # mm over the opening's top: the lid moves from here (the lash line stays) ...
DROP_UP = 12.0                    # ... up to the fold, then less, none this far over it (the brow: down 3 mm at its foot)
DROP_LINING = (1.5, 3.5)          # mm off the eyeball: nothing nearer (the socket's lining), all from the second
DROP_SMOOTH = 6                   # mesh rounds the move is averaged over (per vertex, its edge came out in teeth)
LIP = ((1.864, 1.871), (1.883, 1.888), (9.0, 19.0))  # the lower lip: z fading in, z fading out, mm off the middle
LIP_BACK = 3.0                    # mm back (+y), all of it where the lip stands out most
UPPER_LIP = ((1.881, 1.886), (1.892, 1.898), (5.0, 11.0), 2.0)  # the upper lip between the moustache's halves: z in, z
                                  # out, mm off the middle, mm back (it stood out of the gap, a pink knob)
FOLD_DEG = 120.0                  # faces folded over a neighbour by more than this ...
FOLD_EYE = 0.019                  # ... not this near an eyeball's middle (the sockets' linings, out of sight)
RELAX_ROUNDS = 40                 # ... their vertices and their neighbours moved to their neighbours' middle, at most
                                  # this many rounds
RELAX_MAX = 0.006                 # m: no vertex further than this
ZONES = [((0.079, -0.033, 1.871), 0.020),   # 4. spiky patches (folds of 60-125 deg, thorns in the light) smoothed
         ((-0.081, -0.063, 1.972), 0.022),  # without shrinking (Taubin): under his left ear by the beard, his right
         ((-0.089, 0.002, 1.902), 0.009),   # temple by the hair's edge, under his right ear, the back of his left
         ((0.101, 0.015, 1.945), 0.010),    # ear's rim; (centre, radius - all of it inside half of it)
         ((0.105, 0.022, 1.985), 0.008)]
ZONE_ROUNDS = 12
TAUBIN = (0.5, -0.53)
UNFOLD = (90.0, 0.0015, 6)        # faces still folded over a neighbour by more than this (micro slivers, 0.7-1.4 mm
                                  # edges: smoothing does not turn them out): each vertex moved along the surface, at
                                  # most this far, as little as turns its faces out; this many passes
CROSS = (0.0004, 8)               # 6. faces of the mesh through each other (where the ears and the beard's back ends were
                                  # joined on: tips of the hidden layer through the skin - the thorns and white flecks
                                  # by the ears and under the jaw): the hidden layer's vertices put this far behind the
                                  # one seen from outside; this many passes
NECK_CUT = 1.73                   # z: under it the neck's cut edge (in the collar) is never moved
REWEIGHT = 0.0005                 # m: vertices moved more than this take the skin weights of where they are now
POSE_FOLD = (100.0, 0.009)        # the leader: faces the pose folded over a neighbour by more than this (not so at
                                  # rest; under his left jaw, turned to the camera, the skin by the beard crumpled into
                                  # thorns), smoothed within this of them


def smoothstep(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def eyes():
    """The eyeballs' middles (his left: +x) and radius."""
    ob = bpy.data.objects['Eyes']
    ec = np.array([ob.matrix_world @ v.co for v in ob.data.vertices])
    out = {}
    for s, m in (('l', ec[:, 0] > ec[:, 0].mean()), ('r', ec[:, 0] <= ec[:, 0].mean())):
        e = ec[m]
        out[s] = (e.min(0) + e.max(0)) / 2
    return out, float((e.max(0) - e.min(0)).max() / 2)


def head_co(ob):
    return np.array([ob.matrix_world @ v.co for v in ob.data.vertices])


def set_co(ob, co):
    inv = np.array(ob.matrix_world.inverted())
    loc = co @ inv[:3, :3].T + inv[:3, 3]
    ob.data.vertices.foreach_set('co', loc.astype(np.float32).ravel())
    ob.data.update()


def depth(tree, x, z):
    """The face's y seen from the front at (x, z) (nan: nothing there)."""
    hit = tree.ray_cast(Vector((x, -0.5, z)), Vector((0, 1, 0)), 1.0)
    return hit[0].y if hit[0] is not None else np.nan


def neighbours(me):
    nb = [[] for _ in me.vertices]
    for a, b in (e.vertices for e in me.edges):
        nb[a].append(b); nb[b].append(a)
    return nb


def opening(tree, c, R):
    """Over each FOLD_X, seen from the front: the top of the eyeball's bare span (mm over its middle; under the
    middle where it is shut)."""
    top = []
    for dx in FOLD_X:
        bare = [dz for dz in np.arange(-10.0, 12.0, 0.25)
                if R * R - (dx / 1000) ** 2 - (dz / 1000) ** 2 > 0
                and not depth(tree, c[0] + dx / 1000, c[2] + dz / 1000) - c[1]
                < -math.sqrt(R * R - (dx / 1000) ** 2 - (dz / 1000) ** 2)]
        top.append(max(bare) if bare else 0.0)
    return np.array(top), None


def lowered(co, polys, nb):
    """1. -> vertices with the skin over his left upper lid lowered: the fold FOLD_DROP lower, what is over it less
    so up to the brow, the lid under it pressed into what is left (its lash line stays)."""
    E, R = eyes()
    c = E['l']
    tree = BVHTree.FromPolygons([Vector(p) for p in co], polys)
    zs = np.arange(FOLD_Z[0], FOLD_Z[1] + 0.01, 0.25)
    fold = []
    for dx in FOLD_X:
        d = np.array([depth(tree, c[0] + dx / 1000, c[2] + z / 1000) for z in zs]) - c[1]
        step = -np.gradient(np.nan_to_num(d, nan=0.0)) / 0.25  # how steeply the face comes out going up
        fold.append(zs[int(np.argmax(step))])
    k = np.exp(-0.5 * (np.arange(-6, 7) * 0.5 / 1.5) ** 2)
    fold = np.convolve(np.pad(np.array(fold), 6, mode='edge'), k / k.sum(), 'valid')
    drop = FOLD_DROP * (1 - smoothstep(np.abs(FOLD_X), *FOLD_EDGE))
    for x, f, d in list(zip(FOLD_X, fold, drop))[::6]:
        print('  %+5.1f mm: fold %.1f mm over the middle -> crease at %.1f' % (x, f, f - d))
    lo, _ = opening(tree, c, R)
    q = co - c
    dx, dz = q[:, 0] * 1000, q[:, 2] * 1000
    f, dr = np.interp(dx, FOLD_X, fold), np.interp(dx, FOLD_X, drop, left=0, right=0)
    a = np.interp(dx, FOLD_X, lo) + DROP_FROM  # the lid's lash line and what is under it stay
    off = (np.linalg.norm(q, axis=1) - R) * 1000  # mm off the eyeball: the lid's lining in the socket stays (seen
    g = (smoothstep(dz, a, f) * (1 - smoothstep(dz, f, f + DROP_UP)) * (q[:, 1] < 0)  # from the front only, the
         * smoothstep(off, *DROP_LINING))                                             # fold's underside stayed: a slot)
    dzv = -dr / 1000 * g
    keep = g > 0
    for _ in range(DROP_SMOOTH):  # averaged with the neighbours, on the face only
        dzv = np.array([dzv[v] if not nb[v] else (dzv[v] + dzv[nb[v]].sum()) / (len(nb[v]) + 1) for v in range(len(dzv))])
        dzv *= keep
    out = co.copy()
    out[:, 2] += dzv
    gap = np.linalg.norm(out - c, axis=1)[keep].min() - R
    print('  lid: %d vertices down, at most %.1f mm; nearest the eyeball %.1f mm off it' % (
        int((dzv < -1e-6).sum()), -dzv.min() * 1000, gap * 1000))
    return out


def lip_back(co):
    """2. -> vertices with the lower lip pushed back."""
    E, _ = eyes()
    mid = (E['l'][0] + E['r'][0]) / 2
    (z0, z1), (z2, z3), (x0, x1) = LIP
    w = (smoothstep(co[:, 2], z0, z1) * (1 - smoothstep(co[:, 2], z2, z3))
         * (1 - smoothstep(np.abs(co[:, 0] - mid) * 1000, x0, x1)) * (co[:, 1] < -0.12))
    (u0, u1), (u2, u3), (v0, v1), ub = UPPER_LIP
    wu = (smoothstep(co[:, 2], u0, u1) * (1 - smoothstep(co[:, 2], u2, u3))
          * (1 - smoothstep(np.abs(co[:, 0] - mid) * 1000, v0, v1)) * (co[:, 1] < -0.12))
    out = co.copy()
    out[:, 1] += LIP_BACK / 1000 * w + ub / 1000 * wu * (1 - w)
    return out


def folded_faces(co, pv, pairs, keep_near):
    tri = co[np.array([p[:3] for p in pv])]
    fn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    ok = np.linalg.norm(fn, axis=1) > 1e-14
    fn = fn / np.maximum(np.linalg.norm(fn, axis=1), 1e-30)[:, None]
    lim = math.cos(math.radians(FOLD_DEG))
    bad = set()
    for g, h in pairs:
        if ok[g] and ok[h] and fn[g] @ fn[h] < lim:
            bad.update((g, h))
    return {f for f in bad if not keep_near[f]}


def relaxed(co, me):
    """3. -> vertices with the faces folded over a neighbour relaxed flat."""
    E, _ = eyes()
    pv = [tuple(p.vertices) for p in me.polygons]
    faces = {}
    for i, p in enumerate(me.polygons):
        for k in p.edge_keys:
            faces.setdefault(k, []).append(i)
    pairs = [tuple(fs) for fs in faces.values() if len(fs) == 2]
    nb = neighbours(me)
    centre = np.array([co[list(p)].mean(0) for p in pv])
    keep_near = np.min([np.linalg.norm(centre - e, axis=1) for e in E.values()], 0) < FOLD_EYE
    start = co.copy()
    out = co.copy()
    bad = folded_faces(out, pv, pairs, keep_near)
    print('  folded faces: %d' % len(bad))
    for r in range(RELAX_ROUNDS):
        if not bad:
            break
        vs = {v for f in bad for v in pv[f]}
        vs = sorted(vs | {u for v in vs for u in nb[v]})
        for v in vs:
            out[v] = out[nb[v]].mean(0)
        d = out - start
        n = np.linalg.norm(d, axis=1)
        out = start + d * np.minimum(1, RELAX_MAX / np.maximum(n, 1e-12))[:, None]
        bad = folded_faces(out, pv, pairs, keep_near)
    print('  folded faces left: %d after %d rounds' % (len(bad), r + 1))
    cen = np.array([out[list(pv[f])].mean(0) for f in bad])
    while len(cen):
        k = np.linalg.norm(cen - cen[0], axis=1) < 0.008
        print('    %d at %s' % (int(k.sum()), np.round(cen[k].mean(0), 3)))
        cen = cen[~k]
    return out


def smoothed(co, nb):
    """4. -> vertices with the spiky patches smoothed (Taubin: each round a step to the neighbours' middle and one
    back, so the patch does not shrink)."""
    w = np.zeros(len(co))
    for c, r in ZONES:
        w = np.maximum(w, 1 - smoothstep(np.linalg.norm(co - np.array(c), axis=1), r / 2, r))
    idx = np.nonzero(w)[0]
    out = co.copy()
    for _ in range(ZONE_ROUNDS):
        for lam in TAUBIN:
            mean = np.array([out[nb[v]].mean(0) for v in idx])
            out[idx] += (mean - out[idx]) * (lam * w[idx])[:, None]
    print('  %d vertices in %d patches, at most %.2f mm' % (len(idx), len(ZONES), np.linalg.norm(out - co, axis=1).max() * 1000))
    return out


def topology(me):
    pv = [tuple(p.vertices) for p in me.polygons]
    faces = {}
    for i, p in enumerate(me.polygons):
        for k in p.edge_keys:
            faces.setdefault(k, []).append(i)
    pairs = [tuple(fs) for fs in faces.values() if len(fs) == 2]
    vf = [[] for _ in me.vertices]
    for i, q in enumerate(pv):
        for v in q:
            vf[v].append(i)
    fnb = [[] for _ in pv]
    for g, h in pairs:
        fnb[g].append(h); fnb[h].append(g)
    return pv, pairs, vf, fnb


def face_normals(pv, co):
    tri = co[np.array([q[:3] for q in pv])]
    fn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    return fn / np.maximum(np.linalg.norm(fn, axis=1), 1e-30)[:, None]


def unfolded(co, me, skip=None):
    """-> vertices with the faces still folded over a neighbour (not in skip) turned out: each of their vertices moved
    along the surface (at most UNFOLD[1]) as little as turns its faces out."""
    pv, pairs, vf, fnb = topology(me)
    lim = math.cos(math.radians(UNFOLD[0]))
    skip = skip if skip is not None else np.zeros(len(pv), bool)
    co = co.copy()

    def folded():
        fn = face_normals(pv, co)
        return {f for g, h in pairs if fn[g] @ fn[h] < lim for f in (g, h) if not skip[f]}
    bad = folded()
    n0 = len(bad)
    steps = np.linspace(-UNFOLD[1], UNFOLD[1], 13)
    cand = sorted(((a, b) for a in steps for b in steps if a * a + b * b <= UNFOLD[1] ** 2),
                  key=lambda ab: ab[0] ** 2 + ab[1] ** 2)
    for _ in range(UNFOLD[2]):
        if not bad:
            break
        for v in sorted({v for f in bad for v in pv[f]}):
            local = sorted({g for f in vf[v] for g in fnb[f]} | set(vf[v]))
            idx = {f: i for i, f in enumerate(local)}
            fl = face_normals([pv[f] for f in local], co)
            n = fl.sum(0); n /= max(np.linalg.norm(n), 1e-12)
            u = np.cross(n, [1.0, 0, 0] if abs(n[0]) < 0.9 else [0, 1.0, 0]); u /= np.linalg.norm(u)
            w = np.cross(n, u)
            best = None
            for a_, b_ in cand:
                c2 = co.copy(); c2[v] = co[v] + u * a_ + w * b_
                f2 = face_normals([pv[f] for f in local], c2)
                worst = min(f2[idx[f]] @ f2[idx[g]] for f in vf[v] for g in fnb[f] if g in idx)
                if best is None or worst > best[0] + 1e-9:
                    best = (worst, u * a_ + w * b_)
                if worst > 0.5:
                    break
            co[v] = co[v] + best[1]
        bad = folded()
    print('  folded faces turned out: %d -> %d' % (n0, len(bad)))
    return co


def uncrossed(co, me):
    """6. -> vertices with no face through another: of each crossing pair the one not seen from outside (a ray back
    from out along its normal meets something else first) has its vertices put behind the other."""
    pv = [tuple(p.vertices) for p in me.polygons]
    ring = [set() for _ in pv]
    vf = [[] for _ in me.vertices]
    for i, q in enumerate(pv):
        for v in q:
            vf[v].append(i)
    for i, q in enumerate(pv):
        ring[i] = {g for v in q for g in vf[v]}
    co = co.copy()
    n0 = None
    for _ in range(CROSS[1]):
        vs = [Vector(p) for p in co]
        bvh = BVHTree.FromPolygons(vs, pv)
        pairs = [(a, b) for a, b in bvh.overlap(bvh) if a < b and not set(pv[a]) & set(pv[b])]
        if n0 is None:
            n0 = len(pairs)
        if not pairs:
            break
        fn = face_normals(pv, co)
        cen = np.array([co[list(q)].mean(0) for q in pv])
        outer, inner = set(), set()
        for f in {f for pr in pairs for f in pr}:
            hit = bvh.ray_cast(Vector(cen[f] + fn[f] * 0.02), Vector(-fn[f]), 0.03)
            (outer if hit[2] in ring[f] else inner).add(f)
        if not outer or not inner:
            break
        ol = sorted(outer)
        ob = BVHTree.FromPolygons(vs, [pv[f] for f in ol])
        for v in sorted({v for f in inner for v in pv[f]}):
            loc, nrm, k, d = ob.find_nearest(Vector(co[v]), 0.01)
            if loc is None:
                continue
            n = fn[ol[k]]
            if (co[v] - np.array(loc)) @ n > -CROSS[0]:
                co[v] = np.array(loc) - n * CROSS[0]
    vs = [Vector(p) for p in co]
    bvh = BVHTree.FromPolygons(vs, pv)
    left = [(a, b) for a, b in bvh.overlap(bvh) if a < b and not set(pv[a]) & set(pv[b])]
    print('  faces through each other: %d pairs -> %d' % (n0, len(left)))
    return co


def pose_folds(head, rest):
    """5. (the leader) -> how many faces the pose folded were smoothed out, and how many are left."""
    me = head.data
    pv = [tuple(p.vertices) for p in me.polygons]
    faces = {}
    for i, p in enumerate(me.polygons):
        for k in p.edge_keys:
            faces.setdefault(k, []).append(i)
    pairs = [tuple(fs) for fs in faces.values() if len(fs) == 2]
    nb = neighbours(me)
    E, _ = eyes()
    lim = math.cos(math.radians(POSE_FOLD[0]))

    def bad(co):
        tri = co[np.array([q[:3] for q in pv])]
        fn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        fn = fn / np.maximum(np.linalg.norm(fn, axis=1), 1e-30)[:, None]
        return {f for g, h in pairs if fn[g] @ fn[h] < lim for f in (g, h)}
    co = head_co(head)
    centre = np.array([co[list(q)].mean(0) for q in pv])
    near_eye = np.min([np.linalg.norm(centre - e, axis=1) for e in E.values()], 0) < FOLD_EYE
    at_rest = bad(rest)
    keep = near_eye | (centre[:, 2] < NECK_CUT)  # (the neck's cut edge, in the collar: smoothed, it moved 15 mm)
    found = {f for f in bad(co) - at_rest if not keep[f]}
    if not found:
        return 0, 0
    w = np.zeros(len(co))
    for f in found:
        w = np.maximum(w, 1 - smoothstep(np.linalg.norm(co - centre[f], axis=1), POSE_FOLD[1] / 2, POSE_FOLD[1]))
    idx = np.nonzero(w)[0]
    for _ in range(ZONE_ROUNDS):
        for lam in TAUBIN:
            mean = np.array([co[nb[v]].mean(0) for v in idx])
            co[idx] += (mean - co[idx]) * (lam * w[idx])[:, None]
    set_co(head, co)
    left = {f for f in bad(co) - at_rest if not keep[f]}
    return len(found), len(left)


def reweighted(ob, old, new):
    """The skin weights of each vertex moved more than REWEIGHT: those of the old surface where it is now (the
    nearest point of it, its face's corners' weights by where the point lies in it). Moved by the mending with its
    own, a vertex now among others went with other bones: turning the head, under the ears the skin flipped."""
    me = ob.data
    names = [g.name for g in ob.vertex_groups]
    W = np.zeros((len(me.vertices), len(names)), np.float32)
    for v in me.vertices:
        for g in v.groups:
            W[v.index, g.group] = g.weight
    moved = np.nonzero(np.linalg.norm(new - old, axis=1) > REWEIGHT)[0]
    tris = [tuple(p.vertices[:3]) for p in me.polygons]
    tree = BVHTree.FromPolygons([Vector(p) for p in old], tris)
    from mathutils.interpolate import poly_3d_calc
    W2 = W.copy()
    for i in moved:
        loc, _, f, _ = tree.find_nearest(Vector(new[i]))
        if f is None:
            continue
        b = poly_3d_calc([Vector(old[j]) for j in tris[f]], loc)
        W2[i] = sum(W[j] * bj for j, bj in zip(tris[f], b))
    for k, g in enumerate(ob.vertex_groups):
        for i in moved:
            if W2[i, k] > 1e-5:
                g.add([int(i)], float(W2[i, k]), 'REPLACE')
            elif W[i, k] > 0:
                g.remove([int(i)])
    print('  weights: %d moved vertices given the weights of where they are now' % len(moved))


def transfer(old, new, lo):
    """The rest pose's move (old -> new) onto the posed leader head lo: per moved vertex turned as the head there is
    round it (a rigid fit over everything within 3 cm of it)."""
    d = new - old
    moved = np.nonzero(np.linalg.norm(d, axis=1) > 1e-7)[0]
    out = lo.copy()
    kd = KDTree(len(old))
    for i, p in enumerate(old):
        kd.insert(p, i)
    kd.balance()
    cells = {}
    for i in moved:
        cells.setdefault(tuple(np.floor(old[i] / 0.015).astype(int)), []).append(i)
    worst = 0.0
    for idx in cells.values():
        cen = old[idx].mean(0)
        near = [j for _, j, _ in kd.find_range(cen, 0.03)]
        A, B = old[near], lo[near]
        ca, cb = A.mean(0), B.mean(0)
        U, _, Vt = np.linalg.svd((A - ca).T @ (B - cb))
        Rm = (U @ Vt).T
        if np.linalg.det(Rm) < 0:
            sys.exit('no fit at %s' % np.round(cen, 3))
        worst = max(worst, float(np.linalg.norm((A - ca) @ Rm.T + cb - B, axis=1).max()))
        out[idx] = lo[idx] + d[idx] @ Rm.T
    print('leader: %d vertices moved in %d parts, fits within %.2f mm' % (len(moved), len(cells), worst * 1000))
    return out


def main():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    head = bpy.data.objects['Head']
    if MARK in head:
        sys.exit('the head is mended already (%s)' % bpy.data.filepath)
    old = head_co(head)
    polys = [tuple(p.vertices) for p in head.data.polygons]
    print('1. his left upper lid')
    new = lowered(old, polys, neighbours(head.data))
    print('2. the lower lip')
    new = lip_back(new)
    print('3. folded faces')
    new = relaxed(new, head.data)
    print('4. spiky patches')
    new = smoothed(new, neighbours(head.data))
    print('6. faces through each other')
    new = uncrossed(new, head.data)
    print('5. folds left')
    E, _ = eyes()
    pv = [tuple(p.vertices) for p in head.data.polygons]
    cen = np.array([new[list(q)].mean(0) for q in pv])
    near_eye = np.min([np.linalg.norm(cen - e, axis=1) for e in E.values()], 0) < FOLD_EYE
    new = unfolded(new, head.data, near_eye | (cen[:, 2] < NECK_CUT))  # (the neck's cut edge: in the collar)
    moved = np.linalg.norm(new - old, axis=1)
    print('rest: %d vertices moved, at most %.2f mm' % (int((moved > 1e-7).sum()), moved.max() * 1000))
    set_co(head, new)
    reweighted(head, old, new)
    head[MARK] = True
    out = os.path.abspath(args[0]) if args else HERE
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, os.path.basename(REST)), compress=True)
    bpy.ops.wm.open_mainfile(filepath=LEADER)
    head = bpy.data.objects['Head']
    if MARK in head:
        sys.exit('the head is mended already (%s)' % LEADER)
    lo0 = head_co(head)
    lo = transfer(old, new, lo0)
    set_co(head, lo)
    print('leader: %d faces the pose folded smoothed out, %d left' % pose_folds(head, new))
    E, _ = eyes()
    lo = head_co(head)
    pv = [tuple(p.vertices) for p in head.data.polygons]
    cen = np.array([lo[list(q)].mean(0) for q in pv])
    near_eye = np.min([np.linalg.norm(cen - e, axis=1) for e in E.values()], 0) < FOLD_EYE
    lo = unfolded(lo, head.data, near_eye | (cen[:, 2] < NECK_CUT))
    set_co(head, uncrossed(lo, head.data))
    reweighted(head, lo0, head_co(head))
    head[MARK] = True
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, os.path.basename(LEADER)), compress=True)


main()

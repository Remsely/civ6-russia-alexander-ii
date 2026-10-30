# His left upper lid lowered over the eyeball, the head's mesh otherwise untouched (build_head.py is not repeatable, so
# the head is never rebuilt): the generation set his left eyeball 3.3 mm lower than his right one, and its opening is
# 2.25 mm taller (-4..+6.75 mm over the ball's middle against -6..+2.5): the whole iris bare, a staring, swollen look;
# in the portrait both lids cover the irises' tops.
#   blender -b art/3d/alexander_rest.blend --python art/3d/head_lid.py            (both blends, once)
#   blender -b art/3d/alexander_rest.blend --python art/3d/head_lid.py -- DIR    (both so changed, saved in DIR)
# The upper lid's skin slides down over the ball (its distance off the ball's middle kept: it stays over the blink's
# Eyelids), each place along it LID_SHARE of the way to making the opening there as tall as his right one's (mirrored),
# less from the lid's middle to the fold under the brow, which stays; the lower lid stays. Both eyes must stay one
# size: from the leader camera (the face square to it) the bare eyeball of each, his left 4653 px against 4229 before.
# alexander_leader.blend's head is the portrait's pose: the same move, turned as the head there is round the eye; and
# faces the pose folded over by the eyes turned out again (unfold).
# After it, head_touchup.py again (its masks are by the surface's place).
import bpy, math, os, sys
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
REST = os.path.join(HERE, 'alexander_rest.blend')
LEADER = os.path.join(HERE, 'alexander_leader.blend')
MARK = 'lid_l_lowered'            # the Head object's property once done
OPEN_X = np.arange(-16.0, 16.1, 0.5)  # mm across (out from the nose) the openings are measured at
OPEN_Z = np.arange(-10.0, 12.0, 0.25)  # ... and over the ball's middle
LID_LO = (0.5, 2.5)               # mm over the opening's lower edge (there): the slide fading in (the socket's lining)
LID_HI = (11.5, 17.0)             # mm over the ball's middle: fading out by the fold under the brow (it stays)
LID_RAD = (22.0, 27.0)            # mm off the ball's middle: none past (the brow)
LID_SHARE = 0.25                  # this share of the way to as tall as his right one's: from the leader camera both eyes
                                  # one size (bare eyeball 4242 px against his right's 4229; all the way, 2940 - half shut),
                                  # the irises' tops under the lids alike
LID_SMOOTH = 1.5                  # mm: the slide along the lid smoothed over this
LID_CORNER = (0.5, 12.0, 15.5)    # no more than this share of the opening's height there; fading out between these mm
                                  # across (the corners stay where they meet the lower lid: shut on his right, the whole
                                  # height came down, a wedge under the outer one)


def smoothstep(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def eyes():
    """The eyeballs' middles and radius (his left: +x)."""
    ob = bpy.data.objects['Eyes']
    ec = np.array([ob.matrix_world @ v.co for v in ob.data.vertices])
    out = {}
    for s, m in (('l', ec[:, 0] > ec[:, 0].mean()), ('r', ec[:, 0] <= ec[:, 0].mean())):
        e = ec[m]
        out[s] = (e.min(0) + e.max(0)) / 2
    return out, float((e.max(0) - e.min(0)).max() / 2)


def head_co(ob):
    return np.array([ob.matrix_world @ v.co for v in ob.data.vertices])


def opening(tree, c, sx, R):
    """Over each OPEN_X, seen from the front: the eyeball's bare span (mm over its middle; nan where it is shut)."""
    lo, hi = [], []
    for dx in OPEN_X:
        x = c[0] + sx * dx / 1000
        bare = []
        for dz in OPEN_Z:
            r2 = R * R - (dx / 1000) ** 2 - (dz / 1000) ** 2
            if r2 <= 0:
                continue
            hit = tree.ray_cast(Vector((x, c[1] - 0.2, c[2] + dz / 1000)), Vector((0, 1, 0)), 0.3)
            if hit[0] is None or hit[0].y - c[1] > -math.sqrt(r2):
                bare.append(dz)
        lo.append(min(bare) if bare else np.nan)
        hi.append(max(bare) if bare else np.nan)
    return np.array(lo), np.array(hi)


def lowered(co, polys):
    """Rest-pose vertices -> the same with his left upper lid slid down. -> (vertices, the eyeball's middle)"""
    E, R = eyes()
    c = E['l']
    tree = BVHTree.FromPolygons([Vector(p) for p in co], polys)
    (l0, l1), (r0, r1) = opening(tree, c, 1, R), opening(tree, E['r'], -1, R)
    drop = np.nan_to_num(np.clip((l1 - l0) - np.nan_to_num(r1 - r0), 0, (l1 - l0) * LID_CORNER[0]))
    drop *= LID_SHARE * (1 - smoothstep(np.abs(OPEN_X), *LID_CORNER[1:]))
    k = np.exp(-0.5 * (np.arange(-8, 9) * 0.5 / LID_SMOOTH) ** 2)
    drop = np.convolve(np.pad(drop, 8), k / k.sum(), 'valid')
    floor = np.interp(OPEN_X, OPEN_X[~np.isnan(l0)], l0[~np.isnan(l0)])
    for x, a0, a1, b0, b1, d in list(zip(OPEN_X, l0, l1, r0, r1, drop))[::4]:
        print('  %+5.1f mm: opening %5.2f..%5.2f (his right %5.2f..%5.2f) -> its top down %.2f mm' % (x, a0, a1, b0, b1, d))
    q = co - c
    dxo, dz = q[:, 0] * 1000, q[:, 2] * 1000  # out from the nose: +x on his left
    w = (smoothstep(dz - np.interp(dxo, OPEN_X, floor), *LID_LO) * (1 - smoothstep(dz, *LID_HI))
         * (1 - smoothstep(np.linalg.norm(q, axis=1) * 1000, *LID_RAD)) * (q[:, 1] < 0.004))
    d = np.interp(dxo, OPEN_X, drop, left=0, right=0) * w / 1000
    p = q - np.stack([np.zeros_like(d), np.zeros_like(d), d], 1)  # down, then back to its distance off the middle
    p *= (np.linalg.norm(q, axis=1) / np.maximum(np.linalg.norm(p, axis=1), 1e-9))[:, None]
    return c + p, c


def set_co(ob, co):
    inv = np.array(ob.matrix_world.inverted())
    loc = co @ inv[:3, :3].T + inv[:3, 3]
    ob.data.vertices.foreach_set('co', loc.astype(np.float32).ravel())
    ob.data.update()


def lids_check(head):
    """The blink's Eyelids (leader only): under the skin at rest, along rays from each eyeball's middle."""
    lids = bpy.data.objects.get('Eyelids')
    if not lids:
        return
    hc = head_co(head)
    tree = BVHTree.FromPolygons([Vector(p) for p in hc], [tuple(p.vertices) for p in head.data.polygons])
    rig = bpy.data.objects['HumanRig']
    lc = head_co(lids)
    for s in 'lr':
        c = rig.matrix_world @ rig.data.bones['eye_' + s].head_local
        gi = lids.vertex_groups['lid_upper_' + s].index
        idx = [v.index for v in lids.data.vertices if any(g.group == gi for g in v.groups)]
        worst = 1.0
        for i in idx:
            d = Vector(lc[i]) - c
            hit = tree.ray_cast(c, d.normalized(), 0.05)
            worst = min(worst, (hit[3] if hit[0] else 1.0) - d.length)
        print('eyelid %s: under the skin by %.2f mm at least at rest' % (s, worst * 1000))


def face_normals(pv, co):
    tri = co[np.array([v[:3] for v in pv])]
    fn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    return fn / np.maximum(np.linalg.norm(fn, axis=1), 1e-15)[:, None]


def folded(pairs, pv, co):
    """Faces folded over a neighbour (normals across an edge more than square)."""
    fn = face_normals(pv, co)
    return {f for g, h in pairs if fn[g] @ fn[h] < 0 for f in (g, h)}


def unfold(head, rest, near=(0.018, 0.035), reach=0.0006):
    """Faces the pose folded over a neighbour on the skin round the eyes, between near off an eyeball's middle (in
    the socket nearer, the lids' linings, out of sight, are left as they are; slivers: a row of vertices
    nearly in line, stretched by the pose, turned over - on his nose's left side by the eye, a white fleck in the
    light): each of their vertices moved along the skin (at most reach) as little as turns them all out again.
    -> vertices moved"""
    me = head.data
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
    nb = [[] for _ in pv]
    for g, h in pairs:
        nb[g].append(h); nb[h].append(g)
    co = head_co(head)
    E, _ = eyes()
    keep = folded(pairs, pv, rest)
    moved = set()
    for _ in range(4):
        bad = {f for f in folded(pairs, pv, co) - keep
               if near[0] < min(np.linalg.norm(co[pv[f][0]] - e) for e in E.values()) < near[1]}
        if not bad:
            break
        for v in sorted({v for f in bad for v in pv[f]}):
            fn = face_normals(pv, co)
            ring = {g for f in vf[v] for g in nb[f]} - set(vf[v])
            n = fn[[g for g in ring if g not in bad] or list(ring)].sum(0)
            n /= np.linalg.norm(n)
            u = np.cross(n, [1.0, 0, 0] if abs(n[0]) < 0.9 else [0, 1.0, 0]); u /= np.linalg.norm(u)
            w = np.cross(n, u)
            local = sorted(set(vf[v]) | ring)
            idx = {f: i for i, f in enumerate(local)}
            steps = np.linspace(-reach, reach, 25)
            cand = sorted(((a, b) for a in steps for b in steps if a * a + b * b <= reach * reach),
                          key=lambda ab: ab[0] ** 2 + ab[1] ** 2)
            best = None
            for a_, b_ in cand:  # along the skin: a sliver turns over with which side of its row its vertex is
                c2 = co.copy(); c2[v] = co[v] + u * a_ + w * b_
                f2 = face_normals([pv[f] for f in local], c2)
                worst = min(f2[idx[f]] @ f2[idx[g]] for f in vf[v] for g in nb[f] if g in idx)
                if best is None or worst > best[0] + 1e-9:
                    best = (worst, u * a_ + w * b_)
                if worst > 0.5:
                    break
            co[v] = co[v] + best[1]
            if np.any(best[1]):
                moved.add(v)
    set_co(head, co)
    left = {f for f in folded(pairs, pv, co) - keep
            if near[0] < min(np.linalg.norm(co[pv[f][0]] - e) for e in E.values()) < near[1]}
    print('  folded by the pose by the eyes: %d faces left' % len(left))
    return len(moved)


def main():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    head = bpy.data.objects['Head']
    if MARK in head:
        sys.exit('his left upper lid is lowered already (%s)' % bpy.data.filepath)
    old = head_co(head)
    new, c = lowered(old, [tuple(p.vertices) for p in head.data.polygons])
    moved = np.linalg.norm(new - old, axis=1)
    print('rest: %d vertices moved, at most %.2f mm' % (int((moved > 1e-6).sum()), moved.max() * 1000))
    set_co(head, new)
    head[MARK] = True
    out = os.path.abspath(args[0]) if args else HERE
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, os.path.basename(REST)), compress=True)
    # the leader: its head is posed; per vertex the same move turned as the head is round the eye (a fit there)
    bpy.ops.wm.open_mainfile(filepath=LEADER)
    head = bpy.data.objects['Head']
    if MARK in head:
        sys.exit('his left upper lid is lowered already (%s)' % LEADER)
    lo = head_co(head)
    near = np.linalg.norm(old - c, axis=1) < 0.04
    A, B = old[near], lo[near]
    ca, cb = A.mean(0), B.mean(0)
    U, _, Vt = np.linalg.svd((A - ca).T @ (B - cb))
    R = (U @ Vt).T
    if np.linalg.det(R) < 0:
        sys.exit('no fit')
    res = np.linalg.norm((A - ca) @ R.T + cb - B, axis=1)
    print('leader: the head round the eye turned %.1f deg, fit within %.2f mm' % (
        math.degrees(math.acos(np.clip((np.trace(R) - 1) / 2, -1, 1))), res.max() * 1000))
    set_co(head, lo + (new - old) @ R.T)
    head[MARK] = True
    print('leader: %d vertices of faces the pose folded by the eyes moved' % unfold(head, new))
    lids_check(head)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, os.path.basename(LEADER)), compress=True)


if __name__ == '__main__':
    main()

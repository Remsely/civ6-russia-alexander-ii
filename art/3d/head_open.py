# Both upper lids raised over the eyeballs, the head's mesh otherwise untouched (build_head.py is not repeatable, so the
# head is never rebuilt): from the leader camera the lids covered 31% (his right) and 24% (his left) of the irises'
# height, the openings 0.54-0.56 of an iris tall; in the portrait 15-17%, the openings 0.70-0.72 - the eyes read
# narrow, screwed up.
#   blender -b art/3d/alexander_rest.blend --python art/3d/head_open.py            (both blends, once)
#   blender -b art/3d/alexander_rest.blend --python art/3d/head_open.py -- DIR    (both so changed, saved in DIR)
# The upper lid's skin slides up over the ball (as head_lid.py slid his left one down: its distance off the ball's
# middle kept), RAISE at the lid's middle, less towards the corners, which stay; less up to the fold under the brow,
# which stays; his left lower lid slid down LOWER (it covered 25% of the iris from below against his right's 18%, the
# portrait's 13%), fading out over the bag. Both eyes must stay one size (from the leader camera the bare eyeball of
# each, spot view -25@0). Under his right eye the groove under the lower lid filled (0.5 mm deep at the middle, 2-3 mm
# by the outer corner, a bag's bulge under it: the bag read heavier than his left's, smooth there) - the depth only,
# smoothed over the mesh; the lid's edge stays.
# alexander_leader.blend: the same move turned as the head there is round the eye, faces the pose folded turned out
# again; and the blink's Eyelids (at rest under the skin over the opening, their edge by the lid's) turned up with it
# about the eye's centre, the blink (sc['head']['BLINK_L' / 'BLINK_R']) as much longer, and longer by the lower lid's
# drop: shut they lie as before, run on as far under the lower lid.
# After it, head_touchup.py again (its masks are by the surface's place), the stress tests of the head and clash.
import bpy, math, os, sys
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from head_lid import eyes, head_co, opening, set_co, unfold, smoothstep, OPEN_X, LID_LO, LID_RAD  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REST = os.path.join(HERE, 'alexander_rest.blend')
LEADER = os.path.join(HERE, 'alexander_leader.blend')
MARK = 'lids_raised'              # the Head object's property once done
RAISE = {'r': 2.5, 'l': 1.9}      # mm up at the lid's middle: from the leader camera the irises' tops 13-15% covered
LOWER = {'r': 0.0, 'l': 0.9}      # mm down at the lower lid's middle: his left's bottom from 25% covered to his right's
RAISE_X = (5.0, 13.0)             # mm across from the ball's middle: all of it within the first, none past the second
                                  # (the corners stay where they meet the lower lid)
RAISE_HI = (6.0, 15.0)            # mm over the opening's top: all of it up to the first (the lid), none by the second
                                  # (the fold under the brow)
LOWER_LO = ((-1.5, -0.5), (3.0, 10.0))  # mm under the opening's lower edge: fading in (the lid's lining), out (the bag)
UNDER = {'r': ((-6.0, -7.0), (-13.0, -17.0), (-3.0, 1.0), (17.0, 21.0))}  # the groove filled under these eyes: mm
                                  # over the ball's middle (fading in, full), (full, none); mm out from the nose
                                  # (none, full), (full, none)
UNDER_ROUNDS = 40                 # ... rounds of each vertex's depth (y) to its neighbours' mean, weighted
EYELIDS_SPARE = 0.3               # degrees the blink's Eyelids turn up more than the skin's edge at the lid's middle


def raised(co, polys):
    """Rest-pose vertices -> the same with both upper lids slid up (and the lower ones down). -> (vertices, {side:
    (eye's middle, the upper edge's rise, the lower edge's drop - degrees at the lid's middle)})"""
    E, R = eyes()
    tree = BVHTree.FromPolygons([Vector(p) for p in co], polys)
    new = co.copy()
    out = {}
    for s, sx in (('l', 1), ('r', -1)):
        c = E[s]
        lo, hi = opening(tree, c, sx, R)
        ok = ~np.isnan(hi)
        floor = np.interp(OPEN_X, OPEN_X[ok], lo[ok])
        top = np.interp(OPEN_X, OPEN_X[ok], hi[ok])
        q = co - c
        dxo, dz = q[:, 0] * 1000 * sx, q[:, 2] * 1000  # out from the nose
        over = dz - np.interp(dxo, OPEN_X, top)
        w = (smoothstep(dz - np.interp(dxo, OPEN_X, floor), *LID_LO) * (1 - smoothstep(over, *RAISE_HI))
             * (1 - smoothstep(np.abs(dxo), *RAISE_X)) * (1 - smoothstep(np.linalg.norm(q, axis=1) * 1000, *LID_RAD))
             * (q[:, 1] < 0.004))
        under = np.interp(dxo, OPEN_X, floor) - dz
        wl = (smoothstep(under, *LOWER_LO[0]) * (1 - smoothstep(under, *LOWER_LO[1]))
              * (1 - smoothstep(np.abs(dxo), *RAISE_X)) * (1 - smoothstep(np.linalg.norm(q, axis=1) * 1000, *LID_RAD))
              * (q[:, 1] < 0.004))
        d = (RAISE[s] * w - LOWER[s] * wl) / 1000
        p = q + np.stack([np.zeros_like(d), np.zeros_like(d), d], 1)  # up / down, then back to its distance off the middle
        p *= (np.linalg.norm(q, axis=1) / np.maximum(np.linalg.norm(p, axis=1), 1e-9))[:, None]
        move = p - q
        new = new + move * (np.linalg.norm(move, axis=1) > 0)[:, None]
        # the edge's rise at the lid's middle, in degrees about the eye's centre
        t0 = float(np.interp(0.0, OPEN_X, top)) / 1000
        r_ = math.sqrt(max(R * R - t0 * t0, 1e-12))
        a0 = math.degrees(math.atan2(t0, r_))
        a1 = math.degrees(math.atan2(t0 + RAISE[s] / 1000, math.sqrt(max(R * R - (t0 + RAISE[s] / 1000) ** 2, 1e-12))))
        f0 = float(np.interp(0.0, OPEN_X, floor)) / 1000
        b0, b1 = (math.degrees(math.asin(np.clip(z / R, -1, 1))) for z in (f0, f0 - LOWER[s] / 1000))
        out[s] = (c, a1 - a0, b0 - b1)
        print('%s: opening at the middle %.2f..%.2f mm over the ball\'s middle -> top %.2f; %d vertices, at most %.2f mm;'
              ' the edge up %.1f deg, the lower one down %.1f' % (
                  s, f0 * 1000, t0 * 1000, t0 * 1000 + RAISE[s], int((np.abs(d) > 0).sum()),
                  np.linalg.norm(move, axis=1).max() * 1000, a1 - a0, b0 - b1))
    return new, out


def filled(co, polys, E):
    """The grooves under the eyes in UNDER filled: per vertex its depth (y) to its neighbours' mean, UNDER_ROUNDS
    times, by its weight there (the rest fixed)."""
    ed = set()
    for q in polys:
        for i in range(len(q)):
            a, b = q[i], q[(i + 1) % len(q)]
            ed.add((min(a, b), max(a, b)))
    ed = np.array(sorted(ed))
    deg = np.bincount(ed.ravel(), minlength=len(co)).astype(float)
    out = co.copy()
    for s, (z_in, z_out, x_in, x_out) in UNDER.items():
        q = co - E[s]
        sx = 1 if s == 'l' else -1
        dxo, dz = q[:, 0] * 1000 * sx, q[:, 2] * 1000
        w = ((1 - smoothstep(dz, z_in[1], z_in[0])) * smoothstep(dz, z_out[1], z_out[0]) * smoothstep(dxo, *x_in)
             * (1 - smoothstep(dxo, *x_out)) * (q[:, 1] < 0))
        y = out[:, 1].copy()
        for _ in range(UNDER_ROUNDS):
            acc = np.zeros_like(y)
            np.add.at(acc, ed[:, 0], y[ed[:, 1]]); np.add.at(acc, ed[:, 1], y[ed[:, 0]])
            y = y + (acc / np.maximum(deg, 1) - y) * w
        print('%s: the groove under the eye filled: %d vertices, at most %.2f mm' % (
            s, int((w > 0).sum()), np.abs(y - out[:, 1]).max() * 1000))
        out[:, 1] = y
    return out


def eyelids_up(rise):
    """The blink's Eyelids (leader only) turned up about each eye's centre: the edge as the skin's edge rose there,
    the strip stretched up to the top by as much again and the lower lid's drop (its span is the opening's and 6 deg:
    shut, the top must still reach under the raised skin - else a sliver of the eye over it), the blink as much longer
    as the edge turned and the lower lid dropped; then checked: every vertex under the skin at rest (a ray from the
    eye's centre through it meets the skin further out)."""
    lids = bpy.data.objects.get('Eyelids')
    if not lids:
        return
    rig = bpy.data.objects['HumanRig']
    mw = rig.matrix_world
    bl = rig.data.bones
    lat = (mw.to_3x3() @ (bl['eye_l'].head_local - bl['eye_r'].head_local)).normalized()
    fwd = lat.cross(Vector((0, 0, 1))).normalized()  # (build_skin's axes)
    up = fwd.cross(lat).normalized()  # (up: build_skin turns its elevation about -lat)
    lc = head_co(lids)
    hd = bpy.context.scene['head'].to_dict()
    for s in 'lr':
        c = np.array(mw @ bl['eye_' + s].head_local)
        a = rise[s][1] + EYELIDS_SPARE
        extra = a + rise[s][2]
        gi = lids.vertex_groups['lid_upper_' + s].index
        idx = np.array([v.index for v in lids.data.vertices if any(g.group == gi for g in v.groups)])
        d = lc[idx] - c
        el = np.degrees(np.arctan2(d @ np.array(up), d @ np.array(fwd)))
        col = np.round(np.degrees(np.arcsin(np.clip(d @ np.array(lat) / np.linalg.norm(d, axis=1), -1, 1)))).astype(int)  # (its
        # columns: turning about the eyes' line keeps that)
        t = np.zeros(len(idx))
        for k in np.unique(col):
            m = col == k
            t[m] = (el[m] - el[m].min()) / max(el[m].max() - el[m].min(), 1e-6)
        for i, ang in enumerate(a + extra * t):
            M = np.array(Matrix.Rotation(math.radians(ang), 3, -lat))  # (up: as build_skin.lid_dir's elevation)
            lc[idx[i]] = d[i] @ M.T + c
        hd['BLINK_' + s.upper()] = hd['BLINK_' + s.upper()] + a + rise[s][2]
        print('eyelid %s: its edge turned up %.1f deg, its top %.1f; blink %.1f deg' % (
            s, a, a + extra, hd['BLINK_' + s.upper()]))
    set_co(lids, lc)
    bpy.context.scene['head'] = hd
    head = bpy.data.objects['Head']
    hc = head_co(head)
    tree = BVHTree.FromPolygons([Vector(p) for p in hc], [tuple(p.vertices) for p in head.data.polygons])
    for s in 'lr':
        c = mw @ bl['eye_' + s].head_local
        gi = lids.vertex_groups['lid_upper_' + s].index
        worst, bare = 1.0, 0
        for v in lids.data.vertices:
            if not any(g.group == gi for g in v.groups):
                continue
            d = Vector(lc[v.index]) - c
            hit = tree.ray_cast(c, d.normalized(), 0.05)
            if hit[0] is None:
                bare += 1
                continue
            worst = min(worst, hit[3] - d.length)
        print('eyelid %s: under the skin by %.2f mm at least at rest; %d vertices bare' % (s, worst * 1000, bare))


def main():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    head = bpy.data.objects['Head']
    if MARK in head:
        sys.exit('the upper lids are raised already (%s)' % bpy.data.filepath)
    old = head_co(head)
    polys = [tuple(p.vertices) for p in head.data.polygons]
    new, rise = raised(old, polys)
    new = filled(new, polys, {s: v[0] for s, v in rise.items()})
    moved = np.linalg.norm(new - old, axis=1)
    print('rest: %d vertices moved, at most %.2f mm' % (int((moved > 1e-6).sum()), moved.max() * 1000))
    set_co(head, new)
    head[MARK] = True
    out = os.path.abspath(args[0]) if args else HERE
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, os.path.basename(REST)), compress=True)
    # the leader: its head is posed; per vertex the same move turned as the head is round each eye (a fit there)
    bpy.ops.wm.open_mainfile(filepath=LEADER)
    head = bpy.data.objects['Head']
    if MARK in head:
        sys.exit('the upper lids are raised already (%s)' % LEADER)
    lo = head_co(head)
    res_co = lo.copy()
    for s in 'lr':
        c = rise[s][0]
        near = np.linalg.norm(old - c, axis=1) < 0.04
        A, B = old[near], lo[near]
        ca, cb = A.mean(0), B.mean(0)
        U, _, Vt = np.linalg.svd((A - ca).T @ (B - cb))
        R = (U @ Vt).T
        if np.linalg.det(R) < 0:
            sys.exit('no fit')
        res = np.linalg.norm((A - ca) @ R.T + cb - B, axis=1)
        print('leader %s: the head round the eye turned %.1f deg, fit within %.2f mm' % (
            s, math.degrees(math.acos(np.clip((np.trace(R) - 1) / 2, -1, 1))), res.max() * 1000))
        mine = near & (np.linalg.norm(new - old, axis=1) > 0)
        res_co[mine] = lo[mine] + (new - old)[mine] @ R.T
    set_co(head, res_co)
    head[MARK] = True
    print('leader: %d vertices of faces the pose folded by the eyes moved' % unfold(head, new))
    eyelids_up(rise)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, os.path.basename(LEADER)), compress=True)


if __name__ == '__main__':
    main()

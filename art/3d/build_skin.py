# Weights for motion, and what a moving face needs: the stance is the rig's rest pose, so what bones carry each vertex
# changes nothing of it - only how the leader moves. What the stress tests (tools/blender/stress.py over
# tools/blender/motion.py's stress_*) found and this step mends:
# 1. The skirt's swing bones (build_dangles.py) took the sleeves too where the hands hang below the waist: the cuffs
#    and the hands went with the arm, the sleeve's end lagged behind on the skirt (2 cm through the cuff at a 40 deg
#    raise). They keep off whatever an arm bone carries.
# 2. The neck opening goes with the chest: the uniform round it (and the collars on it, the head's neck inside) is
#    carried by spine_03 and the clavicles only - MPFB's upper arm reached in to the collar's foot, and an arm raised
#    pulled the collar 2.6 times as long on that side. The sleeves' ends go with the forearm only.
# 3. The belt is a stiff band: it and the cloth under it carried alike over its height (BELT_*).
# 4. What lies on the uniform follows the cloth under it: each vertex takes the cloth's weights at the nearest point of
#    it (MPFB's, transferred to the uniform) - the pieces built with their own weights slid over it and through it as
#    soon as the chest or a shoulder moved (the sash and the aiguillettes 4-6 mm into the chest breathing, the orders
#    through it with an arm raised). A rigid piece (an order, a button, the buckle) takes its pieces' mean, so it moves
#    whole; an epaulette's field the cloth's evened out a little over it (SMOOTH_ROUNDS); a loose piece keeps its swing
#    bone's share and takes the cloth's for the rest; the aiguillettes' cords from under the epaulette go with it.
# 5. The fringe rides the shoulder: down each strand from the rim the epaulette's weights give way to the cloth's under
#    it, so when the arm rises the strands on the sleeve rise with it (they hung from the shoulder strap, the arm came
#    up through them); its swing bone is the upper arm's child and has a smaller share.
# 6. Spurs and soles go with the boot round them.
# 7. Eyelids that close over the eyes (LID_*); sc['head']['BLINK_L' / 'BLINK_R']: degrees each turns shut.
# 8. The jaw eased over the lips (MOUTH_*).
# blender -b art/3d/alexander_leader.blend --python art/3d/build_skin.py   (after build_dangles.py; in place)
import bpy, math, os, sys
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from mathutils.interpolate import poly_3d_calc
from mathutils.kdtree import KDTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

OUT = sys.argv[sys.argv.index('--') + 1] if '--' in sys.argv else os.path.join(HERE, 'alexander_leader.blend')
ARM = ('upperarm_', 'lowerarm_', 'hand_', 'index_', 'middle_', 'ring_', 'pinky_', 'thumb_')
# 4: piece -> (how it follows the cloth: 'all' vertex by vertex, 'rigid' each piece of it whole, 'smooth' vertex by
# vertex evened out over the piece, 'held' the share its swing bone does not carry; which cloth: the torso's, a
# sleeve's, or the whole uniform's) - the torso's pieces never from a sleeve (his right hand lies on the belt at his
# back: the belt took the forearm's weights there and stretched out after the hand when the arm moved)
FOLLOW = {'Sash': ('all', 'torso'), 'Belt': ('all', 'torso'), 'Collar': ('all', 'torso'),
          'CollarStand': ('all', 'torso'), 'ShirtCollar': ('all', 'torso'), 'Orders': ('rigid', 'torso'),
          'Buttons': ('rigid', 'torso'), 'Buckle': ('rigid', 'torso'), 'Aiguillettes': ('held', 'all'),
          'AiguilletteTips': ('held', 'torso'), 'BeltKnot': ('held', 'torso'), 'Sabre': ('held', 'torso'),
          'Epaulette_l': ('smooth', 'all'), 'Epaulette_r': ('smooth', 'all')}
for _s in 'lr':
    FOLLOW.update({'Cuff_' + _s: ('all', 'sleeve_' + _s), 'ShirtCuff_' + _s: ('all', 'sleeve_' + _s),
                   'CuffFlap_' + _s: ('rigid', 'sleeve_' + _s), 'CuffButtons_' + _s: ('rigid', 'sleeve_' + _s)})
SLEEVE = 0.5                       # a vertex of the uniform is a sleeve's where its arm bones carry more than this
BELT_BIN, BELT_SMOOTH = 5.0, 6     # 3: degrees round the waist per sector; rounds evening the sectors out
BELT_EASE = 0.035                  # ... the cloth eased back from the band's weights to its own over this above / below
SMOOTH_ROUNDS = 8                  # 4, 'smooth': rounds of evening the cloth's weights over the piece (an epaulette's
                                   # field: whole, the shoulder's cloth and the sash over it bent up through it, 2-4 cm
                                   # with an arm raised or the shoulder shrugged; evened out over 40 rounds, the deltoid
                                   # rose over it with the arm out 45 deg; vertex by vertex, it crumpled at 80)
AIG_EP = (0.03, 0.08)              # 4: the aiguillettes' cords whose top end is within the first of the right epaulette
                                   # take its weights there, the cloth's again the second along the cord
FRINGE_SHARE = 0.3                 # 5: the fringe's swing bone carries at most this of a strand (it carried all of
                                   # the strands' ends: they could not ride the sleeve)
FRINGE_RIDE = (0.1, 0.7)           # ... down the strand (0 at the rim, 1 at its end) the cloth's weights take over
NECK_R = (0.10, 0.15)              # 2: metres off the neck's axis: no upper arm within the first, MPFB's past the
                                   # second (the collar's foot is ~0.08 off it, the shoulder joint 0.23)
NECK_Z = 1.62                      # ... above this
FLOOR, CAP = 0.004, 8              # weights under the first dropped; at most this many bones a vertex
# 7: the eyelids - the skin's own upper lid stretched over the eye in a blink (from a strip under the brow to the
# whole opening) and smeared the lid's crease down over it, grey; now a lid of its own slides down from under the skin
LID_R = 0.00025                    # its sphere this far outside the eyeball (the skin round the opening is 0.5 mm off it)
LID_GAP = 0.0006                   # at rest its edge where the skin over the ball stands this far off it
LID_TUCK = 1.5                     # degrees it runs on under the lower lid shut
LID_TOP = 6.0                      # degrees more of it above the opening shut (under the skin)
LID_STEP = 2.0                     # degrees between its rows and columns
LID_UV = (2.0, 12.0)               # degrees over the upper rim (in the eye's middle) its colour comes from: the lash
                                   # line at its edge, the lid's skin over the rest (each taken from points of the head's
                                   # texture over the strip, it ran across the texture's seams in cracks)
# 8: the mouth is closed and has no inside: the jaw went from none on the upper lip to all on the lower one across one
# edge, and talking split the lips in a row of stretched slivers; eased over MOUTH_R round where they meet, the lips
# and chin stretch instead (a few degrees of jaw: talking under the moustache)
MOUTH_R, MOUTH_ROUNDS = 0.012, 60
LID_AZ = np.arange(-80.0, 80.5, 1.0)
LID_EL = np.arange(-50.0, 60.25, 0.5)

sc = bpy.context.scene
rig = bpy.data.objects['HumanRig']
BONES = [b.name for b in rig.data.bones]
B = {n: i for i, n in enumerate(BONES)}
uni = bpy.data.objects['Uniform']


def coords(ob):
    co = np.zeros(len(ob.data.vertices) * 3); ob.data.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    m = np.array(ob.matrix_world)
    return co @ m[:3, :3].T + m[:3, 3]


def weights(ob):
    """(vertices, bones) array of ob's bone weights, each row summing to 1."""
    W = np.zeros((len(ob.data.vertices), len(BONES)))
    names = [g.name for g in ob.vertex_groups]
    for v in ob.data.vertices:
        for g in v.groups:
            n = names[g.group]
            if n in B:
                W[v.index, B[n]] += g.weight
    s = W.sum(1, keepdims=True)
    return np.where(s > 0, W / np.maximum(s, 1e-12), W)


def put(ob, W):
    """W written back as ob's bone groups: the small ones dropped, at most CAP a vertex, rows summing to 1."""
    W = W.copy()
    W[W < FLOOR] = 0
    if W.shape[1] > CAP:
        kth = -np.sort(-W, axis=1)[:, CAP - 1:CAP]
        W[W < kth] = 0
    W /= np.maximum(W.sum(1, keepdims=True), 1e-12)
    for g in list(ob.vertex_groups):
        if g.name in B:
            ob.vertex_groups.remove(g)
    groups = {j: ob.vertex_groups.new(name=BONES[j]) for j in np.where(W.any(0))[0]}
    for i, j in zip(*np.nonzero(W)):
        groups[j].add([int(i)], float(W[i, j]), 'REPLACE')


def islands(me):
    parent = list(range(len(me.vertices)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    for e in me.edges:
        parent[find(e.vertices[0])] = find(e.vertices[1])
    groups = {}
    for i in range(len(parent)):
        groups.setdefault(find(i), []).append(i)
    return [np.array(g) for g in groups.values()]


def along(ob, co, idx, start):
    """Lengths along ob's edges from the vertices start to each of idx (Dijkstra)."""
    import heapq
    nb = {}
    for e in ob.data.edges:
        a_, b_ = e.vertices
        l_ = float(np.linalg.norm(co[a_] - co[b_]))
        nb.setdefault(a_, []).append((b_, l_)); nb.setdefault(b_, []).append((a_, l_))
    dist = {int(i): 0.0 for i in start}
    heap = [(0.0, int(i)) for i in start]
    while heap:
        d, i = heapq.heappop(heap)
        if d > dist.get(i, 1e9):
            continue
        for j, l_ in nb.get(i, ()):
            if d + l_ < dist.get(j, 1e9):
                dist[j] = d + l_
                heapq.heappush(heap, (d + l_, j))
    return np.array([dist.get(int(i), 1e9) for i in idx])


def is_bone(prefixes):
    return np.array([n.startswith(prefixes) for n in BONES])


DANGLE = is_bone(('dangle_',))
SKIRT = is_bone(('dangle_skirt_',))
ARMS = is_bone(ARM)

# ---------------------------------------------------------------- 1. the skirt's bones off the arms
WU = weights(uni)
arm = WU[:, ARMS].sum(1) > 0
WU[np.ix_(arm, SKIRT)] = 0
WU /= np.maximum(WU.sum(1, keepdims=True), 1e-12)
print('skirt bones off %d arm vertices' % int((arm & (weights(uni)[:, SKIRT].sum(1) > 0)).sum()))

# ---------------------------------------------------------------- 2. the neck opening with the chest
CU = coords(uni)
ax = Vector(sc['uniform']['NECK_AXIS'])
r = np.hypot(CU[:, 0] - ax.x, CU[:, 1] - ax.y)
t = np.clip((r - NECK_R[0]) / (NECK_R[1] - NECK_R[0]), 0, 1)
keep = np.where(CU[:, 2] > NECK_Z, t * t * (3 - 2 * t), 1.0)  # how much of the upper arm stays


def off_arms(W, keep):
    """The upper arms' weight times keep, the rest of it to the clavicle of its side."""
    for s in 'lr':
        u, c = B['upperarm_' + s], B['clavicle_' + s]
        moved = W[:, u] * (1 - keep)
        W[:, u] -= moved
        W[:, c] += moved
    return W


WU = off_arms(WU, keep)
print('neck opening: upper arm off %d uniform vertices' % int((keep < 1).sum()))
# the sleeves' ends on the forearm only: the hand flexed, they bent after it (a share of the hand from MPFB's wrist) and
# the stiff cuffs over them came apart from their flaps and buttons
for s in 'lr':
    hand = is_bone(tuple(p + s for p in ARM[2:]))
    WU[:, B['lowerarm_' + s]] += WU[:, hand].sum(1)
    WU[:, hand] = 0

# ---------------------------------------------------------------- 3. the belt a stiff band
belt = bpy.data.objects.get('Belt')
if belt:
    CB = coords(belt)
    bc = CB[:, :2].mean(0)
    if bpy.data.objects.get('Buckle'):  # the band as high as the buckle where it is (it stands over the belt's edges)
        CB = np.vstack([CB, coords(bpy.data.objects['Buckle'])])

    def azim(co):
        return np.degrees(np.arctan2(co[:, 0] - bc[0], -(co[:, 1] - bc[1]))) % 360

    ab = azim(CB)
    bins = np.arange(0, 360, BELT_BIN)
    lo = np.full(len(bins), np.nan); hi = np.full(len(bins), np.nan); rad = np.full(len(bins), np.nan)
    kb = (ab // BELT_BIN).astype(int) % len(bins)
    for k in range(len(bins)):
        sel = kb == k
        if sel.any():
            lo[k], hi[k] = CB[sel, 2].min(), CB[sel, 2].max()
            rad[k] = np.hypot(*(CB[sel, :2] - bc).T).min()
    ok = ~np.isnan(lo)
    for arr in (lo, hi, rad):  # sectors the belt's mesh missed: from their neighbours round the waist
        arr[~ok] = np.interp(bins[~ok], bins[ok], arr[ok], period=360)
    # the cloth under the band and its weights per sector: the mean over the band's height
    au = azim(CU)
    ku = (au // BELT_BIN).astype(int) % len(bins)
    r_u = np.hypot(*(CU[:, :2] - bc).T)
    under = (CU[:, 2] > lo[ku] - 0.002) & (CU[:, 2] < hi[ku] + 0.002) & (r_u < rad[ku] + 0.004) & (r_u > rad[ku] - 0.05)
    under &= WU[:, ARMS].sum(1) < SLEEVE
    band = np.zeros((len(bins), len(BONES)))
    for k in range(len(bins)):
        sel = under & (ku == k)
        if sel.any():
            band[k] = WU[sel].mean(0)
    have = band.any(1)
    for j in range(len(BONES)):
        band[~have, j] = np.interp(bins[~have], bins[have], band[have, j], period=360)
    for _ in range(BELT_SMOOTH):  # round the waist the band bends smoothly
        band = (np.roll(band, 1, 0) + 2 * band + np.roll(band, -1, 0)) / 4
    # the cloth takes it over the band's height, easing back to its own over BELT_EASE above and below
    near = (r_u < rad[ku] + 0.004) & (r_u > rad[ku] - 0.06) & (WU[:, ARMS].sum(1) < SLEEVE)
    dz = np.maximum(lo[ku] - CU[:, 2], CU[:, 2] - hi[ku])
    t = np.where(near, 1 - np.clip(dz / BELT_EASE, 0, 1), 0.0)
    t = t * t * (3 - 2 * t)
    WU = WU * (1 - t[:, None]) + band[ku] * t[:, None]
    print('belt: the cloth under it and %.0f%% round it as one band (%d vertices)' % (100 * (t > 0).mean(), int((t > 0).sum())))
put(uni, WU)
head = bpy.data.objects.get('Head')
if head:
    WH = weights(head)
    CH = coords(head)
    rh = np.hypot(CH[:, 0] - ax.x, CH[:, 1] - ax.y)
    th = np.clip((rh - NECK_R[0]) / (NECK_R[1] - NECK_R[0]), 0, 1)
    put(head, off_arms(WH, th * th * (3 - 2 * th)))  # the neck's foot inside the tunic (the head is all within)

# ---------------------------------------------------------------- 4. what lies on the cloth follows it
me = uni.data
me.calc_loop_triangles()
TRI = np.zeros(len(me.loop_triangles) * 3, np.int32); me.loop_triangles.foreach_get('vertices', TRI)
TRI = TRI.reshape(-1, 3)
side_arm = {s: WU[:, is_bone(tuple(p + s for p in ARM))].sum(1) for s in 'lr'}
REGION = {'all': np.ones(len(CU), bool), 'torso': (side_arm['l'] + side_arm['r']) < SLEEVE,
          'sleeve_l': side_arm['l'] >= SLEEVE, 'sleeve_r': side_arm['r'] >= SLEEVE}
TREES = {}


def cloth_weights(co, region='all'):
    """The uniform's weights at the nearest point of its region to each of co (interpolated over the triangle)."""
    if region not in TREES:
        tri = TRI[REGION[region][TRI].all(1)]
        TREES[region] = (BVHTree.FromPolygons([Vector(c) for c in CU], tri.tolist(), all_triangles=True), tri)
    tree, tri = TREES[region]
    out = np.zeros((len(co), len(BONES)))
    for i, p in enumerate(co):
        hit = tree.find_nearest(Vector(p))
        k = hit[2]
        a, b_, c = CU[tri[k]]
        v0, v1, v2 = b_ - a, c - a, np.array(hit[0]) - a
        d00, d01, d11, d20, d21 = v0 @ v0, v0 @ v1, v1 @ v1, v2 @ v0, v2 @ v1
        den = d00 * d11 - d01 * d01 or 1e-18
        y, z = (d11 * d20 - d01 * d21) / den, (d00 * d21 - d01 * d20) / den
        out[i] = WU[tri[k]].T @ np.array([1 - y - z, y, z])
    return out


for name, (how, region) in FOLLOW.items():
    ob = bpy.data.objects.get(name)
    if ob is None:
        continue
    W = weights(ob)
    WC = cloth_weights(coords(ob), region)
    if how == 'all':
        W = WC
    elif how == 'rigid':
        for idx in islands(ob.data):
            W[idx] = WC[idx].mean(0)
    elif how == 'smooth':  # vertex by vertex, evened out over the piece: it bends only as gently as the shoulder
        ed = np.zeros(len(ob.data.edges) * 2, np.int32); ob.data.edges.foreach_get('vertices', ed)
        ed = ed.reshape(-1, 2)
        deg = np.bincount(ed.ravel(), minlength=len(WC)).astype(float)[:, None]
        W = WC
        for _ in range(SMOOTH_ROUNDS):
            acc = np.zeros_like(W)
            np.add.at(acc, ed[:, 0], W[ed[:, 1]]); np.add.at(acc, ed[:, 1], W[ed[:, 0]])
            W = np.where(deg > 0, acc / np.maximum(deg, 1), W)
    else:  # held: the swing bones' share stays
        d = W[:, DANGLE].sum(1, keepdims=True)
        W = np.where(DANGLE, W, 0) + WC * (1 - d)
    put(ob, W)
print('following the cloth:', ', '.join(n for n in FOLLOW if bpy.data.objects.get(n)))

# the aiguillettes' cords where they come from under the epaulette go with it (from the cloth under them, they and the
# fringe over them went apart as soon as the shoulder moved, 2-4 cm through each other with a shrug)
aig, ep = bpy.data.objects.get('Aiguillettes'), bpy.data.objects.get('Epaulette_r')
if aig and ep:
    ep_w, ep_co = weights(ep), coords(ep)
    kd = KDTree(len(ep_co))
    for i, c in enumerate(ep_co):
        kd.insert(c, i)
    kd.balance()
    co = coords(aig)
    W = weights(aig)
    near = [kd.find(c) for c in co]
    # by the length along each cord from its end under the epaulette, the same all round the cord (by the distance
    # off the epaulette, the side of a cord nearer it took more and the cord twisted inside out)
    t = np.zeros(len(co))
    for idx in islands(aig.data):
        top = idx[co[idx, 2] > co[idx, 2].max() - 0.004]
        if min(near[i][2] for i in top) > AIG_EP[0]:
            continue
        arc = along(aig, co, idx, top)
        x = 1 - np.clip(arc / AIG_EP[1], 0, 1)
        t[idx] = x * x * (3 - 2 * x)
    d = W[:, DANGLE].sum(1, keepdims=True)
    held = np.where(DANGLE, 0, W) / np.maximum(1 - d, 1e-6)
    held = held * (1 - t[:, None]) + ep_w[[n[1] for n in near]] * t[:, None]
    put(aig, np.where(DANGLE, W, 0) + held * (1 - d))
    print('aiguillettes: %d vertices by the epaulette go with it' % int((t > 0).sum()))

# ---------------------------------------------------------------- 5. the fringe rides the shoulder
for s in 'lr':
    fr, ep = bpy.data.objects.get('EpauletteFringe_' + s), bpy.data.objects.get('Epaulette_' + s)
    if not (fr and ep):
        continue
    co = coords(fr)
    W = weights(fr)
    bone = 'dangle_fringe_' + s
    d = W[:, B[bone]] * FRINGE_SHARE / max(W[:, B[bone]].max(), 1e-6)
    ep_w, ep_co = weights(ep), coords(ep)  # the field's, where each strand hangs from it
    kd = KDTree(len(ep_co))
    for i, c in enumerate(ep_co):
        kd.insert(c, i)
    kd.balance()
    rim = ep_w[[kd.find(c)[1] for c in co]]
    top, bot = co[:, 2].max(), co[:, 2].min()
    u = np.clip(((top - co[:, 2]) / (top - bot) - FRINGE_RIDE[0]) / (FRINGE_RIDE[1] - FRINGE_RIDE[0]), 0, 1)
    u = u * u * (3 - 2 * u)
    held = rim * (1 - u[:, None]) + cloth_weights(co) * u[:, None]
    held[:, DANGLE] = 0
    held /= np.maximum(held.sum(1, keepdims=True), 1e-12)
    W = held * (1 - d[:, None])
    W[:, B[bone]] = d
    put(fr, W)
    # its swing bone hangs from the upper arm, under which most of the strands lie
    bpy.context.view_layer.objects.active = rig
    for o in sc.objects:
        o.select_set(o == rig)
    bpy.ops.object.mode_set(mode='EDIT')
    rig.data.edit_bones[bone].parent = rig.data.edit_bones['upperarm_' + s]
    bpy.ops.object.mode_set(mode='OBJECT')
print('fringe: swing share %.2f, riding the cloth over %.1f..%.1f of the strands' % (FRINGE_SHARE, *FRINGE_RIDE))

# ---------------------------------------------------------------- 6. spurs and soles with the boots
for s in 'lr':
    boot = bpy.data.objects.get('Boot_' + s)
    if not boot:
        continue
    bc, bw = coords(boot), weights(boot)
    me = boot.data
    me.calc_loop_triangles()
    bt = np.zeros(len(me.loop_triangles) * 3, np.int32); me.loop_triangles.foreach_get('vertices', bt)
    bt = bt.reshape(-1, 3)
    btree = BVHTree.FromPolygons([Vector(c) for c in bc], bt.tolist(), all_triangles=True)
    for name in ('Spur_' + s, 'Sole_' + s):
        ob = bpy.data.objects.get(name)
        if not ob:
            continue
        W = np.zeros((len(ob.data.vertices), len(BONES)))
        for i, p in enumerate(coords(ob)):
            W[i] = bw[bt[btree.find_nearest(Vector(p))[2]]].mean(0)
        if name.startswith('Spur'):
            W[:] = W.mean(0)
        put(ob, W)

# ---------------------------------------------------------------- 7. the eyelids
def lid_dir(axes, az, el):
    lat, fwd, up = axes
    return Matrix.Rotation(math.radians(el), 3, -lat) @ (Matrix.Rotation(math.radians(az), 3, up) @ fwd)


def lid_grid(c, R, axes, tree):
    """The skin's distance off the eyeball (m; minus in the opening, where it is sunk under the ball) along rays from
    its centre, over azimuth x elevation (degrees, LID_AZ x LID_EL)."""
    gap = np.full((len(LID_AZ), len(LID_EL)), 1.0)
    for i, az in enumerate(LID_AZ):
        for j, el in enumerate(LID_EL):
            hit = tree.ray_cast(c, lid_dir(axes, az, el), 0.05)
            if hit[0] is not None:
                gap[i, j] = hit[3] - R
    return gap


def eyelid(s, c, R, axes, tree, gap, uv_at):
    """A lid for eye s: a strip of sphere LID_R outside the eyeball, at rest under the skin over the opening (its edge
    where the skin stands LID_GAP off the ball); turned down about the eye's centre by the blink it covers the opening
    and runs LID_TUCK on under the lower lid. -> (vertices, faces, uvs, blink degrees)"""
    mid = np.where(np.abs(LID_EL) <= 25)[0]
    cols = []
    for i, az in enumerate(LID_AZ):
        j0 = mid[np.argmin(gap[i, mid])]  # the opening's middle in this column (by the corners it is not level)
        if gap[i, j0] >= 0:
            continue
        j_u = j0
        while j_u + 1 < len(LID_EL) and gap[i, j_u + 1] < 0:
            j_u += 1
        j_l = j0
        while j_l > 0 and gap[i, j_l - 1] < 0:
            j_l -= 1
        j_e = j_u + 1
        while j_e + 1 < len(LID_EL) and gap[i, j_e] < LID_GAP:
            j_e += 1
        cols.append((az, LID_EL[j_u], LID_EL[j_l], LID_EL[j_e]))
    step = LID_AZ[1] - LID_AZ[0]
    every = max(1, int(round(LID_STEP / step)))
    pick = cols[::every]
    if pick[-1] is not cols[-1]:
        pick.append(cols[-1])
    # past the corners a little, the corner's lines kept
    cols = [(pick[0][0] - LID_STEP,) + pick[0][1:]] + pick + [(pick[-1][0] + LID_STEP,) + pick[-1][1:]]
    blink = max(e - l for _, _, l, e in cols) + LID_TUCK
    span = blink + LID_TOP
    rows = int(math.ceil(span / LID_STEP)) + 1
    verts, uvs = [], []
    az_m, u_m = min(cols, key=lambda col: abs(col[0]))[:2]
    lash, skin = (uv_at(c, lid_dir(axes, az_m, u_m + d)) for d in LID_UV)
    for az, u, l, e in cols:
        for r in range(rows):
            t = r / (rows - 1)
            verts.append(c + lid_dir(axes, az, e + span * t) * (R + LID_R))
            uvs.append(lash if r == 0 else skin)
    faces = []
    for a in range(len(cols) - 1):
        for r in range(rows - 1):
            k = a * rows + r
            faces.append((k, k + 1, k + rows + 1, k + rows))
    # checks: under the skin at rest; shut, under it wherever it is not over the opening
    rot = Matrix.Rotation(math.radians(blink), 3, axes[0])
    worst_rest = worst_shut = 1.0
    for v in verts:
        d = v - c
        hit = tree.ray_cast(c, d.normalized(), 0.05)
        worst_rest = min(worst_rest, (hit[3] if hit[0] else 1.0) - d.length)
        d2 = rot @ d
        hit = tree.ray_cast(c, d2.normalized(), 0.05)
        if hit[0] is not None and hit[3] > R:
            worst_shut = min(worst_shut, hit[3] - d2.length)
    print('eyelid %s: %d x %d, blink %.1f deg; under the skin by %.2f mm at least at rest, %.2f mm shut'
          % (s, len(cols), rows, blink, worst_rest * 1000, worst_shut * 1000))
    return verts, faces, uvs, blink


head = bpy.data.objects.get('Head')
if head and 'EYE_R' in sc['head']:
    hd = sc['head'].to_dict()
    mw = rig.matrix_world
    bl = rig.data.bones
    lat = (mw.to_3x3() @ (bl['eye_l'].head_local - bl['eye_r'].head_local)).normalized()
    fwd = lat.cross(Vector((0, 0, 1))).normalized()
    axes = (lat, fwd, lat.cross(fwd).normalized())
    hm = head.data
    hcos = [head.matrix_world @ v.co for v in hm.vertices]
    tree = BVHTree.FromPolygons(hcos, [tuple(p.vertices) for p in hm.polygons])
    uvl = hm.uv_layers.active.data

    def uv_at(c, d):
        hit = tree.ray_cast(c, d, 0.05)
        poly = hm.polygons[hit[2]]
        w = poly_3d_calc([hcos[i] for i in poly.vertices], hit[0])
        return sum((Vector(uvl[li].uv) * wi for li, wi in zip(poly.loop_indices, w)), Vector((0, 0)))
    verts, faces, uvs, groups = [], [], [], []
    for s in 'lr':
        c = mw @ bl['eye_' + s].head_local
        R = hd['EYE_R'][s]
        v, f, u, blink = eyelid(s, c, R, axes, tree, lid_grid(c, R, axes, tree), uv_at)
        base = len(verts)
        verts += v
        uvs += u
        faces += [tuple(k + base for k in q) for q in f]
        groups += ['lid_upper_' + s] * len(v)
        hd['BLINK_' + s.upper()] = blink
    sc['head'] = hd
    old = bpy.data.objects.get('Eyelids')
    if old:
        bpy.data.objects.remove(old)
    me = bpy.data.meshes.new('Eyelids')
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.uv_layers.new(name=hm.uv_layers.active.name)
    for poly in me.polygons:
        poly.use_smooth = True
        for li in poly.loop_indices:
            me.uv_layers[0].data[li].uv = uvs[me.loops[li].vertex_index]
    me.materials.append(hm.materials[0])
    lids = bpy.data.objects.new('Eyelids', me)
    sc.collection.objects.link(lids)
    for s in 'lr':
        lids.vertex_groups.new(name='lid_upper_' + s).add(
            [i for i, g in enumerate(groups) if g == 'lid_upper_' + s], 1.0, 'REPLACE')
    lids.modifiers.new('Armature', 'ARMATURE').object = rig
    # the skin's own upper lids stay where they are
    WH = weights(head)
    for s in 'lr':
        WH[:, B['head']] += WH[:, B['lid_upper_' + s]]
        WH[:, B['lid_upper_' + s]] = 0
    put(head, WH)
    print('blink: l %.1f, r %.1f deg' % (hd['BLINK_L'], hd['BLINK_R']))

# ---------------------------------------------------------------- 8. the mouth
if head:
    WH = weights(head)
    J = WH[:, B['jaw']].copy()
    ed = np.zeros(len(head.data.edges) * 2, np.int32); head.data.edges.foreach_get('vertices', ed)
    ed = ed.reshape(-1, 2)
    CH = coords(head)
    line = CH[ed[np.abs(J[ed[:, 0]] - J[ed[:, 1]]) > 0.3]].reshape(-1, 3)  # the lips' meeting: the jaw's step
    if len(line):
        lt = KDTree(len(line))
        for i, c in enumerate(line):
            lt.insert(c, i)
        lt.balance()
        d = np.array([lt.find(c)[2] for c in CH])
        free = d < MOUTH_R
        deg = np.bincount(ed.ravel(), minlength=len(J)).astype(float)
        J1 = J.copy()
        for _ in range(MOUTH_ROUNDS):
            acc = np.zeros_like(J1)
            np.add.at(acc, ed[:, 0], J1[ed[:, 1]]); np.add.at(acc, ed[:, 1], J1[ed[:, 0]])
            J1 = np.where(free, acc / np.maximum(deg, 1), J1)
        WH[:, B['head']] += J - J1
        WH[:, B['jaw']] = J1
        put(head, WH)
        print('mouth: jaw eased over %d vertices round the lips' % int(free.sum()))

bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
print('saved', OUT, os.path.getsize(OUT))

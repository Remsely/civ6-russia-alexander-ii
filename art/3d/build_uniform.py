# Uniform without details (tunic with skirt, trousers) built from the MPFB body surface.
# blender -b art/3d/alexander_assembly.blend --python art/3d/build_uniform.py
# Writes art/3d/alexander_rest.blend: only the 'Human' scene (rig, body, uniform); the source file is left untouched.
# MPFB space: metres, Z up, the human faces -Y, A-pose rest. Clothes are made in the rest pose and skinned to the same
# 53-bone game_engine skeleton, so every animation of the body drives them too.
import bpy, bmesh, math, os, sys
import mathutils.geometry as mg
from collections import defaultdict
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'alexander_rest.blend')  # in the rest pose; build_pose.py poses it into alexander_leader.blend
sys.path.insert(0, HERE)
import head_shape  # noqa: E402
import mat_util  # noqa: E402

# Alexander's build (alexander_ii_full.png): a big chest and broad shoulders over a waist the belt can take in, a
# V rather than a barrel. MPFB macros and extra targets from MPFB's library, applied to the 'Human' basemesh before
# anything is measured; then his head (head_shape.py) and a neck for the collar; the rig is refitted to the new shape.
HEAD_SCALE = 1.0
NECK_LONGER = 0.6
BODY_MACROS = {'weight': 0.85, 'muscle': 0.7}
BODY_TARGETS = {'torso/torso-scale-depth-incr': 0.4, 'torso/measure-shoulder-dist-incr': 0.6,
                'torso/torso-scale-horiz-incr': 0.35, 'torso/measure-bust-circ-incr': 0.3,
                # the portrait's head is 1/7.7 of his height, MPFB's 1/8.6: a bigger head (the generated one follows it)
                'head/head-scale-vert-incr': HEAD_SCALE, 'head/head-scale-horiz-incr': HEAD_SCALE,
                'head/head-scale-depth-incr': HEAD_SCALE,
                # a longer neck: the portrait's chin is ~8 cm over the shoulders at the collar, room for its tall collar
                'neck/measure-neck-height-incr': NECK_LONGER}

# Heights from alexander_ii_full.png scaled to the 2.07 m MPFB figure (feet 0, crown 2.07).
# The tunic's own standing collar (the dark collar seen between the halves of the red one, which build_details.py lays
# over it): its top runs round the neck under the jaw, a little higher at the back. Set from the chin once the head is
# on (shape_body).
STAND_BELOW_CHIN, STAND_BACK_RISE = 0.022, 0.015
STAND_TOP_FRONT, STAND_TOP_BACK = 1.795, 1.85
STAND_OFF = 0.006                 # off the neck: its narrowest outline over NECK_OUTLINE_ZS (the chin widens the top)
NECK_OUTLINE_ZS = (1.75, 1.77, 1.79)
WAIST_Z = 1.325                   # belt line (its centre 3 cm below: 1.295 in the portrait): the torso part of the tunic ends just below, the skirt starts just above
BELT_H, BELT_N = 0.058, 96        # belt over the waist seam (WAIST_Z - 0.03): height; directions of its profile
HEM_Z = 0.86                      # tunic hem, mid-thigh
ANKLE_Z = 0.12                    # trousers end, inside the boot
BOOT_TOP = 0.45                   # top of the boot shafts: the trousers are tucked in below it
SLEEVE_T = 0.95                   # sleeve end along the forearm (0 elbow, 1 wrist)
TUNIC_OFF, TROUSERS_OFF = 0.028, 0.015
SHOULDER_OFF = 0.012              # tunic offset over the shoulders (above the armpits)
SLEEVE_EASE, CUFF_EASE = 0.006, 0.014  # sleeves: round tubes this much looser than the arm; cuff off the wrist
SKIRT_EASE, SKIRT_FLARE = 0.008, 0.035  # skirt clearance over hips and thighs, extra radius at the hem
TROUSER_EASE = 1.08                # trouser leg radius over the mid-thigh
TROUSER_TAPER = 0.85              # straight trouser leg: radius at the ankle relative to the top of the thigh
CLOTH_THICK = 0.006
WELD = 0.007                      # body vertices closer than this are merged in the clothes
WAIST_GAP, WAIST_TAPER = 0.012, 0.015 # front pulled in from the chest to the belt by up to WAIST_TAPER
CHEST_GAP = 0.02                  # cloth (wool and lining) over the ironed chest
SKIN_GAP = 0.008                  # minimum cloth-to-skin distance (skinning moves them apart unevenly)
FLAP_X, FLAP_STEP = -0.02, 0.003  # closure edge: 2 cm to the wearer's right, flap lifted 3 mm
# Texture: dark green-black wool of the Imperial uniform, red piping (linear RGB); widths are half-widths in metres.
TEX = 2048
TEX_OUT = os.path.join(HERE, 'textures', 'uniform_albedo.png')
CLOTH_RGB = (0.0065, 0.007, 0.0105)
PIPING_RGB = (0.50, 0.012, 0.010)
PIPING_W, STRIPE_W, CUFF_T = 0.007, 0.012, 0.30
WOOL_REPEATS, WOOL_CONTRAST = 10, 0.22  # textures/gen/wool.png over the UVs (~15 cm a tile), its weave's strength
NORMAL_OUT = os.path.join(HERE, 'textures', 'uniform_normal.png')
WOOL_H, PIPING_H = 0.25, 2.5        # px of relief: the weave; the piping, a cord sewn into the seams
WOOL_SHEEN, SHEEN_TINT = 0.25, (0.04, 0.045, 0.07)  # broadcloth's fuzz at grazing angles: a faint dark blue (the portrait's cloth is near black)
PLEAT_ANGLE = 90                  # degrees from the front centre to the piped pleats of the skirt (at the sides)

sc = bpy.data.scenes['Human']
bpy.context.window.scene = sc
for s in list(bpy.data.scenes):
    if s != sc:
        bpy.data.scenes.remove(s)
h, rig = bpy.data.objects['Human'], bpy.data.objects['HumanRig']
for name in ('Body', 'LEAD_REMSELY_TEST', 'LeaderCameraRig', 'Tunic', 'Trousers', 'BodyUnder'):
    o = bpy.data.objects.get(name)
    if o and name != 'LEAD_REMSELY_TEST':
        bpy.data.objects.remove(o)
root = bpy.data.objects.get('LEAD_REMSELY_TEST')
if root:
    rig.parent = None
    bpy.data.objects.remove(root)
# Modelling happens in the rest pose (MPFB's A-pose): no test animation on the rig, no posed bones.
if rig.animation_data:
    rig.animation_data_clear()
for pb in rig.pose.bones:
    pb.matrix_basis.identity()



def shape_body():
    from bl_ext.blender_org import mpfb
    from bl_ext.blender_org.mpfb.services.targetservice import TargetService
    from bl_ext.blender_org.mpfb.services.humanservice import HumanService
    for k, v in BODY_MACROS.items():
        h['MPFB_HUM_' + k] = v
    TargetService.reapply_macro_details(h)
    keys = h.data.shape_keys.key_blocks
    for name, val in BODY_TARGETS.items():
        nm = os.path.basename(name)
        if keys.get(nm):
            keys[nm].value = val
        else:
            TargetService.load_target(h, os.path.join(os.path.dirname(mpfb.__file__), 'data', 'targets', name + '.target.gz'),
                                      weight=val, name=nm)
    for nm in ('measure-neck-circ-incr',):  # targets of earlier versions, now done by head_shape.fit_neck
        if keys.get(nm):
            keys[nm].value = 0.0
    head_shape.straighten(h)
    head_shape.flatten_back(h)
    HumanService.refit(h)
    head_shape.fit(h)
    global STAND_TOP_FRONT, STAND_TOP_BACK
    chin = float(head_shape.LAST['landmarks']['chin'][2])
    STAND_TOP_FRONT = chin - STAND_BELOW_CHIN
    STAND_TOP_BACK = STAND_TOP_FRONT + STAND_BACK_RISE
    print('stand collar: top %.3f front, %.3f back' % (STAND_TOP_FRONT, STAND_TOP_BACK))
    neck = rig.data.bones['neck_01'].head_local
    head_shape.fit_neck(h, (neck.x, neck.y), chin, STAND_TOP_FRONT, STAND_TOP_BACK)
    head_shape.slope_shoulders(h)
    HumanService.refit(h)
    head_shape.face_weights(h)
    sc['head'] = dict(T=[list(r) for r in head_shape.LAST['T']], CHIN_Z=float(head_shape.LAST['landmarks']['chin'][2]))


shape_body()

# Body in the rest pose with the current MPFB shape (shape keys + mask of helper geometry).
rig.data.pose_position = 'REST'
dg = bpy.context.evaluated_depsgraph_get()
body_me = bpy.data.meshes.new_from_object(h.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
rig.data.pose_position = 'POSE'
vg_names = [g.name for g in h.vertex_groups]
gi = {n: i for i, n in enumerate(vg_names)}


def iron_chest(me):
    """Iron the chest of the body itself - pectorals and nipples (the skin there is hidden under the tunic anyway), so
    no step that builds cloth from the body can bring them back: the front of the chest is replaced by a heavily
    smoothed copy, fading out towards the armpits, the collarbones and the belly."""
    bm = bmesh.new(); bm.from_mesh(me)
    orig = [v.co.copy() for v in bm.verts]
    for _ in range(40):
        bmesh.ops.smooth_vert(bm, verts=bm.verts[:], factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    for v, c in zip(bm.verts, orig):
        k = (smoothstep(-abs(c.x), -0.21, -0.15) * smoothstep(c.z, 1.30, 1.38) * smoothstep(-c.z, -1.70, -1.64)
             * smoothstep(-c.y, 0.0, 0.06))
        v.co = c.lerp(v.co, k)
    bm.to_mesh(me); bm.free()


def smoothstep(x, a, b):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


iron_chest(body_me)
bones = {b.name: (rig.matrix_world @ b.head_local, rig.matrix_world @ b.tail_local) for b in rig.data.bones}


def wsum(v, names):
    return sum(g.weight for g in v.groups if vg_names[g.group] in names)


HAND = {n for n in gi if n.startswith(('hand_', 'index_', 'middle_', 'pinky_', 'ring_', 'thumb_'))}
FOOT = {'foot_l', 'foot_r', 'ball_l', 'ball_r'}
ARM = {'upperarm_l', 'upperarm_r', 'lowerarm_l', 'lowerarm_r'}


def forearm_t(co, side):
    a, b = bones['lowerarm_' + side]
    d = b - a
    return (co - a).dot(d) / d.length_squared


def cut_body():
    """Body with clean cut lines (edge loops) at the belt, ankles and sleeve ends."""
    bm = bmesh.new(); bm.from_mesh(body_me)
    planes = [((0, 0, WAIST_Z - 0.03), (0, 0, 1)), ((0, 0, ANKLE_Z), (0, 0, 1))]
    for s in 'lr':
        a, b = bones['lowerarm_' + s]
        planes.append((a + (b - a) * SLEEVE_T, (b - a).normalized()))
    for co, no in planes:
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=co, plane_no=no)
    me = bpy.data.meshes.new('BodyCut'); bm.to_mesh(me); bm.free()
    return me


cut_me = cut_body()


def region(p):
    """'tunic', 'trousers' or None (skin stays visible) for a face of the cut body."""
    c = p.center
    vs = [cut_me.vertices[i] for i in p.vertices]
    w = lambda names: sum(wsum(v, names) for v in vs) / len(vs)
    if w(ARM) + w(HAND) > 0.5:
        return 'tunic' if forearm_t(c, 'l' if c.x > 0 else 'r') < SLEEVE_T else None
    if c.z < ANKLE_Z or c.z > stand_top(c):
        return None
    return 'tunic' if c.z > WAIST_Z - 0.03 else 'trousers'


NECK_AXIS = bones['neck_01'][0].xy


def neck_outline(z, n=72):
    """Radius of the neck from NECK_AXIS per direction (n sectors), from the body edges crossing the plane z."""
    rs = [0.0] * n
    for e in body_me.edges:
        p, q = body_me.vertices[e.vertices[0]].co, body_me.vertices[e.vertices[1]].co
        if (p.z - z) * (q.z - z) < 0:
            x = (p + (q - p) * ((z - p.z) / (q.z - p.z))).xy - NECK_AXIS
            if x.length < 0.14:
                k = int((math.atan2(x.x, -x.y) % (2 * math.pi)) / (2 * math.pi) * n) % n
                rs[k] = max(rs[k], x.length)
    for k in range(n):  # empty sectors take their neighbours
        if rs[k] == 0:
            rs[k] = max(rs[k - 1], rs[(k + 1) % n])
    return rs


NECK_RS = [min(rs) for rs in zip(*(neck_outline(z) for z in NECK_OUTLINE_ZS))]
for _ in range(3):
    NECK_RS = [NECK_RS[k] * 0.5 + (NECK_RS[k - 1] + NECK_RS[(k + 1) % len(NECK_RS)]) * 0.25 for k in range(len(NECK_RS))]
print('neck outline', round(min(NECK_RS), 3), round(max(NECK_RS), 3))


def neck_sector(d):
    return int((math.atan2(d.x, -d.y) % (2 * math.pi)) / (2 * math.pi) * len(NECK_RS)) % len(NECK_RS)


def stand_top(c):
    """Top of the tunic's standing collar above c (by direction round the neck)."""
    d = c.xy - NECK_AXIS
    back = (1 + d.y / max(d.length, 1e-6)) / 2  # 0 front .. 1 back
    return STAND_TOP_FRONT + (STAND_TOP_BACK - STAND_TOP_FRONT) * back


freg = [region(p) for p in cut_me.polygons]


def leg_axis_point(co, s):
    pts = [bones['thigh_' + s][0], bones['calf_' + s][0], bones['calf_' + s][1]]
    best = None
    for a, b in zip(pts, pts[1:]):
        d = b - a
        p = a + d * max(0.0, min(1.0, (co - a).dot(d) / d.length_squared))
        if best is None or (co - p).length < (co - best).length:
            best = p
    return best


def loosen_legs(bm):
    """Straight trouser legs: push the leg surface out to a cylinder tapering from the thigh to the ankle."""
    top = {}
    for s in 'lr':
        rs = sorted((v.co - leg_axis_point(v.co, s)).length for v in bm.verts
                    if 0.74 < v.co.z < 0.80 and (v.co.x > 0) == (s == 'l'))  # mid-thigh, clear of the crotch
        top[s] = rs[len(rs) // 2] * TROUSER_EASE
    print('thigh radius', top)
    for v in bm.verts:
        blend = max(0.0, min(1.0, (1.08 - v.co.z) / 0.12)) * smoothstep(v.co.z, BOOT_TOP - 0.03, BOOT_TOP + 0.07)
        if blend == 0:
            continue
        s = 'l' if v.co.x > 0 else 'r'
        p = leg_axis_point(v.co, s)
        r = v.co - p
        t = max(0.0, min(1.0, (v.co.z - ANKLE_Z) / (0.95 - ANKLE_Z)))
        target = top[s] * (TROUSER_TAPER + (1 - TROUSER_TAPER) * t)
        if r.length < target:
            v.co = v.co.lerp(p + r.normalized() * target, blend)


def ray_hull(hull, c, d):
    """Distance from c along unit direction d to the convex polygon hull."""
    best = 0.0
    for i in range(len(hull)):
        r = mg.intersect_line_line_2d(c, c + d * 3.0, hull[i], hull[(i + 1) % len(hull)])
        if r is not None:
            best = max(best, (r - c).length)
    return best


_hulls = {}


def hull_at(z):
    """Convex hull of the body slice at height z without arms and hands (both legs together below the crotch)."""
    key = round(z, 2)
    if key not in _hulls:
        pts = [Vector((p.x, p.y)) for p in TRUNK_PTS if abs(p.z - key) < 0.012]
        _hulls[key] = [pts[i] for i in mg.convex_hull_2d(pts)] if len(pts) > 2 else None
    return _hulls[key]


def arm_weight(v, dl):
    return sum(w for g, w in v[dl].items() if vg_names[g] in ARM or vg_names[g] in HAND)


def convexify_torso(bm):
    """Cloth spans the hollows: each torso slice is pushed out to the convex hull of the same slice of the (already
    inflated and smoothed) cloth. The hull of the cloth, not of the body: the body's nipples would come back as bumps."""
    dl = bm.verts.layers.deform.active
    trunk = [v.co.copy() for v in bm.verts if arm_weight(v, dl) < 0.3]
    hulls = {}
    for v in bm.verts:
        k = smoothstep(0.6 - arm_weight(v, dl), 0.0, 0.4)  # 1 on the torso, fading out into the sleeves
        if k == 0:
            continue
        key = round(v.co.z, 2)
        if key not in hulls:
            pts = [q.xy for q in trunk if abs(q.z - key) < 0.012]
            hulls[key] = [pts[i] for i in mg.convex_hull_2d(pts)] if len(pts) > 2 else None
        hull = hulls[key]
        if not hull:
            continue
        c = sum(hull, Vector((0.0, 0.0))) / len(hull)
        d = v.co.xy - c
        if d.length < 1e-6:
            continue
        target = ray_hull(hull, c, d.normalized())
        if target > d.length:
            v.co.xy = c + d.normalized() * (d.length + (target - d.length) * k)


def fill_vertical(bm):
    """Cloth also spans vertical hollows: on the chest it falls straight from the pectorals to the belly (no fold under
    the breast), on the back from the shoulder blades to the waist. Per 1.5 cm column the front (back) profile is
    pushed out to its upper convex envelope."""
    dl = bm.verts.layers.deform.active
    cross = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    for sign in (-1, 1):  # front faces -Y
        cols = defaultdict(list)
        for v in bm.verts:
            if sign * v.co.y > 0 and v.co.z > WAIST_Z - 0.06 and arm_weight(v, dl) < 0.3:
                cols[round(v.co.x / 0.015)].append(v)
        for col in cols.values():
            hull = []
            for q in sorted((v.co.z, sign * v.co.y) for v in col):
                while len(hull) >= 2 and cross(hull[-2], hull[-1], q) >= 0:
                    hull.pop()
                hull.append(q)
            zs, fs = [q[0] for q in hull], [q[1] for q in hull]
            for v in col:
                f = float(np.interp(v.co.z, zs, fs))
                if sign * v.co.y < f:
                    v.co.y = sign * f


def upper_envelope(pts):
    """Upper convex envelope of (t, f) points as sorted (ts, fs) - the line a cloth stretched over them would take."""
    cross = lambda o, p, q: (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])
    hull = []
    for q in sorted(pts):
        while len(hull) >= 2 and cross(hull[-2], hull[-1], q) >= 0:
            hull.pop()
        hull.append(q)
    return [q[0] for q in hull], [q[1] for q in hull]


def tailored_front(bm):
    """The front of the tunic from the belt to the collarbones is laid like stretched wool over the ironed body: in
    every vertical column the cloth runs from the collar over the chest and then in towards the belt (no sag
    under the chest, no bosom), across every height one arc spans the sternum; CHEST_GAP off the body."""
    dl = bm.verts.layers.deform.active
    z0, z1, xmax = WAIST_Z - 0.06, 1.76, 0.2
    skin = [p for p in SMOOTH_TRUNK if p.y < 0 and abs(p.x) < xmax + 0.02 and z0 - 0.02 < p.z < z1 + 0.02]
    xs = np.arange(-xmax, xmax + 1e-6, 0.01)
    zs = np.arange(z0, z1 + 1e-6, 0.01)
    grid = np.zeros((len(zs), len(xs)))
    for j, x in enumerate(xs):  # vertical: per column
        col = [(p.z, -p.y) for p in skin if abs(p.x - x) < 0.008]
        tz, tf = upper_envelope([(z, f + CHEST_GAP) for z, f in col])
        env = np.interp(zs, tz, tf)
        # Below the fullest point of the chest the cloth is pulled in towards the belt (the tunic is cut to the waist),
        # as far as the belly lets it: never closer than WAIST_GAP to the body. Not a straight drop: that hangs.
        floor = np.full(len(zs), -1.0)
        for z, f in col:
            i = int(round((z - z0) / 0.01))
            if 0 <= i < len(zs):
                floor[i] = max(floor[i], f + WAIST_GAP)
        ok = floor > -1
        floor = np.interp(zs, zs[ok], floor[ok])
        top = int(np.argmax(env))
        for i in range(top):
            t = (zs[top] - zs[i]) / (zs[top] - z0)
            env[i] = max(floor[i], min(env[i], env[top] - WAIST_TAPER * smoothstep(t, 0.0, 1.0)))
        grid[:, j] = env
    across = np.abs(xs) <= 0.17
    for i in range(len(zs)):  # horizontal: per height one arc f = a - b*x^2 lifted over the columns. A stretched
        # envelope would be a flat plate between the pectorals with rounded corners that read as two bumps.
        b = min(max(0.0, -np.polyfit(xs[across] ** 2, grid[i][across], 1)[0]), 4.0)
        grid[i] = (grid[i][across] + b * xs[across] ** 2).max() - b * xs ** 2
    for _ in range(3):  # soften the envelope's corners
        grid[1:-1] = (grid[:-2] + grid[1:-1] + grid[2:]) / 3
    front = [v for v in bm.verts if v.co.y < 0 and abs(v.co.x) < xmax and z0 < v.co.z < z1 and arm_weight(v, dl) < 0.3]

    def onto_front():
        for v in front:
            i = min(max((v.co.z - z0) / 0.01, 0), len(zs) - 1.001)
            i0 = int(i); fr = i - i0
            f = np.interp(v.co.x, xs, grid[i0] * (1 - fr) + grid[i0 + 1] * fr)
            w = smoothstep(-abs(v.co.x), -0.19, -0.12) * smoothstep(-v.co.z, -1.75, -1.66)
            v.co.y += (-f - v.co.y) * w

    onto_front()
    # spread the vertices evenly over the new surface (the body's dense nipple/navel topology is crumpled there)
    inner = [v for v in front if not v.is_boundary]
    for _ in range(15):
        bmesh.ops.smooth_vert(bm, verts=inner, factor=0.5, use_axis_x=True, use_axis_y=False, use_axis_z=True)
        onto_front()


def cinch_waist(bm):
    """The tunic is cut to the waist and the belt takes it in: around the belt the cloth comes down to WAIST_GAP off
    the body, easing back out to the full chest and over the hips (the skirt grows from this loop)."""
    dl = bm.verts.layers.deform.active
    bm.normal_update()
    for v in bm.verts:
        # a narrow band at the belt; pulled in at the sides and the back, the front stays straight (a cinch reaching
        # up under the chest makes a bust)
        k = smoothstep(v.co.z, WAIST_Z - 0.06, WAIST_Z - 0.02) * smoothstep(-v.co.z, -(WAIST_Z + 0.10), -(WAIST_Z + 0.01))
        k *= smoothstep(0.3 - arm_weight(v, dl), 0.0, 0.2) * smoothstep(v.normal.y, -0.8, -0.2)
        if k == 0:
            continue
        loc, nrm, _, _ = SMOOTH_BVH.find_nearest(v.co)
        target = loc + nrm * WAIST_GAP
        if (v.co - loc).dot(nrm) > WAIST_GAP:
            v.co = v.co.lerp(target, k)


def fit_neckline(bm):
    """Around the neck the tunic lies on the body (SHOULDER_OFF off it): the slice hulls of the cloth at these heights
    span the neck and the shoulders, which made the neckline stand off the neck like a flared collar."""
    dl = bm.verts.layers.deform.active
    for v in bm.verts:
        k = smoothstep(v.co.z, 1.66, 1.73) * smoothstep(0.3 - arm_weight(v, dl), 0.0, 0.2)
        if k == 0:
            continue
        loc, nrm, _, _ = SMOOTH_BVH.find_nearest(v.co)
        v.co = v.co.lerp(loc + nrm * SHOULDER_OFF, k)


def stand_collar(bm):
    """Above the shoulders the tunic stands up as a collar: a smooth tube STAND_OFF round the neck, never inside the
    body where the shoulders rise into it."""
    for v in bm.verts:
        w = smoothstep(v.co.z, 1.70, 1.75)
        d = v.co.xy - NECK_AXIS
        if w == 0 or d.length > 0.2:
            continue
        dd = Vector((d.x, d.y, 0.0)).normalized()
        hit = BODY_BVH.ray_cast(Vector((NECK_AXIS.x, NECK_AXIS.y, v.co.z)), dd, 0.25)  # neck or shoulder, from inside
        target = max(NECK_RS[neck_sector(d)] + STAND_OFF, (hit[3] + SKIN_GAP) if hit[0] else 0.0)
        v.co.xy = NECK_AXIS + d.normalized() * (d.length + (target - d.length) * w)
    # a straight top edge: the ring under it is spread evenly between the edge and the cloth below
    edge = [v for v in bm.verts if v.is_boundary and v.co.z > 1.70]
    for v in edge:
        v.co.z = stand_top(v.co)
    for v in {e.other_vert(v) for v in edge for e in v.link_edges} - set(edge):
        top = stand_top(v.co)
        if v.co.z > top - 0.008:
            v.co.z = top - 0.008


def arm_axis(co, s):
    """Nearest point on the arm (shoulder -> elbow -> wrist) and its parameter u in 0..1 along the arm."""
    pts = [bones['upperarm_' + s][0], bones['lowerarm_' + s][0], bones['hand_' + s][0]]
    lens = [(b - a).length for a, b in zip(pts, pts[1:])]
    best, acc = None, 0.0
    for (a, b), ln in zip(zip(pts, pts[1:]), lens):
        t = max(0.0, min(1.0, (co - a).dot(b - a) / ln ** 2))
        p = a + (b - a) * t
        if best is None or (co - p).length < (co - best[0]).length:
            best = (p, (acc + t * ln) / sum(lens))
        acc += ln
    return best


def loosen_sleeves(bm):
    """Sleeves become round tubes: radius per slice = the fullest part of the arm there plus SLEEVE_EASE, tapering
    along the forearm into a cuff that sits CUFF_EASE off the wrist."""
    dl = bm.verts.layers.deform.active
    nb = 25
    for s in 'lr':
        vs = [(v, *arm_axis(v.co, s)) for v in bm.verts if (v.co.x > 0) == (s == 'l') and arm_weight(v, dl) > 0.3]
        bins = defaultdict(list)
        for v, p, u in vs:
            bins[min(int(u * nb), nb - 1)].append((BODY_BVH.find_nearest(v.co)[0] - p).length)
        body = {k: sorted(r)[int(len(r) * 0.8)] for k, r in bins.items()}
        keys = sorted(body)
        cuff = sorted(bins[keys[-1]] + bins[keys[-2]])[len(bins[keys[-1]] + bins[keys[-2]]) // 2] + CUFF_EASE
        # straight tube: the upper-arm radius narrowing evenly to the cuff, never tighter than the arm under it
        upper = sorted(r for k in keys if 0.15 < (k + 0.5) / nb < 0.4 for r in bins[k])
        top = upper[len(upper) // 2] + SLEEVE_EASE  # median: the deltoid and armpit would make a balloon
        prof = {}
        for k in keys:
            u = (k + 0.5) / nb
            prof[k] = max(top, body[k] + 0.012)  # straight: one width from the shoulder to the cuff
        print('sleeve', s, 'radius %.3f' % top)
        for v, p, u in vs:
            k = smoothstep(arm_weight(v, dl), 0.3, 0.7) * smoothstep(u, 0.0, 0.18)  # blend into the shoulder
            d = v.co - p
            target = prof[min(int(u * nb), nb - 1)]
            v.co = p + d.normalized() * (d.length + (target - d.length) * k)


def extrude_skirt(bm, rings=20):
    """The skirt continues the tunic below the waist: rings grown from the waist edge loop down to the hem, hanging over
    the hips and both thighs (never narrower than the ring above). Returns the new vertices with their 0..1 depth."""
    loop_edges = [e for e in bm.edges if e.is_boundary and all(v.co.z < WAIST_Z for v in e.verts)]
    adj = defaultdict(list)
    for e in loop_edges:
        a, b = e.verts
        adj[a].append(b); adj[b].append(a)
    start = next(iter(adj)); loop = [start]; prev = None
    while True:
        nxt = [w for w in adj[loop[-1]] if w is not prev][0]
        if nxt is start:
            break
        prev = loop[-1]; loop.append(nxt)
    print('waist loop', len(loop), 'of', len(loop_edges))
    c = sum((v.co.xy for v in loop), Vector((0.0, 0.0))) / len(loop)
    dirs = [(v.co.xy - c).normalized() for v in loop]
    radius = [(v.co.xy - c).length for v in loop]
    # radius profile per column: clear the body, never narrower than above, then eased so the cloth falls smoothly
    # from the waist over the hips instead of kinking like a lampshade
    prof = [[radius[j]] for j in range(len(loop))]
    for i in range(1, rings):
        t = i / (rings - 1)
        for j, v0 in enumerate(loop):
            hull = hull_at(v0.co.z + (HEM_Z - v0.co.z) * t)
            target = ray_hull(hull, c, dirs[j]) + TUNIC_OFF + SKIRT_EASE if hull else 0.0
            prof[j].append(max(prof[j][-1], target))
    for col in prof:
        for _ in range(12):
            col[1:-1] = [max(col[k], (col[k - 1] + col[k] + col[k + 1]) / 3) if k > 2 else (col[k - 1] + col[k] + col[k + 1]) / 3
                         for k in range(1, len(col) - 1)]
        col[-1] = max(col[-1], col[-2])
    for col in prof:
        for i in range(1, rings):
            col[i] += SKIRT_FLARE * (i / (rings - 1)) ** 1.6
    rows, out = [loop], []
    for i in range(1, rings):
        t = i / (rings - 1)
        row = []
        for j, v0 in enumerate(loop):
            z = v0.co.z + (HEM_Z - v0.co.z) * t
            co = c + dirs[j] * prof[j][i]
            nv = bm.verts.new((co.x, co.y, z)); row.append(nv); out.append((nv, t))
        rows.append(row)
    new_faces = []
    for r0, r1 in zip(rows, rows[1:]):
        for j in range(len(loop)):
            j2 = (j + 1) % len(loop)
            new_faces.append(bm.faces.new((r0[j], r0[j2], r1[j2], r1[j])))
    bm.normal_update()
    f = new_faces[len(new_faces) // 2]
    if f.normal.xy.dot(f.calc_center_median().xy - c) < 0:
        bmesh.ops.reverse_faces(bm, faces=new_faces)
    inner = [v for row in rows[1:-1] for v in row]
    for _ in range(3):
        bmesh.ops.smooth_vert(bm, verts=inner, factor=0.5, use_axis_x=True, use_axis_y=True)
    # round off the turn from the cinched waist into the skirt: the waist loop itself and a few rings either side
    turn = [v for v in bm.verts if not v.is_boundary and WAIST_Z - 0.10 < v.co.z < WAIST_Z + 0.06]
    for _ in range(8):
        bmesh.ops.smooth_vert(bm, verts=turn, factor=0.5, use_axis_x=True, use_axis_y=True)
    return out


def overlap_front(bm):
    """Single-breasted closure: the wearer's left flap laps over the right and ends FLAP_X right of the centre (to the
    viewer's left), where the piping runs. The flap is lifted FLAP_STEP so its edge reads as a step in the cloth."""
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(FLAP_X, 0, 0), plane_no=(1, 0, 0))
    bm.normal_update()
    for v in bm.verts:
        if v.co.y < -0.03 and v.co.x > FLAP_X + 1e-4:
            v.co.y -= FLAP_STEP * smoothstep(-abs(v.co.x - FLAP_X), -0.12, -0.08)  # flap fades out towards the side


def belt_band(bm):
    """The belt draws the tunic in: on the belt's height the cloth is taken in to one profile all round - the body's
    outline there plus the cloth's offset at its tightest place - fading out above and below. The profile is kept
    (BELT_PROFILE) for build_details.py, which puts the belt on it, so it hugs the tunic at the back as well."""
    zc = WAIST_Z - 0.03
    hull = hull_at(zc)
    c = sum(hull, Vector((0.0, 0.0))) / len(hull)
    dirs = [Vector((math.sin(2 * math.pi * k / BELT_N), -math.cos(2 * math.pi * k / BELT_N))) for k in range(BELT_N)]
    body = [ray_hull(hull, c, d) for d in dirs]
    sector = lambda d: (math.atan2(d.x, -d.y) % (2 * math.pi)) / (2 * math.pi) * BELT_N
    cloth = [0.0] * BELT_N
    for v in bm.verts:
        if abs(v.co.z - zc) < 0.01 and abs(v.co.x) < 0.35:
            d = v.co.xy - c
            k = int(round(sector(d))) % BELT_N
            cloth[k] = max(cloth[k], d.length)
    fit = max(0.012, min(t - b for t, b in zip(cloth, body) if t > 0))
    prof = [b + fit for b in body]
    for _ in range(4):
        prof = [prof[k] * 0.5 + (prof[k - 1] + prof[(k + 1) % BELT_N]) * 0.25 for k in range(BELT_N)]
    half = BELT_H / 2 + 0.004
    for v in bm.verts:
        w = 1 - smoothstep(abs(v.co.z - zc), half, half + 0.03)
        if w <= 0 or abs(v.co.x) > 0.35:
            continue
        d = v.co.xy - c
        f = sector(d); k0 = int(f) % BELT_N
        target = prof[k0] + (prof[(k0 + 1) % BELT_N] - prof[k0]) * (f - int(f))
        if d.length > target:
            v.co.xy = c + d.normalized() * (d.length + (target - d.length) * w)
    print('belt fit %.3f, profile %.3f..%.3f' % (fit, min(prof), max(prof)))
    return dict(BELT_ZC=zc, BELT_H=BELT_H, BELT_C=(c.x, c.y), BELT_PROFILE=prof)


def extract(name, keep, offset, smooth):
    bm = bmesh.new(); bm.from_mesh(cut_me)
    drop = [f for f in bm.faces if not keep(freg[f.index])]
    bmesh.ops.delete(bm, geom=drop, context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    # Weld the body's micro-detail (nipple rings, navel): flattened, those tiny faces fold over and shade as dark dots.
    n = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=[v for v in bm.verts if not v.is_boundary], dist=WELD)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=1e-4)
    print(name, 'welded', n - len(bm.verts), 'vertices')
    # Inflate and iron out anatomy (nipples, navel, muscles); the tunic is then given its own volume.
    bm.normal_update()
    for v in bm.verts:
        k = 1.0 if name != 'Tunic' else 1 - (1 - SHOULDER_OFF / offset) * smoothstep(v.co.z, 1.58, 1.68)
        v.co += v.normal * offset * k  # thinner over the shoulders, or they balloon
    if name == 'Trousers':
        loosen_legs(bm)
    inner = [v for v in bm.verts if not v.is_boundary]
    for _ in range(smooth):
        bmesh.ops.smooth_vert(bm, verts=inner, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    if name == 'Tunic':
        chest = [v for v in inner if v.co.y < 0 and 1.40 < v.co.z < 1.72 and abs(v.co.x) < 0.2]
        for _ in range(smooth * 3):
            bmesh.ops.smooth_vert(bm, verts=chest, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
        convexify_torso(bm)
        fill_vertical(bm)
        tailored_front(bm)
        cinch_waist(bm)
        fit_neckline(bm)
        loosen_sleeves(bm)
        for _ in range(6):
            bmesh.ops.smooth_vert(bm, verts=inner, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    # Ragged face-level edges (neckline) become smooth curves: relax boundary vertices along their own loop.
    for _ in range(10):
        new = {}
        for v in bm.verts:
            if v.is_boundary:
                nb = [e.other_vert(v) for e in v.link_edges if e.is_boundary]
                if len(nb) == 2:
                    new[v] = v.co * 0.5 + (nb[0].co + nb[1].co) * 0.25
        for v, co in new.items():
            v.co = co
    for _ in range(2):  # only keep the cloth off the skin; a full offset would bring the anatomy back
        bm.normal_update()
        for v in bm.verts:
            loc, nrm, _, dist = SMOOTH_BVH.find_nearest(v.co)
            if loc is not None and (v.co - loc).dot(nrm) < offset * 0.4:
                v.co = loc + nrm * offset * 0.4
            loc, nrm, _, dist = BODY_BVH.find_nearest(v.co)  # and never closer than SKIN_GAP to the real skin
            if loc is not None and (v.co - loc).dot(nrm) < SKIN_GAP:
                v.co = loc + nrm * SKIN_GAP
        bmesh.ops.smooth_vert(bm, verts=inner, factor=0.3, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    if name == 'Trousers':  # under the skirt the waistband hugs the body, or it shows through the cinched tunic
        for v in bm.verts:
            k = smoothstep(v.co.z, WAIST_Z - 0.16, WAIST_Z - 0.08)
            if k > 0:
                loc, nrm, _, _ = SMOOTH_BVH.find_nearest(v.co)
                if (v.co - loc).dot(nrm) > 0.005:
                    v.co = v.co.lerp(loc + nrm * 0.005, k)
    if name == 'Tunic':
        stand_collar(bm)
        depth = bm.verts.layers.float.new('skirt_depth')  # 0 above the waist, 0..1 down the skirt; read for skinning
        for v, t in extrude_skirt(bm):
            v[depth] = t
        overlap_front(bm)
        BELT.update(belt_band(bm))
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob)
    for n in vg_names:
        ob.vertex_groups.new(name=n)
    return ob


def uniform_colour(pos, part):
    """Albedo (linear RGB) per surface point of the uniform in the rest pose: dark wool with red piping, cuffs and
    trouser stripes. Gold, collar and the rest are separate detail meshes, not painted."""
    x, y, z = pos[:, 0], pos[:, 1], pos[:, 2]
    red = np.zeros(len(pos), bool)
    coat = part < 2
    # piping down the front closure, from the collar to the hem
    red |= coat & (y < -0.03) & (x > FLAP_X - 0.002) & (x < FLAP_X + PIPING_W)  # along the flap edge
    # cuffs: the last CUFF_T of the forearm
    for s_ in 'lr':
        a, b = (np.array(v) for v in bones['lowerarm_' + s_])
        d = b - a
        t = (pos - a) @ d / (d @ d)
        radial = np.linalg.norm(pos - a - np.outer(t, d), axis=1)
        red |= (part == 0) & (t > SLEEVE_T - CUFF_T) & (t <= SLEEVE_T + 0.05) & (radial < 0.09)
    # lampas: a stripe down the outer seam of each trouser leg
    zs = [bones['thigh_l'][0].z, bones['calf_l'][0].z, bones['calf_l'][1].z][::-1]
    ys = [bones['thigh_l'][0].y, bones['calf_l'][0].y, bones['calf_l'][1].y][::-1]
    xs = [bones['thigh_l'][0].x, bones['calf_l'][0].x, bones['calf_l'][1].x][::-1]
    yc, xc = np.interp(z, zs, ys), np.interp(z, zs, xs)
    red |= (part == 2) & (np.abs(y - yc) < STRIPE_W) & (np.abs(x) > xc)  # outer side only
    # piping on the skirt's rear pleats, seen at the sides from the front: from the belt to the hem
    ang = np.degrees(np.arctan2(np.abs(x), -y))
    dist = np.radians(np.abs(ang - PLEAT_ANGLE)) * np.hypot(x, y)
    red |= coat & (z < WAIST_Z - 0.03) & (dist < PIPING_W)
    col = np.tile(np.array(CLOTH_RGB, np.float32), (len(pos), 1))
    col[red] = PIPING_RGB
    return col


def wool_detail():
    """The weave of the generated broadcloth (textures/gen/wool.png, seamless) as a brightness factor round 1, tiled
    WOOL_REPEATS times over the uniform's UVs (smart UV keeps the texel density even)."""
    img = bpy.data.images.load(os.path.join(HERE, 'textures', 'gen', 'wool.png'), check_existing=False)
    w, hh = img.size
    a = np.array(img.pixels[:], np.float32).reshape(hh, w, 4)[..., :3] @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    bpy.data.images.remove(img)
    a /= a.mean()
    ys = (np.arange(TEX) * WOOL_REPEATS * hh // TEX) % hh
    xs = (np.arange(TEX) * WOOL_REPEATS * w // TEX) % w
    return (1 + (a[np.ix_(ys, xs)] - 1) * WOOL_CONTRAST).astype(np.float32)


def paint_uniform(ob, mat):
    """Smart-UV the uniform and rasterise uniform_colour() into its albedo (supersampled, island edges dilated)."""
    for o in sc.objects:
        o.select_set(o == ob)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.004)
    bpy.ops.object.mode_set(mode='OBJECT')
    me = ob.data
    me.calc_loop_triangles()
    n = TEX * 2
    acc = np.zeros((n, n, 3), np.float32); cov = np.zeros((n, n), bool)
    uv = np.zeros(len(me.loops) * 2, np.float32); me.uv_layers.active.data.foreach_get('uv', uv); uv = uv.reshape(-1, 2) * n
    co = np.zeros(len(me.vertices) * 3, np.float32); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    part = np.zeros(len(me.polygons), np.int32); me.attributes['part'].data.foreach_get('value', part)
    for tri in me.loop_triangles:
        t_uv = uv[list(tri.loops)]; t_co = co[list(tri.vertices)]
        x0, y0 = np.floor(t_uv.min(0)).astype(int); x1, y1 = np.ceil(t_uv.max(0)).astype(int)
        xs, ys_ = np.meshgrid(np.arange(max(x0, 0), min(x1 + 1, n)), np.arange(max(y0, 0), min(y1 + 1, n)))
        px = np.stack([xs.ravel() + 0.5, ys_.ravel() + 0.5], 1)
        (ax, ay), (bx, by), (cx, cy) = t_uv
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-9:
            continue
        l1 = ((by - cy) * (px[:, 0] - cx) + (cx - bx) * (px[:, 1] - cy)) / den
        l2 = ((cy - ay) * (px[:, 0] - cx) + (ax - cx) * (px[:, 1] - cy)) / den
        l3 = 1 - l1 - l2
        inside = (l1 >= -0.02) & (l2 >= -0.02) & (l3 >= -0.02)
        if not inside.any():
            continue
        bary = np.stack([l1, l2, l3], 1)[inside]
        pos = bary @ t_co
        ix, iy = px[inside, 0].astype(int), px[inside, 1].astype(int)
        acc[iy, ix] = uniform_colour(pos, np.full(len(pos), part[tri.polygon_index]))
        cov[iy, ix] = True
    for _ in range(8):  # dilate islands so mip-mapping and filtering never pull in the empty background
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            src = np.roll(np.roll(cov, dy, 0), dx, 1); fill = src & ~cov
            acc[fill] = np.roll(np.roll(acc, dy, 0), dx, 1)[fill]; cov |= fill
    acc[~cov] = CLOTH_RGB
    img_px = acc.reshape(TEX, 2, TEX, 2, 3).mean((1, 3))
    wool = wool_detail()
    img_px *= wool[..., None]
    piping = (img_px[..., 0] > 0.1).astype(np.float32)  # the red (linear) of the piping and stripes
    height = mat_util.blur(piping, 2) * PIPING_H + (wool - 1) / WOOL_CONTRAST * WOOL_H
    img_px = np.where(img_px <= 0.0031308, img_px * 12.92, 1.055 * np.power(img_px, 1 / 2.4) - 0.055)  # to sRGB
    albedo = mat_util.save('Uniform_Albedo', img_px, TEX_OUT, 'sRGB')
    nrm = mat_util.save('Uniform_Normal', mat_util.normals(height) * 0.5 + 0.5, NORMAL_OUT, 'Non-Color')
    mat_util.material(mat.name, albedo, None, nrm, rough=0.95, sheen=WOOL_SHEEN, sheen_tint=SHEEN_TINT)
    print('painted', TEX_OUT)


TRUNK_PTS = [v.co.copy() for v in body_me.vertices if ANKLE_Z < v.co.z and wsum(v, ARM | HAND) < 0.3]
bmb = bmesh.new(); bmb.from_mesh(body_me)
BODY_BVH = BVHTree.FromBMesh(bmb)
# Ironed body for keeping the cloth off the skin: against the real one, nipples and muscles push bumps back into it.
for _ in range(15):
    bmesh.ops.smooth_vert(bmb, verts=bmb.verts[:], factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
SMOOTH_BVH = BVHTree.FromBMesh(bmb)
bmb.verts.ensure_lookup_table()
SMOOTH_TRUNK = [bmb.verts[i].co.copy() for i, v in enumerate(body_me.vertices) if wsum(v, ARM | HAND) < 0.3]
bmb.free()

BELT = {}
tunic = extract('Tunic', lambda r: r == 'tunic', TUNIC_OFF, 30)
trousers = extract('Trousers', lambda r: r == 'trousers', TROUSERS_OFF, 10)


# Tunic and trousers skinning: copy the body weights from the nearest surface point.
src = bpy.data.objects.new('BodyWeights', cut_me); sc.collection.objects.link(src)
for n in vg_names:
    src.vertex_groups.new(name=n)
for ob in (tunic, trousers):
    m = ob.modifiers.new('W', 'DATA_TRANSFER')
    m.object = src; m.use_vert_data = True; m.data_types_verts = {'VGROUP_WEIGHTS'}
    m.vert_mapping = 'POLYINTERP_NEAREST'
    m.layers_vgroup_select_src = 'ALL'; m.layers_vgroup_select_dst = 'NAME'
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.modifier_apply(modifier='W')
# Skirt skinning: pelvis at the waist, blending into the thigh of its side towards the hem (the cloth follows the leg
# halfway, so a step does not tear it). Extra skirt bones can be added later for secondary motion.
depth = [0.0] * len(tunic.data.vertices)
tunic.data.attributes['skirt_depth'].data.foreach_get('value', depth)
for idx, t in enumerate(depth):
    if t <= 0:
        continue
    co = tunic.data.vertices[idx].co
    for g in tunic.vertex_groups:
        g.remove([idx])
    side = abs(co.x) / (abs(co.x) + abs(co.y) + 1e-6)
    wt = 0.55 * t ** 1.5 * side
    tunic.vertex_groups['pelvis'].add([idx], 1.0 - wt, 'REPLACE')
    if wt > 0:
        tunic.vertex_groups['thigh_l' if co.x > 0 else 'thigh_r'].add([idx], wt, 'REPLACE')

# Join into one Uniform mesh, keep only deform groups, give it thickness and a cloth material.
for part, ob in ((0, tunic), (2, trousers)):  # face attribute for the texture painter below
    a = ob.data.attributes.new('part', 'INT', 'FACE')
    a.data.foreach_set('value', [part] * len(ob.data.polygons))
for o in sc.objects:
    o.select_set(o in (tunic, trousers))
bpy.context.view_layer.objects.active = tunic
bpy.ops.object.join()
uni = tunic; uni.name = uni.data.name = 'Uniform'
for g in list(uni.vertex_groups):
    if g.name not in bones:
        uni.vertex_groups.remove(g)
mat = bpy.data.materials.get('Uniform_Cloth') or bpy.data.materials.new('Uniform_Cloth')
mat.diffuse_color = (0.04, 0.045, 0.06, 1)
uni.data.materials.clear(); uni.data.materials.append(mat)
for p in uni.data.polygons:
    p.use_smooth = True
paint_uniform(uni, mat)  # on the single sheet: the inner layer added next reuses the same UVs
# thickness stays a modifier: build_pose.py simulates the single sheet as cloth and applies it after
sol = uni.modifiers.new('Thick', 'SOLIDIFY'); sol.thickness = CLOTH_THICK; sol.offset = -1; sol.use_rim = True

# Body under the clothes: drop faces hidden by the uniform (keeps hands, feet, neck, head), so nothing pokes through.
bm = bmesh.new(); bm.from_mesh(cut_me)
hidden = {f for f in bm.faces if freg[f.index] is not None}
for _ in range(2):  # keep a margin of two face rings under the cloth edges (sleeve ends, neckline, ankles)
    edge = {f for f in hidden if any(g not in hidden for v in f.verts for g in v.link_faces)}
    hidden -= edge
bmesh.ops.delete(bm, geom=list(hidden), context='FACES')
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
under_me = bpy.data.meshes.new('BodyUnder'); bm.to_mesh(under_me); bm.free()
bpy.data.objects.remove(src)
under = bpy.data.objects.new('BodyUnder', under_me); sc.collection.objects.link(under)
for n in vg_names:
    under.vertex_groups.new(name=n)
for g in list(under.vertex_groups):
    if g.name not in bones and g.name not in head_shape.FACE_BONES:
        under.vertex_groups.remove(g)
skin = bpy.data.materials.get('LEAD_REMSELY_TEST_Skin') or bpy.data.materials.new('Skin')
under.data.materials.clear(); under.data.materials.append(skin)
for ob in (uni, under):
    ob.modifiers.new('Armature', 'ARMATURE').object = rig
h.hide_set(True); h.hide_render = True
for ob in (uni, under):  # every vertex's weights sum to 1 (the importer does not normalise)
    bpy.context.view_layer.objects.active = ob
    for o in sc.objects:
        o.select_set(o == ob)
    bpy.ops.object.vertex_group_normalize_all(lock_active=False)

print('uniform verts', len(uni.data.vertices), 'faces', len(uni.data.polygons))
# Measurements the details (build_details.py) are fitted to.
sc['uniform'] = dict(WAIST_Z=WAIST_Z, HEM_Z=HEM_Z, SLEEVE_T=SLEEVE_T, CUFF_T=CUFF_T, FLAP_X=FLAP_X, BOOT_TOP=BOOT_TOP,
                     ANKLE_Z=ANKLE_Z, STAND_TOP_FRONT=STAND_TOP_FRONT, STAND_TOP_BACK=STAND_TOP_BACK,
                     NECK_AXIS=tuple(NECK_AXIS), **BELT)
print('body under verts', len(under.data.vertices))
bpy.ops.outliner.orphans_purge(do_recursive=True)
for screen in bpy.data.screens:  # open with the texture visible (Solid mode shows only the flat material colour)
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            area.spaces.active.shading.type = 'MATERIAL'
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
print('saved', OUT, os.path.getsize(OUT))

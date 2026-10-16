# Uniform details fitted to the rest-pose uniform of alexander_rest.blend (run build_uniform.py first):
# standing collar, buttons, belt with buckle, cuffs with flaps, riding boots. Shapes and textures follow
# art/source/alexander_ii_full.png and alexander_ii_short.png; the embroidery, galloon, buckle and cuff flap are cut
# from those pictures by extract_ref_textures.py (textures/ref_*.png).
# blender -b art/3d/alexander_rest.blend --python art/3d/build_details.py   (rewrites the file in place)
# Every detail is skinned to the same skeleton. Rigid parts (buttons, buckle, flaps) take the weights of one surface
# point, so they ride the cloth without bending; soft parts blend the weights of the cloth or body under them.
# All details share one material and one texture atlas (albedo + metal/roughness), laid out in ATLAS.
import bpy, bmesh, math, os, sys
import numpy as np
import mathutils.geometry as mg
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mat_util  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'alexander_rest.blend')  # in the rest pose; build_pose.py poses it into alexander_leader.blend
TEXDIR = os.path.join(HERE, 'textures')
TEX = 2048
ALBEDO_OUT = os.path.join(TEXDIR, 'details_albedo.png')
MR_OUT = os.path.join(TEXDIR, 'details_mr.png')  # R metal, G roughness
NORMAL_OUT = os.path.join(TEXDIR, 'details_normal.png')
EMBROIDERY_H, THREAD_H = 3.0, 4.0  # px: the gold embroidery raised off the cloth; its threads' relief per unit of light

# Flat colours (linear RGB).
RED = (0.55, 0.014, 0.010)
GOLD = (0.80, 0.52, 0.16)
LEATHER = (0.009, 0.009, 0.010)
SOLE = (0.006, 0.005, 0.005)
WHITE = (0.80, 0.78, 0.72)
CLOTH = (0.010, 0.011, 0.016)     # the tunic's wool (build_uniform.CLOTH_RGB)

# Red collar over the tunic's standing collar: down from its top edge to where the cloth turns out into the shoulders
# (by COLLAR_TURN, at most COLLAR_MAX_H); halves apart at the front, the tunic's dark collar between them.
COLLAR_LIFT, COLLAR_TURN, COLLAR_MAX_H = 0.0025, 0.004, 0.075
COLLAR_FLARE = 0.003              # the band widens downwards by at most this
COLLAR_MIN_H = 0.07               # ... but at the front at least this tall (the portrait's collar: one pupil distance)
COLLAR_FRONT_GAP = 0.017          # half-width of the opening at the front, at the top ...
COLLAR_FRONT_GAP_BOTTOM = 0.04    # ... and at the bottom edge (the halves part downwards, the dark stand between)
COLLAR_REPEATS, CUFF_REPEATS, BELT_REPEATS = 2, 2, 4  # mirrored repeats of the generated pictures (textures/gen)
COLLAR_THICK = 0.004
# Buttons down the closure, on the wearer's right of the piped edge; some hide under the sash.
BUTTON_R, BUTTON_H = 0.0085, 0.0055
BUTTON_ZS = (1.66, 1.60, 1.54, 1.48, 1.42, 1.36)  # above the belt
BUTTON_DXS = (-0.024, 0.031)      # from the flap edge: a row either side of the piped closure, as in the portrait
# Belt over the waist seam of the tunic; buckle plate taller than the belt, top corners cut off.
BELT_THICK, BELT_EASE = 0.004, 0.001   # height and profile come from build_uniform.py (it takes the tunic in)
BUCKLE_W, BUCKLE_H, BUCKLE_RAISE = 0.125, 0.088, 0.004
BUCKLE_CUT_X, BUCKLE_CUT_Z = 0.020, 0.032  # cut-off top corners, measured on the plate in the picture
BUCKLE_CLOSURE = 0.8               # the closure runs through the buckle this far across it (from the picture's left)
# Cuffs: a band over the end of the sleeve with piped (beaded) edges; a gold flap with three buttons outside.
CUFF_RAISE, CUFF_THICK, CUFF_LIP, CUFF_BEAD = 0.002, 0.003, 0.012, 0.003
FLAP_ACROSS, FLAP_ALONG, FLAP_RAISE = 0.068, 0.074, 0.003
# Riding boots up to BOOT_TOP, wider than the tucked-in trousers; sole with a welt, heel, accordion folds over the
# ankle, a spur at the heel.
BOOT_EASE, BOOT_FOOT_OFF, BOOT_THICK = 0.018, 0.006, 0.003
SOLE_H, WELT, HEEL_H = 0.012, 0.004, 0.032
FOLD_Z0, FOLD_Z1, FOLD_PITCH, FOLD_AMP = 0.12, 0.27, 0.032, 0.005

# Atlas regions (u0, v0, u1, v1).
ATLAS = {
    'collar': (0.0, 0.0, 0.5, 0.125),
    'cuff': (0.5, 0.0, 1.0, 0.125),
    'belt': (0.0, 0.125, 1.0, 0.1875),
    'buckle': (0.0, 0.1875, 0.125, 0.3125),
    'flap': (0.125, 0.1875, 0.1875, 0.3125),
    'gold': (0.1875, 0.1875, 0.25, 0.25),
    'leather': (0.25, 0.1875, 0.3125, 0.25),
    'sole': (0.3125, 0.1875, 0.375, 0.25),
    'red': (0.375, 0.1875, 0.4375, 0.25),
    'white': (0.4375, 0.1875, 0.5, 0.25),
    'cloth': (0.5, 0.1875, 0.5625, 0.25),
}

sc = bpy.context.scene
P = sc['uniform'].to_dict()
rig = bpy.data.objects['HumanRig']
rig.data.pose_position = 'REST'
uni, under, h = bpy.data.objects['Uniform'], bpy.data.objects['BodyUnder'], bpy.data.objects['Human']
bones = {b.name: (rig.matrix_world @ b.head_local, rig.matrix_world @ b.tail_local) for b in rig.data.bones}
for o in list(bpy.data.objects):  # previous run
    if o.get('detail'):
        bpy.data.objects.remove(o)


def smoothstep(x, a, b):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def circ_smooth(vals, n=2, k=0.5):
    for _ in range(n):
        vals = [vals[i] * (1 - k) + (vals[i - 1] + vals[(i + 1) % len(vals)]) * k / 2 for i in range(len(vals))]
    return vals


# ---------------------------------------------------------------- surfaces and weights
dg = bpy.context.evaluated_depsgraph_get()
body_me = bpy.data.meshes.new_from_object(h.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
body_groups = [g.name for g in h.vertex_groups]


def bvh_of(me):
    bm = bmesh.new(); bm.from_mesh(me)
    t = BVHTree.FromBMesh(bm); bm.free()
    return t


UNI_BVH, BODY_BVH = bvh_of(uni.data), bvh_of(body_me)


class Weights:
    """Bone weights of a skinned mesh, looked up at any point (inverse-distance blend of the nearest vertices)."""

    def __init__(self, me, names):
        self.kd = KDTree(len(me.vertices))
        self.w = []
        for v in me.vertices:
            self.kd.insert(v.co, v.index)
            self.w.append({names[g.group]: g.weight for g in v.groups if names[g.group] in bones and g.weight > 0})
        self.kd.balance()

    def at(self, co, k=4):
        acc = {}
        for _, i, d in self.kd.find_n(co, k):
            for n, w in self.w[i].items():
                acc[n] = acc.get(n, 0.0) + w / (d + 1e-4)
        return normalised(acc)


def normalised(acc):
    top = sorted(acc.items(), key=lambda x: -x[1])[:4]
    s = sum(w for _, w in top)
    return {n: w / s for n, w in top}


def blend_w(a, b, t):
    acc = {}
    for ws, k in ((a, 1 - t), (b, t)):
        for n, w in ws.items():
            acc[n] = acc.get(n, 0.0) + w * k
    return normalised(acc)


UNI_W = Weights(uni.data, [g.name for g in uni.vertex_groups])
BODY_W = Weights(body_me, body_groups)


def ray_dist(bvh, o, d, maxd=0.3):
    """Distance from o along d to the farthest surface within maxd (the outer layer of the cloth, not its lining)."""
    loc, nrm, _, dist = bvh.ray_cast(o + d * maxd, -d, maxd)
    return maxd - dist if dist is not None else None


def body_slice(z, keep):
    """Points where body edges cross the plane z, filtered by keep(point)."""
    out = []
    for e in body_me.edges:
        p, q = body_me.vertices[e.vertices[0]].co, body_me.vertices[e.vertices[1]].co
        if (p.z - z) * (q.z - z) < 0:
            x = p + (q - p) * ((z - p.z) / (q.z - p.z))
            if keep(x):
                out.append(x.xy)
    return out


def hull_rays(pts, c, dirs):
    """Distance from c along each 2D direction to the convex hull of pts."""
    hull = [pts[i] for i in mg.convex_hull_2d(pts)]
    out = []
    for d in dirs:
        r = 0.0
        for k in range(len(hull)):
            q = mg.intersect_line_line_2d(c, c + d * 1.0, hull[k], hull[(k + 1) % len(hull)])
            if q is not None:
                r = max(r, (q - c).length)
        out.append(r)
    return out


# ---------------------------------------------------------------- texture atlas (built in sRGB)
def to_srgb(c):
    c = np.asarray(c, np.float32)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def load_ref(name, path=None):
    """textures/ref_<name>.png (or path) as an sRGB float array, row 0 = bottom (Blender's order)."""
    img = bpy.data.images.load(path or os.path.join(TEXDIR, 'ref_%s.png' % name), check_existing=False)
    w, hh = img.size
    a = np.array(img.pixels[:], np.float32).reshape(hh, w, 4)[..., :3]
    bpy.data.images.remove(img)
    return a


def sample(img, u, v):
    """Bilinear lookup at normalised coordinates (arrays), v = 0 bottom."""
    hh, w = img.shape[:2]
    x = np.clip(u * (w - 1), 0, w - 1.001); y = np.clip(v * (hh - 1), 0, hh - 1.001)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = (x - x0)[..., None], (y - y0)[..., None]
    return ((img[y0, x0] * (1 - fx) + img[y0, x0 + 1] * fx) * (1 - fy)
            + (img[y0 + 1, x0] * (1 - fx) + img[y0 + 1, x0 + 1] * fx) * fy)


def gold_mask(rgb):
    """Gold thread/metal in a picture patch: warm, bright, not red cloth."""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    return np.clip((g - 0.28) / 0.15, 0, 1) * np.clip((g - b - 0.08) / 0.1, 0, 1)


def load_gen(name):
    """textures/gen/<name>.png: the material pictures generated after the portrait (flat light, see art/prompts.md)."""
    return load_ref(None, os.path.join(TEXDIR, 'gen', name + '.png'))


def mirrored(u, n):
    """u in 0..1 over n mirrored repeats: 0..1..0..1 - seamless wherever the picture's ends meet."""
    t = (u * n) % 2.0
    return np.where(t > 1, 2 - t, t)


def collar_tex(w, hh):
    """One half of the collar, front edge at u = 0, back centre at u = 1: the generated oak-leaf band, mirrored repeats
    (the halves meet at the back on the same column); its gold edges at the collar's top and bottom."""
    ref = load_gen('collar_oak')
    u, v = np.meshgrid(np.linspace(0, 1, w), np.linspace(0, 1, hh))
    return sample(ref, mirrored(u, COLLAR_REPEATS), v)


def cuff_tex(w, hh):
    """Round the cuff: red piping at both edges, the generated oak-leaf panel between, mirrored repeats."""
    ref = load_gen('cuff_oak')
    u, v = np.meshgrid(np.linspace(0, 1, w), np.linspace(0, 1, hh))
    rgb = sample(ref, mirrored(u, CUFF_REPEATS), (v - 0.12) / 0.76)
    edge = (v < 0.12) | (v > 0.88)
    shade = 0.7 + 0.3 * np.sin(np.where(v < 0.5, v, 1 - v)[edge] / 0.12 * math.pi)
    rgb[edge] = to_srgb(RED) * shade[:, None]
    return rgb


def belt_tex(w, hh):
    """The generated galloon (red edges, woven gold), mirrored repeats round the waist."""
    ref = load_gen('belt_galloon')
    u, v = np.meshgrid(np.linspace(0, 1, w), np.linspace(0, 1, hh))
    return sample(ref, mirrored(u, BELT_REPEATS), v)


def buckle_tex(w, hh):
    """The generated buckle plate; its grey background in the cut corners becomes the plate's gold edge."""
    c = sample(load_gen('buckle'), *np.meshgrid(np.linspace(0, 1, w), np.linspace(0, 1, hh)))
    grey = (c.max(2) - c.min(2) < 0.06) & (c.max(2) > 0.6)
    c[grey] = np.array([0.72, 0.55, 0.25], np.float32)
    return c


VIVID_SAT, VIVID_GAMMA, VIVID_GAIN = 1.3, 0.85, 1.08  # the pictures carry the painting's light: rendered under ours
                                                    # they came out dull - more saturated and brighter


def vivid(rgb):
    """Saturation and brightness up (sRGB), hue kept."""
    v = rgb.max(2, keepdims=True)
    grey = np.repeat(v, 3, 2)
    c = grey + (rgb - grey) * VIVID_SAT
    v2 = np.clip(np.power(np.maximum(v, 1e-6), VIVID_GAMMA) * VIVID_GAIN, 0, 1)
    return np.clip(c * v2 / np.maximum(v, 1e-6), 0, 1)


def build_atlas():
    rgb = np.zeros((TEX, TEX, 3), np.float32)
    metal = np.zeros((TEX, TEX), np.float32); rough = np.full((TEX, TEX), 0.8, np.float32)
    height = np.zeros((TEX, TEX), np.float32)

    def px(region):
        u0, v0, u1, v1 = ATLAS[region]
        return int(u0 * TEX), int(v0 * TEX), int(u1 * TEX), int(v1 * TEX)

    def put(region, fn, raw=False):
        x0, y0, x1, y1 = px(region)
        c = fn(x1 - x0, y1 - y0)
        c = c if raw else vivid(c)
        g = gold_mask(c)
        rgb[y0:y1, x0:x1] = c
        metal[y0:y1, x0:x1] = 0.5 * g  # the pictures already carry the shading of the gold: some shine on top
        rough[y0:y1, x0:x1] = 0.75 - 0.45 * g
        # relief: the gold embroidery stands up from the cloth, its threads by their light and dark
        height[y0:y1, x0:x1] = mat_util.blur(g.astype(np.float32), 2) * EMBROIDERY_H + mat_util.relief(c, THREAD_H)

    def flat(region, col, m, r):
        x0, y0, x1, y1 = px(region)
        rgb[y0:y1, x0:x1] = to_srgb(col); metal[y0:y1, x0:x1] = m; rough[y0:y1, x0:x1] = r

    def picture(name):
        def fn(w, hh):
            u, v = np.meshgrid(np.linspace(0, 1, w), np.linspace(0, 1, hh))
            return sample(load_ref(name), u, v)
        return fn

    put('collar', collar_tex, raw=True)
    put('cuff', cuff_tex, raw=True)
    put('belt', belt_tex, raw=True)
    put('buckle', buckle_tex, raw=True)
    put('flap', picture('cuff_flap'))
    flat('gold', GOLD, 1.0, 0.3)
    flat('leather', LEATHER, 0.0, 0.16)
    flat('sole', SOLE, 0.0, 0.6)
    flat('red', RED, 0.0, 0.85)
    flat('white', WHITE, 0.0, 0.7)
    flat('cloth', CLOTH, 0.0, 0.85)
    albedo = mat_util.save('Details_Albedo', rgb, ALBEDO_OUT, 'sRGB')
    mr = mat_util.save('Details_MR', np.stack([metal, rough, np.zeros_like(metal)], 2), MR_OUT, 'Non-Color')
    nrm = mat_util.save('Details_Normal', mat_util.normals(height) * 0.5 + 0.5, NORMAL_OUT, 'Non-Color')
    mat = mat_util.material('Details', albedo, mr, nrm)
    print('atlas', ALBEDO_OUT)
    return mat


MAT = build_atlas()


def uv_in(region, u, v):
    u0, v0, u1, v1 = ATLAS[region]
    pad = 2 / TEX
    return (u0 + pad + (u1 - u0 - 2 * pad) * u, v0 + pad + (v1 - v0 - 2 * pad) * v)


# ---------------------------------------------------------------- mesh helpers
def new_detail(name, bm, uvs=None, weights=None, solidify=0.0):
    """bm with per-vertex UVs and weights (dicts or functions of the vertex) -> skinned object in the scene.
    solidify > 0 thickens inwards, < 0 outwards."""
    for lay in list(bm.loops.layers.uv.values()):
        bm.loops.layers.uv.remove(lay)
    if uvs is not None:
        lay = bm.loops.layers.uv.new('UVMap')
        for f in bm.faces:
            for l in f.loops:
                l[lay].uv = uvs(l.vert) if callable(uvs) else uvs[l.vert]
    me = bpy.data.meshes.new(name)
    vw = [weights(v) if callable(weights) else weights[v] for v in bm.verts] if weights else None
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob)
    ob['detail'] = True
    me.materials.append(MAT)
    for p in me.polygons:
        p.use_smooth = True
    if vw:
        for i, ws in enumerate(vw):
            for n, w in ws.items():
                g = ob.vertex_groups.get(n) or ob.vertex_groups.new(name=n)
                g.add([i], w, 'REPLACE')
    if solidify:
        m = ob.modifiers.new('Thick', 'SOLIDIFY'); m.thickness = solidify; m.offset = -1; m.use_rim = True
        for o in sc.objects:
            o.select_set(o == ob)
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.modifier_apply(modifier='Thick')
    ob.modifiers.new('Armature', 'ARMATURE').object = rig
    return ob


def loft(rings, closed=True):
    """Grid of faces between consecutive rings of vertex coordinates; returns bm and the vertex grid."""
    bm = bmesh.new()
    grid = [[bm.verts.new(c) for c in ring] for ring in rings]
    n = len(rings[0])
    for r0, r1 in zip(grid, grid[1:]):
        for j in range(n if closed else n - 1):
            j2 = (j + 1) % n
            bm.faces.new((r0[j], r0[j2], r1[j2], r1[j]))
    return bm, grid


def outward_normals(bm, centre_fn):
    bm.normal_update(); bm.faces.ensure_lookup_table()
    f = bm.faces[len(bm.faces) // 2]
    if f.normal.dot(f.calc_center_median() - centre_fn(f.calc_center_median())) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])


def rigid(ws):
    return lambda v: ws


def merge_bms(bms):
    out = bmesh.new()
    for b in bms:
        me = bpy.data.meshes.new('tmp'); b.to_mesh(me); b.free()
        out.from_mesh(me); bpy.data.meshes.remove(me)
    return out


def button_mesh(centre, normal, r=BUTTON_R, hgt=BUTTON_H):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=14, v_segments=8, radius=r)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < -1e-4], context='VERTS')
    for v in bm.verts:
        v.co.z = v.co.z / r * hgt
    bmesh.ops.contextual_create(bm, geom=[e for e in bm.edges if e.is_boundary])  # flat back
    m = Matrix.Translation(centre) @ normal.to_track_quat('Z', 'Y').to_matrix().to_4x4()
    bmesh.ops.transform(bm, matrix=m, verts=bm.verts[:])
    return bm


def buttons_detail(name, spots, r=BUTTON_R, hgt=BUTTON_H):
    """Gold buttons at (point on the surface, normal, weights) spots, one rigid piece each."""
    parts, wts = [], []
    for loc, nrm, ws in spots:
        b = button_mesh(loc + nrm * 0.0005, nrm, r, hgt)
        parts.append(b); wts += [ws] * len(b.verts)
    bm = merge_bms(parts); bm.verts.ensure_lookup_table()
    return new_detail(name, bm, {v: uv_in('gold', 0.5, 0.5) for v in bm.verts}, {v: wts[v.index] for v in bm.verts})


# ---------------------------------------------------------------- collar
def build_collar(nu=64, nv=7):
    """Red embroidered collar laid over the tunic's own standing collar (build_uniform.py): from where the tunic turns
    out into the shoulders up to its top edge, COLLAR_LIFT off the dark cloth; the halves stand apart at the front, the
    dark collar shows between them. A white shirt collar shows above the top edge."""
    c0 = Vector(P['NECK_AXIS'])
    gap = COLLAR_FRONT_GAP / 0.08
    thetas = [gap + (2 * math.pi - 2 * gap) * j / (nu - 1) for j in range(nu)]
    dirs = [Vector((math.sin(t), -math.cos(t), 0.0)) for t in thetas]
    top_at = lambda t: P['STAND_TOP_FRONT'] + (P['STAND_TOP_BACK'] - P['STAND_TOP_FRONT']) * (1 - math.cos(t)) / 2
    cloth = lambda z, d: ray_dist(UNI_BVH, c0.to_3d() + Vector((0, 0, z)), d, 0.16)
    tops, bots, turns = [], [], []
    for t, d in zip(thetas, dirs):
        zt = top_at(t) + 0.001  # over the tunic's top edge
        r0 = cloth(zt - 0.006, d) or 0.08
        z = zt - 0.006
        while z > zt - COLLAR_MAX_H:  # down the stand until the cloth turns out into the shoulder
            r = cloth(z - 0.002, d)
            if r is None or r > r0 + COLLAR_TURN:
                break
            z -= 0.002
        turns.append(z)
        front = smoothstep(math.cos(t), 0.4, 0.85)  # the front only: at the sides and back it would lie on the shoulders
        tops.append(zt); bots.append(min(z, zt - COLLAR_MIN_H * front - (zt - z) * (1 - front)))
    bots = circ_smooth(bots, 3)
    rings = []
    gap_b = COLLAR_FRONT_GAP_BOTTOM / 0.08
    for i in range(nv):
        f = i / (nv - 1)
        ring = []
        g = gap_b + (gap - gap_b) * f
        ring_dirs = [Vector((math.sin(t), -math.cos(t), 0.0)) for t in
                     (g + (2 * math.pi - 2 * g) * j / (nu - 1) for j in range(nu))]
        for j, (d, zb, zt, zturn) in enumerate(zip(ring_dirs, bots, tops, turns)):
            z = zb + (zt - zb) * f
            r_top = cloth(zt - 0.004, d) or 0.08
            # a straight band down to where the cloth turns out (no flare onto the shoulders); below that (the front,
            # down to COLLAR_MIN_H) it lies on the cloth
            r = cloth(min(z, zt - 0.004), d) or 0.08
            if z >= zturn:
                r = min(r, r_top + COLLAR_FLARE)
            ring.append(c0.to_3d() + Vector((0, 0, z)) + d * (r + COLLAR_LIFT))
        rings.append(ring)
    for i in range(nv):  # smooth round: the rays catch the cloth's small dents
        ctr = c0.to_3d()
        rad = circ_smooth([(p - Vector((ctr.x, ctr.y, p.z))).xy.length for p in rings[i]], 2)
        rings[i] = [Vector((*(ctr.xy + (p.xy - ctr.xy).normalized() * r), p.z)) for p, r in zip(rings[i], rad)]
    # the piped top edge rolls over the tunic collar's edge to its inside
    rings.append([Vector((c0.x, c0.y, p.z + 0.003)) + (Vector((p.x, p.y, 0)) - c0.to_3d()).normalized()
                  * ((p.xy - c0).length - COLLAR_LIFT - 0.004) for p in rings[-1]])
    print('collar: bottom z %.3f..%.3f, top z %.3f..%.3f' % (min(bots), max(bots), min(tops), max(tops)))
    bm, grid = loft(rings, closed=False)
    outward_normals(bm, lambda p: Vector((c0.x, c0.y, p.z)))
    neck_w = {'neck_01': 0.6, 'spine_03': 0.4}
    uvs, wts = {}, {}
    for i, row in enumerate(grid):
        f = min(i / (nv - 1), 1.0)
        for j, v in enumerate(row):
            s = (min(thetas[j], 2 * math.pi - thetas[j]) - gap) / (math.pi - gap)  # 0 front edge, 1 back centre
            uvs[v] = uv_in('collar', s, f)
            wts[v] = UNI_W.at(v.co)
    collar = new_detail('Collar', bm, uvs, wts, -COLLAR_THICK)
    # white shirt collar showing above the top edge, between the neck and the tunic's collar
    rings = []
    for k in range(2):
        ring = []
        for zt, d in zip(tops, dirs):
            z = zt - 0.008 + 0.0115 * k
            rn = cloth(zt - 0.006, d) or 0.07
            ring.append(c0.to_3d() + Vector((0, 0, z)) + d * (rn - 0.0075))
        rings.append(ring)
    bm, grid = loft(rings, closed=False)
    outward_normals(bm, lambda p: Vector((c0.x, c0.y, p.z)))
    shirt = new_detail('ShirtCollar', bm, {v: uv_in('white', 0.5, 0.5) for row in grid for v in row},
                       lambda v: BODY_W.at(v.co), 0.0012)
    return collar, shirt


# ---------------------------------------------------------------- buttons
def build_buttons():
    spots = []
    for dx in BUTTON_DXS:
        for z in BUTTON_ZS:
            loc, nrm, _, _ = UNI_BVH.ray_cast(Vector((P['FLAP_X'] + dx, -0.6, z)), Vector((0, 1, 0)), 1.0)
            spots.append((loc, nrm, UNI_W.at(loc)))
    return buttons_detail('Buttons', spots)


# ---------------------------------------------------------------- belt with buckle
def build_belt(nu=96, nv=4):
    """Belt on the profile build_uniform.py took the tunic in to (BELT_PROFILE, directions from the front round
    through the wearer's left), buckle placed on the closure as in the picture."""
    zc, hb = P['BELT_ZC'], P['BELT_H']
    c = Vector(P['BELT_C'])
    prof = list(P['BELT_PROFILE'])
    n = len(prof)

    def radius(theta):  # theta from the front (-Y) towards +X
        f = (theta % (2 * math.pi)) / (2 * math.pi) * n
        k = int(f) % n
        return prof[k] + (prof[(k + 1) % n] - prof[k]) * (f - int(f)) + BELT_EASE

    thetas = [math.pi + 2 * math.pi * j / nu for j in range(nu + 1)]  # j = 0 at the back; seam vertices duplicated
    rings = [[(c + Vector((math.sin(t), -math.cos(t))) * radius(t)).to_3d() + Vector((0, 0, zc - hb / 2 + hb * i / (nv - 1)))
              for t in thetas] for i in range(nv)]
    bm, grid = loft(rings, closed=False)
    outward_normals(bm, lambda p: Vector((c.x, c.y, p.z)))
    uvs = {v: uv_in('belt', j / nu, i / (nv - 1)) for i, row in enumerate(grid) for j, v in enumerate(row)}
    belt = new_detail('Belt', bm, uvs, lambda v: UNI_W.at(v.co), -BELT_THICK)
    # Buckle: a plate curved over the belt, taller than it, the top corners cut off as in the picture.
    k = 11
    pts, uv = [], []
    dx = P['FLAP_X'] - (BUCKLE_CLOSURE - 0.5) * BUCKLE_W  # buckle centre
    t0 = math.asin(max(-1.0, min(1.0, (dx - c.x) / radius(0.0))))
    for i in range(k):
        b = i / (k - 1)  # 0 bottom .. 1 top
        row, urow = [], []
        for j in range(k):
            a = j / (k - 1)
            x = (a - 0.5) * BUCKLE_W
            into = (b - (1 - BUCKLE_CUT_Z / BUCKLE_H)) / (BUCKLE_CUT_Z / BUCKLE_H)  # 0..1 up through the cut
            if into > 0:
                x *= 1 - into * BUCKLE_CUT_X / (BUCKLE_W / 2)
            t = t0 + x / radius(t0)
            r = radius(t) + BELT_THICK + BUCKLE_RAISE
            row.append((c + Vector((math.sin(t), -math.cos(t))) * r).to_3d() + Vector((0, 0, zc + (b - 0.5) * BUCKLE_H)))
            urow.append(uv_in('buckle', x / BUCKLE_W + 0.5, b))
        pts.append(row); uv.append(urow)
    bm, grid = loft(pts, closed=False)
    outward_normals(bm, lambda p: Vector((c.x, c.y, p.z)))
    uvs = {v: uv[i][j] for i, row in enumerate(grid) for j, v in enumerate(row)}
    mid = (c + Vector((math.sin(t0), -math.cos(t0))) * radius(t0)).to_3d() + Vector((0, 0, zc))
    buckle = new_detail('Buckle', bm, uvs, rigid(UNI_W.at(mid)), 0.003)
    return belt, buckle


# ---------------------------------------------------------------- cuffs
CUFF_PROFILE = [(0.0, 0.0), (0.035, CUFF_BEAD), (0.10, 0.001), (0.90, 0.001), (0.965, CUFF_BEAD), (1.0, 0.001)]


def build_cuffs(nu=40):
    out = []
    for s in 'lr':
        sign = 1 if s == 'l' else -1
        a, b = bones['lowerarm_' + s]
        ax = (b - a).normalized()
        e1 = ax.cross(Vector((0, 0, 1))).normalized(); e2 = ax.cross(e1).normalized()
        t0, t1 = P['SLEEVE_T'] - P['CUFF_T'], P['SLEEVE_T']
        inner = Vector((-sign, 0, 0))  # UV seam on the inner side of the forearm, towards the body
        phase = math.atan2(inner.dot(e2), inner.dot(e1))
        thetas = [phase + 2 * math.pi * j / nu for j in range(nu + 1)]
        dirs = [e1 * math.cos(t) + e2 * math.sin(t) for t in thetas]
        rs = []
        for d in dirs[:-1]:
            rs.append(max((ray_dist(UNI_BVH, a + (b - a) * float(t), d, 0.15) or 0.0)
                          for t in np.linspace(t0, t1 - 0.01, 6)) + CUFF_RAISE)
        rs = circ_smooth(rs, 3); rs.append(rs[0])
        axis = lambda f: a + (b - a) * (t0 + (t1 - t0) * f)
        rings = [[axis(f) + d * (r + dr) for d, r in zip(dirs, rs)] for f, dr in CUFF_PROFILE]
        rings.append([axis(1.0) + d * (r - CUFF_LIP) for d, r in zip(dirs, rs)])  # turned in at the wrist
        vs = [f for f, _ in CUFF_PROFILE] + [1.0]
        bm, grid = loft(rings, closed=False)
        outward_normals(bm, lambda p, a=a, b=b: a + (b - a) * ((p - a).dot(b - a) / (b - a).length_squared))
        uvs = {v: uv_in('cuff', j / nu, vs[i]) for i, row in enumerate(grid) for j, v in enumerate(row)}
        out.append(new_detail('Cuff_' + s, bm, uvs, lambda v: UNI_W.at(v.co), CUFF_THICK))
        rw = [(ray_dist(BODY_BVH, axis(1.0), d, 0.1) or 0.03) + 0.003 for d in dirs[:-1]]
        rw = circ_smooth(rw, 3); rw.append(rw[0])
        span = 0.012 / (b - a).length
        rings = [[a + (b - a) * (t1 + span * k) + d * r for d, r in zip(dirs, rw)] for k in (-1.5, 0.0, 1.0)]
        bm, grid = loft(rings, closed=False)
        outward_normals(bm, lambda p, a=a, b=b: a + (b - a) * ((p - a).dot(b - a) / (b - a).length_squared))
        out.append(new_detail('ShirtCuff_' + s, bm, lambda v: uv_in('white', 0.5, 0.5), lambda v: BODY_W.at(v.co), 0.0012))
        # Flap on the outer side (back of the forearm), curved with the cuff, three buttons along the arm.
        outer = Vector((sign, -0.6, 0.0)).normalized()
        jc = max(range(nu), key=lambda j: dirs[j].dot(outer))
        tc, rc = thetas[jc], rs[jc] + CUFF_BEAD
        k = 6
        pts, uv = [], []
        for i in range(k):
            fa = i / (k - 1)  # along the arm: 0 elbow side .. 1 wrist side
            row, urow = [], []
            for j in range(k):
                fc = j / (k - 1)
                ang = tc + (fc - 0.5) * FLAP_ACROSS / rc
                d = e1 * math.cos(ang) + e2 * math.sin(ang)
                c = axis(0.5) + ax * (fa - 0.5) * FLAP_ALONG
                row.append(c + d * (rc + FLAP_RAISE))
                urow.append(uv_in('flap', fc, 1 - fa))  # the picture's top is the elbow side
            pts.append(row); uv.append(urow)
        bm, grid = loft(pts, closed=False)
        outward_normals(bm, lambda p, a=a, b=b: a + (b - a) * ((p - a).dot(b - a) / (b - a).length_squared))
        uvs = {v: uv[i][j] for i, row in enumerate(grid) for j, v in enumerate(row)}
        ws = UNI_W.at(axis(0.5) + dirs[jc] * rs[jc])
        out.append(new_detail('CuffFlap_' + s, bm, uvs, rigid(ws), 0.003))
        spots = []
        for fa in (0.2, 0.5, 0.8):
            c = axis(0.5) + ax * (fa - 0.5) * FLAP_ALONG * 0.85
            spots.append((c + dirs[jc] * (rc + FLAP_RAISE), dirs[jc], ws))
        out.append(buttons_detail('CuffButtons_' + s, spots, r=0.0068, hgt=0.0048))
    return out


# ---------------------------------------------------------------- boots
def keep_largest(bm):
    bm.verts.ensure_lookup_table()
    seen, best = set(), []
    for v0 in bm.verts:
        if v0 in seen:
            continue
        comp, stack = [], [v0]; seen.add(v0)
        while stack:
            v = stack.pop(); comp.append(v)
            for e in v.link_edges:
                w = e.other_vert(v)
                if w not in seen:
                    seen.add(w); stack.append(w)
        if len(comp) > len(best):
            best = comp
    keep = set(best)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v not in keep], context='VERTS')


def apply_mods(ob, mods):
    for o in sc.objects:
        o.select_set(o == ob)
    bpy.context.view_layer.objects.active = ob
    for kind, props in mods:
        m = ob.modifiers.new(kind, kind)
        for k, v in props.items():
            setattr(m, k, v)
        bpy.ops.object.modifier_apply(modifier=m.name)


def prism(poly, z0, z1):
    b = bmesh.new()
    vs = [b.verts.new((p.x, p.y, z0)) for p in poly]
    f = b.faces.new(vs)
    ext = bmesh.ops.extrude_face_region(b, geom=[f])
    bmesh.ops.translate(b, vec=(0, 0, z1 - z0), verts=[e for e in ext['geom'] if isinstance(e, bmesh.types.BMVert)])
    bmesh.ops.recalc_face_normals(b, faces=b.faces[:])
    return b


def build_boots(nu=48):
    """Riding boots. The foot is the body's foot inflated by the leather and voxel-remeshed together with the shaft, so
    the toes melt into one rounded toe box; the shaft is lofted through slices of the leg (convex hull + ease over the
    tucked-in trousers) with accordion folds over the ankle. A sole with a welt and a heel block go underneath."""
    top = P['BOOT_TOP']
    dirs = [Vector((math.sin(2 * math.pi * j / nu), -math.cos(2 * math.pi * j / nu))) for j in range(nu)]
    gi = {n: i for i, n in enumerate(body_groups)}
    out = []
    for s in 'lr':
        sign = 1 if s == 'l' else -1
        near = lambda p: abs(p.x - sign * 0.21) < 0.13 and p.y < 0.2
        # foot: the body below the ankle, inflated, closed
        leg = {gi[n] for n in ('calf_' + s, 'foot_' + s, 'ball_' + s) if n in gi}
        bm = bmesh.new(); bm.from_mesh(body_me)
        dl = bm.verts.layers.deform.active
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, 0.17), plane_no=(0, 0, 1))
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.calc_center_median().z > 0.17
                                   or not near(f.calc_center_median())
                                   or min(sum(v[dl].get(g, 0) for g in leg) for v in f.verts) < 0.5], context='FACES')
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
        keep_largest(bm)
        bm.normal_update()
        for v in bm.verts:
            v.co += v.normal * BOOT_FOOT_OFF
        bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary], sides=0)
        # shaft
        rings = []
        for z in list(np.arange(0.10, FOLD_Z1, FOLD_PITCH / 4)) + list(np.linspace(FOLD_Z1 + 0.02, top, 7)):
            pts = body_slice(float(z), near)
            c = sum(pts, Vector((0.0, 0.0))) / len(pts)
            ease = BOOT_FOOT_OFF + (BOOT_EASE - BOOT_FOOT_OFF) * smoothstep(z, 0.10, 0.20)
            ring = []
            for d, r in zip(dirs, hull_rays(pts, c, dirs)):
                r += ease
                if z > top - 0.1:  # clear of the tucked-in trousers (cut 2 cm into the boot)
                    rt = ray_dist(UNI_BVH, Vector((c.x, c.y, float(z))), d.to_3d(), 0.2)
                    r = max(r, (rt or 0.0) + BOOT_THICK + 0.004)
                if FOLD_Z0 < z < FOLD_Z1:  # accordion folds, strongest at the front and sides
                    fade = math.sin(math.pi * (z - FOLD_Z0) / (FOLD_Z1 - FOLD_Z0))
                    r += FOLD_AMP * fade * (0.6 + 0.4 * -d.y) * math.sin(2 * math.pi * (z - FOLD_Z0) / FOLD_PITCH
                                                                         + 1.3 * d.x * sign)
                p = c + d * r
                ring.append(Vector((p.x, p.y, float(z))))
            rings.append(ring)
        sb, _ = loft(rings)
        bmesh.ops.holes_fill(sb, edges=[e for e in sb.edges if e.is_boundary], sides=0)
        bm = merge_bms([bm, sb])
        me = bpy.data.meshes.new('BootTmp'); bm.to_mesh(me); bm.free()
        ob = bpy.data.objects.new('BootTmp', me); sc.collection.objects.link(ob)
        apply_mods(ob, [('REMESH', dict(mode='VOXEL', voxel_size=0.004)),
                        ('SMOOTH', dict(factor=0.6, iterations=8))])
        bm = bmesh.new(); bm.from_mesh(ob.data)
        bpy.data.objects.remove(ob)
        low = [v.co.xy.copy() for v in bm.verts if v.co.z < SOLE_H + 0.01]
        y_toe, y_heel = min(p.y for p in low), max(p.y for p in low)
        y_breast = y_heel - (y_heel - y_toe) * 0.27  # front face of the heel
        # the toes melt away: the forefoot smoothed hard (the upper surface only, the sole outline stays)
        fore = [v for v in bm.verts if v.co.y < y_breast - 0.04 and SOLE_H + 0.008 < v.co.z < 0.09]
        for _ in range(25):
            bmesh.ops.smooth_vert(bm, verts=fore, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
        # open the top with a straight cut
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, top), plane_no=(0, 0, 1),
                               clear_outer=True)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
        me = bpy.data.meshes.new('BootTmp'); bm.to_mesh(me); bm.free()
        ob = bpy.data.objects.new('BootTmp', me); sc.collection.objects.link(ob)
        apply_mods(ob, [('DECIMATE', dict(ratio=0.1))])
        bm = bmesh.new(); bm.from_mesh(ob.data)
        bpy.data.objects.remove(ob)
        for v in bm.verts:
            floor = HEEL_H if v.co.y > y_breast else SOLE_H
            if v.co.z < floor:
                v.co.z = floor
        out.append(new_detail('Boot_' + s, bm, lambda v: uv_in('leather', 0.5, 0.5), lambda v: BODY_W.at(v.co),
                              BOOT_THICK))
        # sole with a welt, and the heel block, from the outline of the boot's bottom
        hull = [low[i] for i in mg.convex_hull_2d(low)]
        cxy = sum(hull, Vector((0.0, 0.0))) / len(hull)
        welt = [p + (p - cxy).normalized() * WELT for p in hull]
        heel_poly = [p - (p - cxy).normalized() * 0.002 for p in welt if p.y > y_breast]
        heel_poly.sort(key=lambda p: math.atan2(p.x - cxy.x, p.y - cxy.y))
        sole = merge_bms([prism(welt, 0.0, SOLE_H), prism(heel_poly, 0.0, HEEL_H)])
        sole.verts.ensure_lookup_table()
        out.append(new_detail('Sole_' + s, sole, lambda v: uv_in('sole', 0.5, 0.5), lambda v: BODY_W.at(v.co)))
        # spur: a gold boss at the back of the heel, on the outer side
        boot = out[-2]
        bvh = bvh_of(boot.data)
        o = Vector((cxy.x + sign * 0.07, y_heel + 0.07, 0.065))
        aim = Vector((cxy.x, y_heel - 0.03, 0.065))
        loc, nrm, _, _ = bvh.ray_cast(o, (aim - o).normalized(), 0.3)
        if loc is not None:
            out.append(buttons_detail('Spur_' + s, [(loc, nrm, BODY_W.at(loc))], r=0.008, hgt=0.006))
    return out


collar = build_collar()
buttons = build_buttons()
belt = build_belt()
cuffs = build_cuffs()
boots = build_boots()

# Trouser legs and feet inside the boots are hidden: delete them.
bm = bmesh.new(); bm.from_mesh(uni.data)
part = bm.faces.layers.int.get('part')
bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, P['BOOT_TOP'] - 0.02),
                       plane_no=(0, 0, 1))
bmesh.ops.delete(bm, geom=[f for f in bm.faces if f[part] == 2 and f.calc_center_median().z < P['BOOT_TOP'] - 0.02],
                 context='FACES')
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
bm.to_mesh(uni.data); bm.free()
bm = bmesh.new(); bm.from_mesh(under.data)
bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.calc_center_median().z < P['BOOT_TOP'] - 0.03], context='FACES')
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
bm.to_mesh(under.data); bm.free()

for o in sc.objects:
    if o.get('detail'):
        print('detail', o.name, len(o.data.vertices), 'verts', len(o.data.polygons), 'faces')
rig.data.pose_position = 'POSE'
bpy.data.meshes.remove(body_me)
bpy.ops.outliner.orphans_purge(do_recursive=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
print('saved', OUT, os.path.getsize(OUT))

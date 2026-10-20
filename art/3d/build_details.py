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
GOLD = tuple(float(((c / 255 + 0.055) / 1.055) ** 2.4) for c in mat_util.GOLD_SRGB)  # linear
LEATHER = (0.009, 0.009, 0.010)
SOLE = (0.006, 0.005, 0.005)
WHITE = (0.80, 0.78, 0.72)
CLOTH = (0.0034, 0.0037, 0.0058)    # the tunic's wool (build_uniform.CLOTH_RGB)

# Red collar over the tunic's standing collar: down from its top edge to where the cloth turns out into the shoulders
# (by COLLAR_TURN, at most COLLAR_MAX_H); as in the portrait the halves stand apart at the front, their edges nearly
# parallel, the tunic's dark collar between them up to the top (the white shirt collar's edge over it); the neck
# stays behind it (build_pose.neck_in_collar).
COLLAR_LIFT, COLLAR_TURN, COLLAR_MAX_H = 0.0025, 0.004, 0.11  # (at 6.6 cm the band ended
                                  # over the shoulders at the back, the tunic's black stand under it: a horse collar)
COLLAR_FLARE = 0.012              # the band widens downwards by at most this: its walls lean out a little (the portrait's
                                  # are nearly upright, ~21 cm across at the top and 23 cm at the foot; flared 3 cm the
                                  # collar was a cone with its lip spread over the shoulders)
COLLAR_MIN_H = 0.060              # ... but at the front at least this tall (the portrait's red band: 6-7 cm at the front)
COLLAR_FRONT_GAP = 0.032          # the opening at the front, at the top (x the radius / 0.08 m: ~3.2 cm half-width; the
                                  # portrait's halves stand ~6 cm apart, the dark tunic and the cross between them) ...
COLLAR_FRONT_GAP_BOTTOM = 0.012   # ... and at the bottom edge: the portrait's opening is a V, ~7.4 cm across at the top
                                  # and ~3.5 cm at the foot (at 2.6 cm half-width there the halves stood apart as two
                                  # upright panels with a broad black strip between them)
STAND_DROP = 0.0                # the dark stand between the halves ends this far under their top: the shirt's white
                                  # edge shows over it (up to the top, it read as a black strip down the front)
COLLAR_REPEATS, CUFF_REPEATS, BELT_REPEATS = 2, 2, 4  # mirrored repeats of the generated pictures (textures/gen)
COLLAR_THICK = 0.004
STAND_ROWS, STAND_COLS = 7, 13    # the dark stand between the halves: rows up it, columns across
SHIRT_SHOW = 0.0145                # the shirt collar's edge this far over the bottom of its band (~6 mm over the red
                                  # collar's top: the portrait's white line is 5-8 px)
SHIRT_IN = 0.0045                 # the white shirt collar this far inside the tunic collar's outside (further in it ran into
                                  # the neck and showed in white flecks round it): its edge a white line along the
                                  # collar's top, as in the portrait
# Buttons down the closure, on the wearer's right of the piped edge; some hide under the sash.
# Measured on alexander_ii_full.png (rows of the 'ref' view: z ~ (1510 - row) * 1.397 mm): on his left of the piping
# the pencil's crook comes from a button at row 385 and the last one over the belt is at 540; on his right the one
# over the belt is at 510; the rest lie under the sash. The two rows stagger (the portrait's do), ~7.2 cm apart.
BUTTON_R, BUTTON_H = 0.0115, 0.0065  # the portrait's are big gilt domes, ~2.5 cm across (1.7 cm read as studs)
BUTTON_SPOTS = [(-0.030, 1.614), (-0.030, 1.542), (-0.030, 1.470), (-0.030, 1.397),  # (dx from the flap edge, z)
                (0.055, 1.572), (0.047, 1.500), (0.039, 1.428), (0.031, 1.356)]  # his left row slants in to the
                                  # belt as the portrait's does (its pencil button 33 px off the piping, the last 13 px)
# Belt over the waist seam of the tunic; buckle plate taller than the belt, top corners cut off.
BELT_THICK, BELT_EASE = 0.004, 0.001
BELT_RED, BELT_EDGE = 0.24, 0.05  # across the belt: red borders to this, a gold edge outside them   # height and profile come from build_uniform.py (it takes the tunic in)
BUCKLE_W, BUCKLE_H, BUCKLE_RAISE = 0.112, 0.074, 0.004  # a little over the belt's height (larger, it dominated the waist)
BUCKLE_CUT_X, BUCKLE_CUT_Z = 0.018, 0.027  # cut-off top corners, measured on the plate in the picture
BUCKLE_CLOSURE = 0.8               # the closure runs through the buckle this far across it (from the picture's left)
# Cuffs: a band over the end of the sleeve with piped (beaded) edges; a gold flap with three buttons outside.
CUFF_RAISE, CUFF_THICK, CUFF_LIP, CUFF_BEAD = 0.002, 0.003, 0.012, 0.003
SHIRT_CUFF_CLEAR = 0.006
FLAP_ACROSS, FLAP_ALONG, FLAP_RAISE = 0.068, 0.074, 0.003
# Riding boots up to BOOT_TOP, wider than the tucked-in trousers; sole with a welt, heel, accordion folds over the
# ankle, a spur at the heel.
BOOT_EASE, BOOT_FOOT_OFF, BOOT_THICK = 0.010, 0.006, 0.003  # (the portrait's shafts are slim: ~11.5 cm across
                                  # at the top, narrowing to the ankle)
BOOT_ROUGH = 0.24                 # polished calf: the portrait's boots shine in bright highlights along the shaft and toe
# The foot of the boot: a last lofted along the foot (cross-sections round on top, flat underneath), as wide as the body's
# foot plus BOOT_FOOT_OFF at every point along it; its top line (z over the sole, by the share of the length from the
# toe tip) - a low rounded toe box rising over the instep into the shaft; the bottom on the sole in front, on the heel
# behind, the arch between. The body's foot inflated (and decimated) came out a crumpled sock on a flat plate.
LAST_TOP = ((0.0, 0.008), (0.03, 0.030), (0.08, 0.047), (0.2, 0.058), (0.4, 0.075), (0.6, 0.115), (0.78, 0.14), (1.0, 0.13))
LAST_ROOM = 0.012                 # the toe this far past the body's toes
LAST_ARCH = (0.45, 0.68)          # the bottom rises from the sole to the heel's top between these shares
SOLE_H, WELT, HEEL_H = 0.010, 0.0015, 0.032
ANKLE_SEAM = (0.06, 0.19, 24)       # the last's join with the shaft: smoothed between these heights, rounds
FOLD_Z0, FOLD_Z1, FOLD_PITCH, FOLD_AMP = 0.16, 0.32, 0.036, 0.005  # (over the ankle, as in the portrait)
FOLD_SLANT, FOLD_WAVE = 2.4, 0.9    # the creases run slanting round the ankle and wander (level rings of even depth
                                  # read as an accordion; the portrait's leather creases soft and unevenly)

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
    rgb[edge] = to_srgb(RED)  # its own colour: no shading painted in (the lighting gives it)
    return rgb


def belt_tex(w, hh):
    """The portrait's belt: a gold galloon (the generated one, mirrored repeats round the waist) between wide red
    borders, a thin gold edge outside them."""
    ref = load_gen('belt_galloon')
    u, v = np.meshgrid(np.linspace(0, 1, w), np.linspace(0, 1, hh))
    c = sample(ref, mirrored(u, BELT_REPEATS), (v - BELT_RED) / (1 - 2 * BELT_RED))
    red = ((v > BELT_EDGE) & (v < BELT_RED)) | ((v > 1 - BELT_RED) & (v < 1 - BELT_EDGE))
    rib = 0.9 + 0.1 * np.sin(u * w * 0.8)[..., None]  # the red silk's weave across the belt
    c[red] = (np.array(to_srgb(RED), np.float32) * 1.15 * rib)[red]
    edge = (v <= BELT_EDGE) | (v >= 1 - BELT_EDGE)
    c[edge] = np.array(mat_util.GOLD_SRGB, np.float32) / 255 * 0.9
    return c


def buckle_tex(w, hh):
    """The generated buckle plate; its grey background in the cut corners becomes the plate's gold edge."""
    c = sample(load_gen('buckle'), *np.meshgrid(np.linspace(0, 1, w), np.linspace(0, 1, hh)))
    grey = (c.max(2) - c.min(2) < 0.06) & (c.max(2) > 0.6)
    c[grey] = np.array(mat_util.GOLD_SRGB, np.float32) / 255 * 0.85
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
        c = mat_util.gold_grade(c, g)  # the pictures' golds differ: all to the portrait's
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
    flat('leather', LEATHER, 0.0, BOOT_ROUGH)
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
    top_at = lambda t: P['STAND_TOP_FRONT'] + (P['STAND_TOP_BACK'] - P['STAND_TOP_FRONT']) * (
        (1 - math.cos(t)) / 2) ** P.get('STAND_RISE_POW', 1.0)  # as build_uniform.stand_top
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
    # one clean band: the radius round the neck from the cloth just under the top edge, smoothed hard (the rays catch
    # the cloth's dents and folds); straight down from there, flaring a little - below the turn it sinks into the cloth
    ctr = c0.to_3d()
    r_top = circ_smooth([cloth(zt - 0.006, d) or 0.08 for zt, d in zip(tops, dirs)], 8)
    for i in range(nv):
        f = i / (nv - 1)
        g = gap_b + (gap - gap_b) * f
        ring = []
        for j, (zb, zt) in enumerate(zip(bots, tops)):
            t = g + (2 * math.pi - 2 * g) * j / (nu - 1)
            d = Vector((math.sin(t), -math.cos(t), 0.0))
            z = zb + (zt - zb) * f
            ring.append(ctr + Vector((0, 0, z)) + d * (r_top[j] + COLLAR_LIFT + COLLAR_FLARE * (1 - f) ** 2))
        rings.append(ring)
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
    # the tunic's dark stand filling the opening between the halves (no neck shows through)
    # (rows like the halves', widening downwards with them: two rows only, the cloth crumpled it into a twisted strip)
    rs = []
    for k in range(STAND_ROWS):
        f = k / (STAND_ROWS - 1)
        z = bots[0] + (tops[0] - STAND_DROP - bots[0]) * f
        rr = (r_top[0] + r_top[-1]) / 2 + COLLAR_LIFT - 0.0015 + COLLAR_FLARE * (1 - f) ** 2
        g = (gap_b + (gap - gap_b) * f) * 1.5
        rs.append([ctr + Vector((0, 0, z)) + Vector((math.sin(t), -math.cos(t), 0)) * rr
                   for t in [-g + 2 * g * q / (STAND_COLS - 1) for q in range(STAND_COLS)]])
    bm, grid = loft(rs, closed=False)
    outward_normals(bm, lambda p: Vector((c0.x, c0.y, p.z)))
    stand = new_detail('CollarStand', bm, {v: uv_in('cloth', 0.5, 0.5) for row in grid for v in row},
                       lambda v: UNI_W.at(v.co), 0.002)
    # white shirt collar showing above the top edge, between the neck and the tunic's collar: a closed ring (its ends
    # at the halves' meeting poked out through the slit in white flecks)
    rings = []
    full = [2 * math.pi * j / nu for j in range(nu)]
    for k in range(2):
        ring = []
        for t in full:
            d = Vector((math.sin(t), -math.cos(t), 0.0))
            zt = top_at(t) + 0.001
            rn = cloth(zt - 0.006, d) or 0.07
            # in the opening between the halves it lies over the dark stand's top and the tunic's own collar edge
            # (inside them, that edge came through it in black and red jags), only its edge showing there too
            front = 1 - smoothstep(min(t, 2 * math.pi - t), gap * 0.8, gap * 0.98)
            z = zt - 0.008 + 0.0065 * front * (1 - k) + SHIRT_SHOW * k  # its edge over the collar's top
            ring.append(c0.to_3d() + Vector((0, 0, z)) + d * (rn - SHIRT_IN + (SHIRT_IN + COLLAR_LIFT - 0.0005) * front))
        rings.append(ring)
    bm, grid = loft(rings, closed=True)
    outward_normals(bm, lambda p: Vector((c0.x, c0.y, p.z)))
    shirt = new_detail('ShirtCollar', bm, {v: uv_in('white', 0.5, 0.5) for row in grid for v in row},
                       lambda v: BODY_W.at(v.co), 0.0012)
    return collar, shirt


# ---------------------------------------------------------------- buttons
def build_buttons():
    spots = []
    for dx, z in BUTTON_SPOTS:
        if True:
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
        # the shirt's cuff: just showing out of the coat's, SHIRT_CUFF_CLEAR off the wrist (its edge reached 1.2 cm
        # past the coat's cuff and 3 mm off: the bent wrist came up through it as a pink patch)
        rw = [max(ray_dist(BODY_BVH, axis(1.0) + ax * dz, d, 0.1) or 0.03 for dz in (0.0, 0.006, 0.012))
              + SHIRT_CUFF_CLEAR for d in dirs[:-1]]
        rw = circ_smooth(rw, 3); rw.append(rw[0])
        span = 0.012 / (b - a).length
        rings = [[a + (b - a) * (t1 + span * k) + d * r for d, r in zip(dirs, rw)] for k in (-1.5, 0.0, 0.6)]
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


def boot_last(foot, n=36, m=24):
    """The boot's foot round the body's foot points (rest pose, toes to -Y): see LAST_*."""
    ys = [p.y for p in foot]
    y_toe, y_heel = min(ys) - LAST_ROOM, max(ys) + BOOT_FOOT_OFF
    length = y_heel - y_toe
    rings = []
    xcs, ws = [], []
    for i in range(n + 1):
        y = y_toe + length * i / n
        band = [p for p in foot if abs(p.y - y) < 0.012] or [min(foot, key=lambda p: abs(p.y - y))]
        x0, x1 = min(p.x for p in band), max(p.x for p in band)
        xcs.append((x0 + x1) / 2); ws.append((x1 - x0) / 2 + BOOT_FOOT_OFF)
    for _ in range(4):  # an even outline (the toes made it lumpy and lopsided)
        xcs = [xcs[0]] + [(xcs[i - 1] + 2 * xcs[i] + xcs[i + 1]) / 4 for i in range(1, n)] + [xcs[-1]]
        ws = [ws[0]] + [(ws[i - 1] + 2 * ws[i] + ws[i + 1]) / 4 for i in range(1, n)] + [ws[-1]]
    for i in range(n + 1):
        t = i / n
        y = y_toe + length * t
        xc, w = xcs[i], ws[i]
        # rounded in plan at the toe and the heel's back
        w *= math.sqrt(max(0.02, min(1.0, (y - y_toe) / 0.075))) * math.sqrt(max(0.02, min(1.0, (y_heel - y) / 0.03)))
        w *= 0.88 + 0.12 * smoothstep(t, 0.0, 0.35)  # a slimmer toe (the portrait's is narrow, a little pointed)
        top = SOLE_H + float(np.interp(t, [a for a, _ in LAST_TOP], [b for _, b in LAST_TOP]))
        bot = SOLE_H + (HEEL_H - SOLE_H) * smoothstep(t, *LAST_ARCH)
        top = max(top, bot + 0.006)
        mid, hh = (top + bot) / 2, (top - bot) / 2
        ring = []
        for k in range(m):
            a = 2 * math.pi * k / m
            ca, sa = math.cos(a), math.sin(a)
            ex = 1.0 if sa > 0 else 2 / 8  # round on top, flat underneath
            x = xc + w * math.copysign(abs(ca) ** (0.8 if sa > 0 else 0.5), ca)
            z = mid + hh * math.copysign(abs(sa) ** ex, sa)
            ring.append(Vector((x, y, z)))
        rings.append(ring)
    bm, grid = loft(rings)
    bm.faces.new(grid[0][::-1]); bm.faces.new(grid[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


BOOT_TWIST_Z = (0.08, 0.22)       # the boot goes over from the foot's bone to the calf's between these heights: the foot
                                  # turned out from the calf (the stance) twists the leather over the ankle gently (with
                                  # the body's weights it crumpled in a knot over the instep)


def boot_weights(co, s):
    wf = 1 - smoothstep(co.z, *BOOT_TWIST_Z)
    return {k: w for k, w in (('foot_' + s, wf), ('calf_' + s, 1 - wf)) if w > 1e-4}


def build_boots(nu=48):
    """Riding boots. The foot is a last round the body's foot (boot_last) voxel-remeshed together with the shaft; the shaft is lofted through slices of the leg (convex hull + ease over the
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
        foot = [v.co.copy() for v in bm.verts if v.co.z < 0.12]
        bm.free()
        bm = boot_last(foot)
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
                if FOLD_Z0 < z < FOLD_Z1:  # creases over the ankle, strongest at the front and sides
                    fade = math.sin(math.pi * (z - FOLD_Z0) / (FOLD_Z1 - FOLD_Z0))
                    ang = math.atan2(d.x, -d.y)
                    depth = (0.5 + 0.5 * -d.y) * (0.7 + 0.3 * math.sin(3.0 * ang + 68.0 * z))
                    r += FOLD_AMP * fade * depth * math.sin(2 * math.pi * (z - FOLD_Z0) / FOLD_PITCH
                                                            + FOLD_SLANT * d.x * sign + FOLD_WAVE * math.sin(2 * ang + sign))
                p = c + d * r
                ring.append(Vector((p.x, p.y, float(z))))
            rings.append(ring)
        sb, _ = loft(rings)
        bmesh.ops.holes_fill(sb, edges=[e for e in sb.edges if e.is_boundary], sides=0)
        bm = merge_bms([bm, sb])
        me = bpy.data.meshes.new('BootTmp'); bm.to_mesh(me); bm.free()
        ob = bpy.data.objects.new('BootTmp', me); sc.collection.objects.link(ob)
        apply_mods(ob, [('REMESH', dict(mode='VOXEL', voxel_size=0.004)),
                        ('SMOOTH', dict(factor=0.6, iterations=16))])
        bm = bmesh.new(); bm.from_mesh(ob.data)
        bpy.data.objects.remove(ob)
        seam = [v for v in bm.verts if ANKLE_SEAM[0] < v.co.z < ANKLE_SEAM[1]]  # the last into the shaft, no crease
        for _ in range(ANKLE_SEAM[2]):
            bmesh.ops.smooth_vert(bm, verts=seam, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
        low = [v.co.xy.copy() for v in bm.verts if v.co.z < HEEL_H + 0.006]
        y_toe, y_heel = min(p.y for p in low), max(p.y for p in low)
        y_breast = y_heel - (y_heel - y_toe) * (1 - LAST_ARCH[1])  # front face of the heel
        # open the top with a straight cut
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, top), plane_no=(0, 0, 1),
                               clear_outer=True)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
        me = bpy.data.meshes.new('BootTmp'); bm.to_mesh(me); bm.free()
        ob = bpy.data.objects.new('BootTmp', me); sc.collection.objects.link(ob)
        apply_mods(ob, [('DECIMATE', dict(ratio=0.5))])
        bm = bmesh.new(); bm.from_mesh(ob.data)
        bpy.data.objects.remove(ob)
        out.append(new_detail('Boot_' + s, bm, lambda v: uv_in('leather', 0.5, 0.5), lambda v, s=s: boot_weights(v.co, s),
                              BOOT_THICK))
        # sole with a welt, and the heel block, from the outline of the boot's bottom
        hull = [low[i] for i in mg.convex_hull_2d(low)]
        cxy = sum(hull, Vector((0.0, 0.0))) / len(hull)
        welt = [p + (p - cxy).normalized() * WELT for p in hull]
        heel_poly = [p - (p - cxy).normalized() * 0.002 for p in welt if p.y > y_breast]
        heel_poly.sort(key=lambda p: math.atan2(p.x - cxy.x, p.y - cxy.y))
        sole = merge_bms([prism(welt, 0.0, SOLE_H), prism(heel_poly, 0.0, HEEL_H)])
        sole.verts.ensure_lookup_table()
        out.append(new_detail('Sole_' + s, sole, lambda v: uv_in('sole', 0.5, 0.5), lambda v, s=s: {'foot_' + s: 1.0}))
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

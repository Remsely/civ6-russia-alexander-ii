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
DETAILS_SPEC = 0.2                # the cloth's and leather's white specular (Specular IOR Level): at 0.5 a white veil
                                  # over the scarlet, pink in the light (the portrait's reds stay deep)
EMBROIDERY_H, THREAD_H = 3.0, 4.0  # px: the gold embroidery raised off the cloth; its threads' relief per unit of light

# Flat colours (linear RGB).
RED = (0.55, 0.014, 0.010)
GOLD = tuple(float(((c / 255 + 0.055) / 1.055) ** 2.4) for c in mat_util.GOLD_SRGB)  # linear
LEATHER = (0.009, 0.009, 0.010)
SOLE = (0.006, 0.005, 0.005)
WHITE = (0.80, 0.78, 0.72)
CLOTH = (0.0034, 0.0037, 0.0058)    # the tunic's wool (build_uniform.CLOTH_RGB)

# Red collar over the tunic's standing collar: a band of one height down from its level top edge, a cone as the
# tunic's stand under it (build_uniform.STAND_LEAN: narrow round the neck at the top, its walls leaning out to the sides
# down to its foot); as in the portrait the halves stand apart at the front, their edges nearly parallel, the tunic's
# dark collar between them up to the top (the white shirt collar's edge over it); the neck stays behind it
# (build_pose.neck_in_collar).
COLLAR_LIFT = 0.001               # off the tunic's stand; its thickness goes outwards (at 2.5 mm and 6 mm the collar stood
                                  # 8.5 mm out of the tunic, ~1.5 cm out of the neck at the top: too wide, a bulky ring)
COLLAR_H = 0.068                  # the band's height, the same all round as a shirt's collar band: its foot as low as
                                  # the portrait's (at 6.8 cm the collar stood ~10 px higher on the neck than the
                                  # portrait's, a small ring under the chin). (Down to where the cloth turned out, at most
                                  # 8.5 cm, the band stood tall up the nape and its foot lay out on the shoulders.)
COLLAR_TUCK = 0.004               # ... its foot this far into the cloth where the shoulder rises into it
CROSS_OVER_FOOT = 0.0               # the neck cross hangs from this far over the corners' foot (build_orders.py): its
                                  # crown over the foot, the cross under the collar, as in the portrait
COLLAR_FRONT_GAP = 0.020          # the opening's half-width at the top: the halves' front edges straight lines at
                                  # x = +-this, the dark tunic and the cross between them ...
COLLAR_FRONT_GAP_BOTTOM = 0.006   # ... and at the foot: a V, as the portrait's (1.6 and 0.9 cm read as a straight
                                  # slot). (As an angle round the neck the edges slanted out on the cone; the collar
                                  # turned per height to stand them up in the 'ref' view came out twisted ~17 deg.)
STAND_DROP = -0.002               # the dark stand between the halves ends this far under their top (over it: 1 mm under
                                  # their rolled top edge, just into the shirt's foot there), the shirt's white edge
                                  # about as thin over it as over the halves, a line across the opening as in the portrait
                                  # (2 mm under their top, 1.1 cm of white stood over it in a band; up to the rolled edge,
                                  # its top stood out of the halves' corners; with the shirt's edge 3 mm over the
                                  # collar, the stand's top came through it in jags)
STAND_UNDER_SHIRT = 0.002         # ... and its top this far inside the shirt collar's outside (the shirt 1.2 mm thick)
COLLAR_REPEATS, CUFF_REPEATS, BELT_REPEATS = 1, 2, 4  # mirrored repeats of the generated pictures (textures/gen)
COLLAR_HALF_LEN = 0.22            # a half's length round the neck, front edge to back seam (for the texture's edges)
COLLAR_PIPING = 0.004             # the portrait's red piping round each half's top, front and bottom edges ...
COLLAR_FRAME_GAP, COLLAR_FRAME_LINE = 0.0018, 0.0012  # ... the thin gold line inside it (this far in, this wide)
COLLAR_OAK_ROWS = (0.115, 0.885)  # the generated band's rows between its gold cords (the oak branch alone)
PIPING_H = 4.0                    # px: the piping's round relief
COLLAR_RED_SRGB = (150, 16, 9)   # the collar's cloth: the portrait's (median 142, 19, 9; at RED, the piping's, it
                                  # came out a flat orange-red)
COLLAR_THICK = 0.0035             # (at 4 mm and no rolled edge its top read as a thin sheet; the rolled edge makes it ~8 mm)
STAND_ROWS, STAND_COLS = 7, 13    # the dark stand between the halves: rows up it, columns across
SHIRT_SHOW = 0.0175               # the shirt collar's edge this far over the bottom of its band (~3 mm over the red
                                  # collar's rolled top: the portrait's white line all along it; at 14.5 mm it stood
                                  # 0.7 mm over the roll and showed only in the opening)
SHIRT_IN = 0.006                  # the white shirt collar this far inside the tunic collar's outside: just inside the
                                  # red collar's rolled top edge (COLLAR_ROLL_IN) and the tunic's own inside (the neck,
                                  # built after it, fills it), its edge a white line along the collar's top, as in the
                                  # portrait (4.5 mm in, it ran through the rolled edge and showed over it in ragged
                                  # white flecks; 13 mm in, the neck in it was ~7 mm thinner than the body's: a stalk)
COLLAR_ROLL_IN = 0.003            # the rolled top edge turns in over the tunic collar's edge to this far inside it
# Buttons down the closure, on the wearer's right of the piped edge; some hide under the sash.
# Measured on alexander_ii_full.png (rows of the 'ref' view: z ~ (1510 - row) * 1.397 mm): on his left of the piping
# the pencil's crook comes from a button at row 385 and the last one over the belt is at 540; on his right the one
# over the belt is at 510; the rest lie under the sash. The two rows stagger (the portrait's do), ~7.2 cm apart.
BUTTON_R, BUTTON_H = 0.0115, 0.0065  # the portrait's are big gilt domes, ~2.5 cm across (1.7 cm read as studs)
BUTTON_SPOTS = [(-0.030, 1.614), (-0.030, 1.542), (-0.030, 1.470), (-0.030, 1.397),  # (dx from the flap edge, z)
                (0.055, 1.572), (0.047, 1.500), (0.039, 1.428), (0.031, 1.356)]  # his left row slants in to the
                                  # belt as the portrait's does (its pencil button 33 px off the piping, the last 13 px)
# Belt over the waist seam of the tunic; buckle plate taller than the belt, its left end an arrow (both corners cut).
BELT_THICK, BELT_EASE = 0.004, 0.001
BELT_RED, BELT_EDGE = 0.12, 0.025  # across the belt: red borders to this, a gold edge outside them (the portrait's
                                  # belt: 40 px high, its red borders 4 px each, the rest the galloon)   # height and profile come from build_uniform.py (it takes the tunic in)
BUCKLE_W, BUCKLE_H, BUCKLE_RAISE = 0.112, 0.074, 0.004  # a little over the belt's height (larger, it dominated the waist)
BUCKLE_CUT_X, BUCKLE_CUT_Z = 0.015, 0.031  # its left corners (the picture's) cut off steeply, top and bottom alike: the
                                  # end an arrow pointing round the waist (the portrait's top cut 7-10 x 21 of its
                                  # 84 x 46 px plate); the right corners square
BUCKLE_CLOSURE = 0.8               # the closure runs through the buckle this far across it (from the picture's left)
BUCKLE_RIM, BUCKLE_FRAME = 3.0, 5.5  # mm, from the plate's edge in: the red enamel rim, the gold frame (a polished
                                  # moulding, twisted; at 4.6 mm chased on a matted ground it read as a thin line)
BUCKLE_EAGLE, BUCKLE_EAGLE_AT = 0.86, (0.0, 0.0)  # the eagle this share of the field's height, its middle here (m)
BUCKLE_EAGLE_GROUND = (64, 66, 71)  # sRGB: the dark grey ground round the bird, hugging its outline (the portrait's)
BUCKLE_EAGLE_EDGE = (2.4, 4.0)    # mm: that ground's width round the bird, and the gaps in it it closes over
BUCKLE_STAFF = (5.5, 4.6, 11.5, 2.0)  # mm: the crossed lances behind the bird, corner to corner on the red field: the
                                  # shaft as wide as the frame, the spearhead's half width and length, its point this
                                  # far in from the frame (balls and trefoils on staves read as bones)
BUCKLE_TROPHY = ((1.2, 0.9), 7.0, (11.0, 7.0, 0.9), (17.0, 2.4))  # mm: the arms of the trophy round the bird, all
                                  # gold as the portrait's: a fine line inside the frame (this far in, this wide); a
                                  # round shield either side of the bird (radius); a banner on each upper lance under
                                  # its head (along it, out from it, its wave); a pile of three balls either side of
                                  # its tail (x off the middle, a ball's radius) - with the lances alone the red field
                                  # read bare
BUCKLE_RELIEF = 1.0               # the relief's heights times their true millimetres
BUCKLE_GUILLOCHE = 240            # the field's engine-turned rays under the red enamel, round the whole turn
# Cuffs: a band over the end of the sleeve with piped (beaded) edges; a gold flap with three buttons outside.
CUFF_RAISE, CUFF_THICK, CUFF_LIP, CUFF_BEAD = 0.002, 0.003, 0.012, 0.003
SHIRT_CUFF_CLEAR = 0.006
FLAP_ACROSS, FLAP_ALONG, FLAP_RAISE = 0.068, 0.074, 0.003
FLAP_TURN = {'l': 75.0, 'r': 0.0}  # degrees the flap is turned on round the forearm from its outer side: the stance
                                  # turns the forearm only by aiming it, so his left one's flap came out on the far
                                  # side of the wrist, under it - the portrait's is on top, facing the viewer
# Riding boots up to BOOT_TOP, wider than the tucked-in trousers; sole with a welt, heel, accordion folds over the
# ankle, a spur at the heel.
BOOT_EASE, BOOT_FOOT_OFF, BOOT_THICK = 0.010, 0.006, 0.003  # (the portrait's shafts are slim: ~11.5 cm across
                                  # at the top, narrowing to the ankle)
BOOT_ROUGH = 0.38                 # polished calf: the portrait's boots shine in soft broad highlights along the shaft and
                                  # toe (at 0.24 small mirror-sharp ones: rubber)
# The foot of the boot: a last lofted along the foot (cross-sections round on top, flat underneath), as wide as the body's
# foot plus BOOT_FOOT_OFF at every point along it; its top line (z over the sole, by the share of the length from the
# toe tip) - a low rounded toe box rising over the instep into the shaft; the bottom on the sole in front, on the heel
# behind, the arch between. The body's foot inflated (and decimated) came out a crumpled sock on a flat plate.
LAST_TOE_ROUND = 0.035            # the toe's end rounded over this far back (side view)
LAST_TOE_PLAN = 0.06              # ... and in plan
LAST_TOP = ((0.0, 0.024), (0.03, 0.034), (0.08, 0.045), (0.2, 0.055), (0.4, 0.068), (0.6, 0.090), (0.78, 0.112),
            (1.0, 0.112))  # (the instep at 0.115-0.14 made a block round the ankle, 13 cm front to back up to 15 cm
                           # high: the boot did not narrow at the ankle as the portrait's does)
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
    'buckle': (0.0, 0.3125, 0.5, 0.640625),  # 1024 x 672 px, the plate's 112 x 74 mm: the eagle's detail reads
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
POSE_POSITION = rig.data.pose_position
TEXTURES_ONLY = 'textures' in (sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])  # (-- textures)
BUCKLE_ONLY = 'buckle' in (sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])  # (-- buckle: on the rest
# file; the atlas, and the buckle's shape and UVs made afresh in place there and in the leader - the plate posed there
# as the old one was, a rigid piece: everything else as it is)
rig.data.pose_position = 'REST'
uni, under, h = bpy.data.objects['Uniform'], bpy.data.objects['BodyUnder'], bpy.data.objects['Human']
bones = {b.name: (rig.matrix_world @ b.head_local, rig.matrix_world @ b.tail_local) for b in rig.data.bones}
for o in [] if TEXTURES_ONLY or BUCKLE_ONLY else list(bpy.data.objects):  # previous run
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


def collar_frame(w, hh):
    """Distances (metres) from the half's top, bottom and front edges per texel, and the nearest of them."""
    u, v = np.meshgrid(np.linspace(0, 1, w), np.linspace(0, 1, hh))
    du, dv = u * COLLAR_HALF_LEN, v * COLLAR_H
    return u, v, np.minimum(np.minimum(dv, COLLAR_H - dv), du)


def collar_tex(w, hh):
    """One half of the collar, front edge at u = 0, back centre at u = 1, as the portrait's: scarlet cloth, a red
    piping round its top, front and bottom edges, a thin gold line inside it, and the oak branch inside that (the
    generated band without its gold cords - the portrait has none - one mirrored repeat a half: at two the leaves came
    out squeezed to half their width, a dense small pattern)."""
    u, v, e = collar_frame(w, hh)
    inset = COLLAR_PIPING + COLLAR_FRAME_GAP * 2 + COLLAR_FRAME_LINE  # the oak inside the gold line
    ui = np.clip((u * COLLAR_HALF_LEN - inset) / (COLLAR_HALF_LEN - inset), 0, 1)
    vi = np.clip((v * COLLAR_H - inset) / (COLLAR_H - 2 * inset), 0, 1)
    oak = sample(load_gen('collar_oak'), mirrored(ui, COLLAR_REPEATS), COLLAR_OAK_ROWS[0]
                 + (COLLAR_OAK_ROWS[1] - COLLAR_OAK_ROWS[0]) * vi)
    g = np.clip(gold_mask(oak) * 1.5, 0, 1)[..., None] * (e > inset - 0.0005)[..., None]  # (at 1x the leaves' darker
    # threads let the red through: pale pink leaves)
    red = np.array(COLLAR_RED_SRGB, np.float32) / 255
    c = red * (1 - g) + oak * g
    line = COLLAR_PIPING + COLLAR_FRAME_GAP
    aa = 0.0003  # (edges eased over this: no jaggies)
    w_line = (np.clip((e - line + aa) / aa, 0, 1) * np.clip((line + COLLAR_FRAME_LINE + aa - e) / aa, 0, 1))[..., None]
    c = c * (1 - w_line) + np.array(mat_util.GOLD_SRGB, np.float32) / 255 * w_line
    w_pipe = np.clip((COLLAR_PIPING + aa - e) / aa, 0, 1)[..., None]
    return c * (1 - w_pipe) + np.array(to_srgb(RED), np.float32) * w_pipe  # (the cuffs' red: brighter than the cloth)


def collar_piping_height(w, hh):
    """The piping's round profile (0..1) for the relief."""
    t = np.clip(collar_frame(w, hh)[2] / COLLAR_PIPING, 0, 1)
    return np.sqrt(np.clip(1 - (2 * t - 1) ** 2, 0, 1)) * (t < 1)


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


def buckle_outline():
    """The plate's outline (metres over it, x to the picture's right, y up), anticlockwise: a rectangle with both its
    left corners cut off steeply, an arrow, as the portrait's."""
    w, h = BUCKLE_W / 2, BUCKLE_H / 2
    return [(-w + BUCKLE_CUT_X, -h), (w, -h), (w, h), (-w + BUCKLE_CUT_X, h), (-w, h - BUCKLE_CUT_Z),
            (-w, -h + BUCKLE_CUT_Z)]


def inset_of(poly, X, Y):
    """mm in from the outline (positive inside) and, for patterns along it, the length along it of the nearest edge."""
    inset = np.full(np.shape(X), 1e9, np.float32)
    along = np.zeros(np.shape(X), np.float32)
    run = 0.0
    for i, (ax, ay) in enumerate(poly):
        bx, by = poly[(i + 1) % len(poly)]
        L = math.hypot(bx - ax, by - ay)
        tx, ty = (bx - ax) / L, (by - ay) / L
        d = (-(X - ax) * ty + (Y - ay) * tx) * 1000  # in from this edge (the outline runs anticlockwise)
        t = ((X - ax) * tx + (Y - ay) * ty) * 1000
        near = d < inset
        inset = np.where(near, d, inset)
        along = np.where(near, run + t, along)
        run += L * 1000
    return inset, along


def grow(a, r):
    """a (0..1) dilated r pixels, near round (square and cross steps in turn)."""
    for k in range(int(r)):
        b = np.maximum(np.roll(a, 1, 0), np.roll(a, -1, 0))
        b = np.maximum(b, np.maximum(np.roll(a, 1, 1), np.roll(a, -1, 1)))
        if k % 2:
            b = np.maximum.reduce([b, np.roll(np.roll(a, 1, 0), 1, 1), np.roll(np.roll(a, 1, 0), -1, 1),
                                   np.roll(np.roll(a, -1, 0), 1, 1), np.roll(np.roll(a, -1, 0), -1, 1)])
        a = np.maximum(a, b)
    return a


def buckle_parts(w, hh):
    """The plate as the portrait's, drawn over the plate's own millimetres (u along it, v up it): a red enamel rim
    round the edge; inside it a thick polished gold frame following the outline (a twisted moulding); inside the
    frame a red enamel field over engine turning, a fine gold line round it, and a gold trophy: two lances crossed
    corner to corner behind the bird (as wide as the frame, a spearhead at each end, a banner under the upper heads),
    a round shield either side, a pile of balls either side of the tail, and in the middle the empire's double-headed eagle in gold
    on a dark grey ground hugging its outline (textures/gen/eagle_imperial.png: the lesser arms of 1883, public domain,
    after Wikimedia Commons; its colours give the gold's relief). Returns albedo, metal, roughness, relief (pixels)."""
    u, v = np.meshgrid(np.linspace(0, 1, w), np.linspace(0, 1, hh))
    X, Y = (u - 0.5) * BUCKLE_W, (v - 0.5) * BUCKLE_H
    mm = (w - 1) / (BUCKLE_W * 1000)  # pixels per millimetre
    poly = buckle_outline()
    inset, along = inset_of(poly, X, Y)
    gold = np.array(mat_util.GOLD_SRGB, np.float32) / 255
    red = np.array(to_srgb(RED), np.float32) * 1.12
    r0, r1 = BUCKLE_RIM, BUCKLE_RIM + BUCKLE_FRAME  # mm: the rim, then the frame
    aa = 0.12

    def band(a, b):
        return np.clip((inset - a) / aa + 0.5, 0, 1) * np.clip((b - inset) / aa + 0.5, 0, 1)

    frame = band(r0, r1)
    field = np.clip((inset - r1) / aa + 0.5, 0, 1)
    # the frame: a rounded moulding, twisted (grooves slanting across it), a fine fillet each side
    acr = np.clip((inset - r0) / BUCKLE_FRAME, 0, 1)  # 0..1 across it
    dome = np.sin(acr * math.pi) ** 0.5
    twist = 0.5 + 0.5 * np.cos((along + (inset - r0) * 1.1) / 2.2 * 2 * math.pi)
    fil = np.maximum(band(r0, r0 + 0.5), band(r1 - 0.5, r1))
    frame_h = frame * (0.6 * dome + 0.18 * dome * twist + 0.15 * fil)
    # the eagle: centred in the field, as tall as the field leaves room for
    eimg = bpy.data.images.load(os.path.join(TEXDIR, 'gen', 'eagle_imperial.png'), check_existing=False)
    ew_, eh_ = eimg.size
    e = np.array(eimg.pixels[:], np.float32).reshape(eh_, ew_, 4)
    bpy.data.images.remove(eimg)
    e[..., :3] *= e[..., 3:]  # premultiplied: no dark fringe where it is sampled between the bird and the clear
    EH = (BUCKLE_H - 2 * r1 / 1000) * BUCKLE_EAGLE
    EW = EH * ew_ / eh_
    ex, ey = BUCKLE_EAGLE_AT
    eu, ev = (X - ex) / EW + 0.5, (Y - ey) / EH + 0.5
    inside = (eu >= 0) & (eu <= 1) & (ev >= 0) & (ev <= 1)
    es = sample(e, eu, ev) * inside[..., None]
    ea = np.clip(es[..., 3], 0, 1) * field
    ec = es[..., :3] / np.maximum(es[..., 3:], 1e-4)
    lum = ec @ np.array([0.3, 0.55, 0.15], np.float32)  # the arms' light and dark: the feathers' lines, the crowns
    # its ground: the bird's outline grown, the gaps in it closed (grown further, then shrunk back)
    gw, gc = BUCKLE_EAGLE_EDGE
    solid = (ea > 0.5).astype(np.float32)
    closed = 1 - grow(1 - grow(solid, round((gw + gc) * mm)), round(gc * mm))
    ground = np.clip(mat_util.blur(closed, max(1, round(0.3 * mm))) * 2 - 0.5, 0, 1) * field
    # the lances: crossed corner to corner through the middle behind the bird, each end a spearhead on a collar
    sw, hw, hl, s_in = BUCKLE_STAFF
    staff = np.zeros_like(X)
    staff_h = np.zeros_like(X)
    ends = 0
    for sy in (1.0, -1.0):
        dx_, dy_ = (BUCKLE_W / 2 - r1 / 1000), sy * (BUCKLE_H / 2 - r1 / 1000)
        L = math.hypot(dx_, dy_)
        dx_, dy_ = dx_ / L, dy_ / L
        t = (X - ex) * dx_ + (Y - ey) * dy_
        n = (-(X - ex) * dy_ + (Y - ey) * dx_) * 1000
        for sgn in (1.0, -1.0):  # out along the lance each way: its point s_in short of the frame
            ts = np.linspace(0.0, L * 1.2, 600)
            ins, _ = inset_of(poly, ex + sgn * ts * dx_, ey + sgn * ts * dy_)
            hit = ins < r1 + s_in
            tip = (ts[np.argmax(hit)] if hit.any() else ts[-1]) * 1000
            sa = sgn * t * 1000  # mm out along it
            base = tip - hl
            shaft = (sa > 0) & (sa < base - 1.6)
            q = np.abs(n) / (sw / 2)
            staff = np.maximum(staff, np.clip((1 - q) * sw / 2 / aa, 0, 1) * shaft)
            staff_h = np.maximum(staff_h, np.sqrt(np.clip(1 - q ** 2, 0, 1)) * shaft)
            # the collar under the head: a ring a little wider than the shaft
            col = (sa >= base - 1.6) & (sa < base)
            qc = np.abs(n) / (sw / 2 + 0.8)
            staff = np.maximum(staff, np.clip((1 - qc) * (sw / 2 + 0.8) / aa, 0, 1) * col)
            staff_h = np.maximum(staff_h, 1.15 * np.sqrt(np.clip(1 - qc ** 2, 0, 1)) * col)
            # the head: a leaf, widest a third of the way up, to a point; a ridge down its middle
            f = np.clip((sa - base) / hl, 0, 1)
            half = hw * np.clip(np.where(f < 0.33, np.sin(f / 0.33 * math.pi / 2) ** 0.6, (1 - f) / 0.67), 0, 1)
            half = np.maximum(half, sw / 2 * (f < 0.12))
            head = (sa >= base) & (sa <= tip)
            qh = np.abs(n) / np.maximum(half, 1e-3)
            staff = np.maximum(staff, np.clip((half - np.abs(n)) / aa, 0, 1) * head)
            staff_h = np.maximum(staff_h, (0.55 * np.clip(1 - qh, 0, 1) + 0.45 * np.clip(1 - qh, 0, 1) ** 0.3) * head)
            ends += 1
    # the trophy: shields either side, banners on the upper lances, piles of balls by the tail, a line inside the frame
    (li, lw_), shr, (bl, bw_, bwave), (bx_, br_) = BUCKLE_TROPHY

    def add(mask, h):
        nonlocal staff, staff_h
        staff = np.maximum(staff, mask)
        staff_h = np.maximum(staff_h, h * mask)
    add(band(r1 + li, r1 + li + lw_), 0.7)
    ins_c, _ = inset_of(poly, np.array([ex]), np.array([ey]))
    for sx in (-1.0, 1.0):
        # the shield: half way between the bird's ground and the frame at the middle's height
        xs = np.linspace(ex, ex + sx * BUCKLE_W / 2, 400)
        gi = ground[hh // 2, np.clip(((xs / BUCKLE_W + 0.5) * (w - 1)).astype(int), 0, w - 1)]
        x_g = xs[np.argmax(gi < 0.05)] if (gi < 0.05).any() else ex
        ins_x, _ = inset_of(poly, xs, np.full_like(xs, ey))
        x_f = xs[np.argmax(ins_x < r1 + li + lw_)] if (ins_x < r1 + li + lw_).any() else xs[-1]
        cx_, cy_ = (x_g + x_f) / 2, ey
        rr = np.hypot(X - cx_, Y - cy_) * 1000
        th = np.arctan2(Y - cy_, X - cx_)
        m_ = np.clip((shr - rr) / aa, 0, 1)
        h_ = np.where(rr > shr - 1.0, 1.0, 0.55 + 0.12 * np.cos(th * 16) * np.clip((rr - 2.2) / 2, 0, 1))
        h_ = np.maximum(h_, 1.25 * np.sqrt(np.clip(1 - (rr / 2.2) ** 2, 0, 1)))  # the boss
        add(m_, h_)
        # the pile of balls by the tail, on the frame's line under it
        yb = -BUCKLE_H / 2 + (r1 + li + lw_ + 0.6 + br_) / 1000
        for qx, qy in ((-br_, 0.0), (br_, 0.0), (0.0, br_ * 1.73)):
            cxb, cyb = ex + sx * bx_ / 1000 + qx / 1000, yb + qy / 1000
            rb = np.hypot(X - cxb, Y - cyb) * 1000
            add(np.clip((br_ - rb) / aa, 0, 1), np.sqrt(np.clip(1 - (rb / br_) ** 2, 0, 1)) * 1.1)
    for sgn_x in (-1.0, 1.0):
        # the banner: on the upper lance's outer side (towards the top), from under its head back along it, waving
        dx_, dy_ = sgn_x * (BUCKLE_W / 2 - r1 / 1000), (BUCKLE_H / 2 - r1 / 1000)
        L = math.hypot(dx_, dy_)
        dx_, dy_ = dx_ / L, dy_ / L
        ts = np.linspace(0.0, L * 1.2, 600)
        ins, _ = inset_of(poly, ex + ts * dx_, ey + ts * dy_)
        hit = ins < r1 + BUCKLE_STAFF[3]
        tip = (ts[np.argmax(hit)] if hit.any() else ts[-1]) * 1000
        a0 = tip - BUCKLE_STAFF[2] - 1.6 - 0.3  # mm out along it: the banner's end under the head
        nx_, ny_ = -dy_, dx_
        if ny_ < 0:
            nx_, ny_ = -nx_, -ny_
        sa = ((X - ex) * dx_ + (Y - ey) * dy_) * 1000
        na = ((X - ex) * nx_ + (Y - ey) * ny_) * 1000
        s0 = np.clip((a0 - sa) / bl, 0, 1)  # 0 at the head's end, 1 back along it
        wave = bwave * np.sin(s0 * 2 * math.pi + na / bw_ * 1.6)
        sa_w = sa + wave
        t_ = na - BUCKLE_STAFF[0] / 2  # out from the shaft's edge
        m_ = (np.clip((a0 - sa_w) / aa, 0, 1) * np.clip((sa_w - (a0 - bl)) / aa, 0, 1)
              * np.clip(t_ / aa + 0.5, 0, 1) * np.clip((bw_ - t_) / aa, 0, 1))
        folds = 0.5 + 0.5 * np.cos((sa_w - a0) / bl * 3 * 2 * math.pi + t_ * 0.35)
        fringe = (t_ > bw_ - 1.3) * (0.5 + 0.5 * np.cos(sa_w * 2 * math.pi / 1.2))
        add(m_, 0.55 + 0.25 * folds + 0.25 * fringe)
    staff = staff * field * (1 - ground)
    staff_h = staff_h * staff
    rays = 0.5 + 0.5 * np.cos(np.arctan2(Y - ey, X - ex) * BUCKLE_GUILLOCHE)  # the engine turning
    # colours: red; the frame gold; the field red over the turning; the lances gold; the ground dark grey; the bird gold
    c = np.tile(red, X.shape + (1,))
    c = c * (1 - field[..., None] * (0.06 * (1 - rays))[..., None])
    c = c * (1 - frame[..., None]) + (gold * (0.9 + 0.1 * dome * (0.6 + 0.4 * twist))[..., None]) * frame[..., None]
    c = c * (1 - staff[..., None]) + gold * (0.88 + 0.12 * staff_h)[..., None] * staff[..., None]
    gr = np.array(BUCKLE_EAGLE_GROUND, np.float32) / 255
    c = c * (1 - ground[..., None]) + gr * ground[..., None]
    tone = 0.74 + 0.26 * np.clip(lum * 1.4, 0, 1)  # the arms' dark feathers a deeper gold (fine relief only)
    c = c * (1 - ea[..., None]) + gold * tone[..., None] * ea[..., None]
    m = np.maximum.reduce([frame, staff, 0.45 * ground, ea])
    ro = (0.3 * np.clip(1 - frame - field, 0, 1) + frame * (0.3 - 0.08 * dome)
          + field * (1 - staff) * (1 - ground) * (0.3 - 0.06 * rays))
    ro = ro * (1 - staff) + 0.24 * staff
    ro = ro * (1 - ground) + 0.42 * ground
    ro = ro * (1 - ea) + (0.32 - 0.08 * np.clip(lum * 1.4, 0, 1)) * ea
    # relief (mm, true scale; normals() takes pixels): the frame, the lances and the bird raised, the bird's detail by
    # its picture's light
    hgt = (0.55 * frame_h + 0.45 * staff_h + 0.1 * ground
           + 0.3 * mat_util.blur(ea, max(1, round(0.3 * mm))) + 0.22 * ea * np.clip(lum * 1.4, 0, 1)
           + 0.01 * rays * field)
    hgt = hgt * mm * BUCKLE_RELIEF
    print('buckle plate: %d x %d px (%.1f px/mm), rim %.1f mm, frame %.1f mm, the eagle %.0f x %.0f mm gold on dark '
          'grey, %d spearheads, shields, banners, balls' % (w, hh, mm, r0, BUCKLE_FRAME, EW * 1000, EH * 1000, ends))
    return c.astype(np.float32), m.astype(np.float32), np.clip(ro, 0.05, 1).astype(np.float32), hgt.astype(np.float32)


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
    x0, y0, x1, y1 = px('collar')
    height[y0:y1, x0:x1] += collar_piping_height(x1 - x0, y1 - y0) * PIPING_H
    put('cuff', cuff_tex, raw=True)
    put('belt', belt_tex, raw=True)
    x0, y0, x1, y1 = px('buckle')  # a chased plate, not embroidery: its own metal, roughness and relief
    rgb[y0:y1, x0:x1], metal[y0:y1, x0:x1], rough[y0:y1, x0:x1], height[y0:y1, x0:x1] = buckle_parts(x1 - x0, y1 - y0)
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
    mat = mat_util.material('Details', albedo, mr, nrm, spec=DETAILS_SPEC)
    print('atlas', ALBEDO_OUT)
    return mat


MAT = build_atlas()
if TEXTURES_ONLY:  # the maps and the material only, saved into the open file (the leader); the meshes as they are
    rig.data.pose_position = POSE_POSITION
    bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath, compress=True)
    print('textures only: saved', bpy.data.filepath)
    sys.exit(0)


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
    thetas = [gap + (2 * math.pi - 2 * gap) * j / (nu - 1) for j in range(nu)]  # from the opening's middle
    dv = lambda t: Vector((math.sin(t), -math.cos(t), 0.0))  # noqa: E731
    dirs = [dv(t) for t in thetas]
    lean = P['STAND_LEAN']
    def top_at(t):  # as build_uniform.stand_top (head_shape.collar_top: the ring tilted forward)
        return P['STAND_TOP_BACK'] + (P['STAND_TOP_FRONT'] - P['STAND_TOP_BACK']) * (1 + math.cos(t)) / 2
    cloth = lambda z, d: ray_dist(UNI_BVH, c0.to_3d() + Vector((0, 0, z)), d, 0.16)
    tops = [top_at(t) + 0.001 for t in thetas]  # over the tunic's top edge
    # one clean band: the radius round the neck from the cloth just under the top edge, smoothed hard (the rays catch
    # the cloth's dents and folds); down from there leaning out as the stand's cone does, COLLAR_H down - or to where
    # the shoulder rises into the cone, its foot tucked in there (carried on down over the shoulder, its foot turned
    # out along it in a lip: the collar slid onto the shoulders)
    ctr = c0.to_3d()
    r_top = circ_smooth([(cloth(zt - 0.006, d) or 0.08) - lean * 0.006 for zt, d in zip(tops, dirs)], 8)
    bots = []
    for zt, d, r0 in zip(tops, dirs, r_top):
        z = zt - 0.02
        while z > zt - COLLAR_H:
            r = cloth(z, d)
            if r is not None and r > r0 + lean * (zt - z) + 0.001:
                break
            z -= 0.002
        bots.append(max(z - COLLAR_TUCK, zt - COLLAR_H))
    bots = circ_smooth(bots, 12)  # (at 3, the wider collar's foot stepped up where the shoulder rises into it)
    rings = []
    r_front = (r_top[0] + r_top[-1]) / 2 + COLLAR_LIFT
    zb_front = (bots[0] + bots[-1]) / 2

    def gap_at(f):  # the opening's half-angle at height f (0 foot, 1 top): its edges straight down at x = +-half-width
        hw = COLLAR_FRONT_GAP_BOTTOM + (COLLAR_FRONT_GAP - COLLAR_FRONT_GAP_BOTTOM) * f
        return math.asin(hw / (r_front + lean * (tops[0] - zb_front) * (1 - f)))
    for i in range(nv):
        f = i / (nv - 1)
        g = gap_at(f)
        ring = []
        for j, (zb, zt) in enumerate(zip(bots, tops)):
            t = g + (2 * math.pi - 2 * g) * j / (nu - 1)
            d = dv(t)
            z = zb + (zt - zb) * f
            # straight down the cone (laid on the cloth under its foot, it turned out along the shoulders in a lip)
            ring.append(ctr + Vector((0, 0, z)) + d * (r_top[j] + COLLAR_LIFT + lean * (zt - z)))
        rings.append(ring)
    # the piped top edge rolls over the tunic collar's edge to its inside
    # (its rise down to none at the front edges: there it stood over the shirt in the opening in a red tip)
    rise = [0.003 * min(1.0, j / 2, (nu - 1 - j) / 2) for j in range(nu)]
    rings.append([Vector((c0.x, c0.y, p.z + rise[j])) + (Vector((p.x, p.y, 0)) - c0.to_3d()).normalized()
                  * ((p.xy - c0).length - COLLAR_LIFT - COLLAR_ROLL_IN) for j, p in enumerate(rings[-1])])
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
    collar['dip'] = CROSS_OVER_FOOT  # (build_orders.py)
    # the tunic's dark stand filling the opening between the halves (no neck shows through)
    # (rows like the halves', widening downwards with them: two rows only, the cloth crumpled it into a twisted strip)
    # (leaning as the halves' front edges do and no lower than them: further out, its foot stood out in front of
    # theirs in a black corner)
    # the white shirt collar's radius round the neck (below), from the cloth under the collar's top
    full = [2 * math.pi * j / (2 * nu) for j in range(2 * nu)]  # (at nu its edge sagged between two vertices by the
    # opening's corners: the red collar's rolled end showed over it)
    rns = circ_smooth([cloth(top_at(t) - 0.005, Vector((math.sin(t), -math.cos(t), 0.0))) or 0.07 for t in full], 32)  # (as smooth round as 8 rounds at half the vertices: less, it bulged into the rolled edge)

    def shirt_out(t):  # the shirt's outside in the opening (over the stand) in the direction t
        x = (t % (2 * math.pi)) / (2 * math.pi) * len(rns)
        j = int(x)
        return rns[j % len(rns)] + (rns[(j + 1) % len(rns)] - rns[j % len(rns)]) * (x - j) + COLLAR_LIFT - 0.0005
    rs = []
    zb0 = max(bots[0], bots[-1])
    rr_top = (r_top[0] + r_top[-1]) / 2 + COLLAR_LIFT - 0.0015 + lean * STAND_DROP
    for k in range(STAND_ROWS):
        f = k / (STAND_ROWS - 1)
        z = zb0 + (tops[0] - STAND_DROP - zb0) * f
        rr = (r_top[0] + r_top[-1]) / 2 + COLLAR_LIFT - 0.0015 + lean * (tops[0] - z)
        g = gap_at(f) * 1.5
        row = []
        for t in [-g + 2 * g * q / (STAND_COLS - 1) for q in range(STAND_COLS)]:
            d = dv(t)
            # up to the shirt over it: its top just inside the shirt's lower edge (at the halves' corners' radius,
            # 1.2 cm behind the shirt over the middle of the opening, the neck showed between them from below)
            # (in the opening only: under the halves, out as far, it stood out of their front edges in a black wedge)
            # (as the shirt over it comes out: further out than it by the halves' edges, it came through it)
            inside = 1 - smoothstep(abs(t), gap_at(f) * 0.7, gap_at(f) * 0.92)
            R = rr + (shirt_out(t) - STAND_UNDER_SHIRT - rr_top) * smoothstep(f, 0.3, 1.0) * inside
            rc = cloth(z, d)
            # (out over the cloth at most 1 mm: further, its top stood out of the halves' rolled corners in a dark lip)
            row.append(ctr + Vector((0, 0, z)) + d * (min(max(R, rc + 0.002), R + 0.001) if rc is not None else R))
        rs.append(row)
    bm, grid = loft(rs, closed=False)
    outward_normals(bm, lambda p: Vector((c0.x, c0.y, p.z)))
    stand = new_detail('CollarStand', bm, {v: uv_in('cloth', 0.5, 0.5) for row in grid for v in row},
                       lambda v: UNI_W.at(v.co), 0.002)
    # white shirt collar showing above the top edge, between the neck and the tunic's collar: a closed ring (its ends
    # at the halves' meeting poked out through the slit in white flecks)
    rings = []
    for k in range(2):  # (round the cloth's dents unsmoothed, its ring came out notched)
        ring = []
        for t, rn in zip(full, rns):
            d = Vector((math.sin(t), -math.cos(t), 0.0))
            zt = top_at(t) + 0.001
            # in the opening between the halves it lies over the dark stand's top and the tunic's own collar edge
            # (inside them, that edge came through it in black and red jags), its foot up by the halves' rolled top:
            # only its edge showing there too, as over them
            g = gap_at(1.0)
            front = 1 - smoothstep(min(t, 2 * math.pi - t), g * 0.7, g * 0.92)
            up = 1 - smoothstep(min(t, 2 * math.pi - t), g * 0.92, g * 1.15)  # (its foot up to under the halves:
            # coming down with it inside them, it showed in a white tooth at each corner)
            z = zt - 0.008 + 0.0095 * up * (1 - k) + SHIRT_SHOW * k  # its edge over the collar's top
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
    through the wearer's left) and in its tilted plane (mat_util.belt_z), buckle placed on the closure as in the
    picture, tilted with it."""
    hb = P['BELT_H']
    c = Vector(P['BELT_C'])
    prof = list(P['BELT_PROFILE'])
    n = len(prof)

    def radius(theta):  # theta from the front (-Y) towards +X
        f = (theta % (2 * math.pi)) / (2 * math.pi) * n
        k = int(f) % n
        return prof[k] + (prof[(k + 1) % n] - prof[k]) * (f - int(f)) + BELT_EASE

    thetas = [math.pi + 2 * math.pi * j / nu for j in range(nu + 1)]  # j = 0 at the back; seam vertices duplicated

    def at(t, r, dz):  # the point round the belt at theta t, radius r, dz over its middle
        p = c + Vector((math.sin(t), -math.cos(t))) * r
        return Vector((p.x, p.y, mat_util.belt_z(P, p.x, p.y) + dz))

    rings = [[at(t, radius(t), -hb / 2 + hb * i / (nv - 1)) for t in thetas] for i in range(nv)]
    bm, grid = loft(rings, closed=False)
    outward_normals(bm, lambda p: Vector((c.x, c.y, p.z)))
    uvs = {v: uv_in('belt', j / nu, i / (nv - 1)) for i, row in enumerate(grid) for j, v in enumerate(row)}
    belt = new_detail('Belt', bm, uvs, lambda v: UNI_W.at(v.co), -BELT_THICK)
    # Buckle: a plate curved over the belt, taller than it, its left corners cut off (an arrow) as in the picture.
    k = 11
    pts, uv = [], []
    dx = P['FLAP_X'] - (BUCKLE_CLOSURE - 0.5) * BUCKLE_W  # buckle centre
    t0 = math.asin(max(-1.0, min(1.0, (dx - c.x) / radius(0.0))))
    bc = BUCKLE_CUT_Z / BUCKLE_H
    for i in range(k):
        # rows: 3 spans through the bottom cut, 4 between the cuts' feet, 3 through the top cut
        b = bc * i / 3 if i <= 3 else bc + (1 - 2 * bc) * (i - 3) / 4 if i <= 7 else 1 - bc + bc * (i - 7) / 3
        row, urow = [], []
        for j in range(k):
            a = j / (k - 1)
            x = (a - 0.5) * BUCKLE_W
            into = max((b - (1 - bc)) / bc, (bc - b) / bc)  # 0..1 out through either cut
            if into > 0 and x < 0:
                x *= 1 - into * BUCKLE_CUT_X / (BUCKLE_W / 2)
            t = t0 + x / radius(t0)
            r = radius(t) + BELT_THICK + BUCKLE_RAISE
            row.append(at(t, r, (b - 0.5) * BUCKLE_H))
            urow.append(uv_in('buckle', x / BUCKLE_W + 0.5, b))
        pts.append(row); uv.append(urow)
    bm, grid = loft(pts, closed=False)
    outward_normals(bm, lambda p: Vector((c.x, c.y, p.z)))
    uvs = {v: uv[i][j] for i, row in enumerate(grid) for j, v in enumerate(row)}
    mid = at(t0, radius(t0), 0.0)
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
        tc = thetas[jc] + math.radians(FLAP_TURN[s])
        rc = float(np.interp((tc - phase) % (2 * math.pi), [t - phase for t in thetas], rs)) + CUFF_BEAD
        dc = e1 * math.cos(tc) + e2 * math.sin(tc)
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
        ws = UNI_W.at(axis(0.5) + dc * (rc - CUFF_BEAD))
        out.append(new_detail('CuffFlap_' + s, bm, uvs, rigid(ws), 0.003))
        spots = []
        for fa in (0.2, 0.5, 0.8):
            c = axis(0.5) + ax * (fa - 0.5) * FLAP_ALONG * 0.85
            spots.append((c + dc * (rc + FLAP_RAISE), dc, ws))
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
    i_cap = min(n, int(math.ceil(LAST_TOE_PLAN / length * n)))  # the toe's end: the width there, rounded off
    for i in range(n + 1):
        t = i / n
        y = y_toe + length * t
        xc, w = (xcs[i_cap], ws[i_cap]) if i < i_cap else (xcs[i], ws[i])  # (the toes' own taper made it a point)
        # rounded in plan at the toe and the heel's back
        u = min(1.0, (y - y_toe) / LAST_TOE_PLAN)  # a round toe (a circle's arc in plan; as a parabola it came to a point)
        w *= math.sqrt(max(0.02, 1 - (1 - u) ** 2)) * math.sqrt(max(0.02, min(1.0, (y_heel - y) / 0.03)))
        w *= 0.82 + 0.18 * smoothstep(t, 0.0, 0.35)  # a slimmer toe (the portrait's is narrow, a little pointed)
        top = SOLE_H + float(np.interp(t, [a for a, _ in LAST_TOP], [b for _, b in LAST_TOP]))
        bot = SOLE_H + (HEEL_H - SOLE_H) * smoothstep(t, *LAST_ARCH)
        # the toe's end rounded over in side view too (a dome, not a wedge: thin at the tip it came out a beak)
        top = bot + (top - bot) * max(0.3, math.sqrt(max(0.0, min(1.0, (y - y_toe) / LAST_TOE_ROUND))))
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
        # sole with a welt, and the heel block, from the outline of the boot's bottom: its farthest point per direction
        # round the middle (the convex hull ran straight across the arch and out to a point at the toe - a plate
        # sticking out round the foot)
        hull = [low[i] for i in mg.convex_hull_2d(low)]
        cxy = sum(hull, Vector((0.0, 0.0))) / len(hull)
        nb = 72
        rad = [0.0] * nb
        for p in low:
            d = p - cxy
            k = int((math.atan2(d.x, d.y) % (2 * math.pi)) / (2 * math.pi) * nb) % nb
            rad[k] = max(rad[k], d.length)
        for _ in range(nb):
            if not all(rad):
                rad = [r or max(rad[k - 1], rad[(k + 1) % nb]) for k, r in enumerate(rad)]
        rad = [max(rad[k], (rad[k - 1] + rad[(k + 1) % nb]) / 2) for k in range(nb)]
        outline = [cxy + Vector((math.sin(a), math.cos(a))) * r
                   for a, r in ((2 * math.pi * (k + 0.5) / nb, rad[k]) for k in range(nb))]
        welt = [p + (p - cxy).normalized() * WELT for p in outline]
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




def buckle_in_place():
    """-- buckle: the new plate's vertices and UVs into the rest file's Buckle and the leader's (the same grid: the
    vertex count must not change), the leader's carried by the old plate's rigid move from rest to stance."""
    def grab(ob):
        me = ob.data
        co = np.zeros(len(me.vertices) * 3, np.float32); me.vertices.foreach_get('co', co)
        uv = np.zeros(len(me.loops) * 2, np.float32); me.uv_layers.active.data.foreach_get('uv', uv)
        return co.reshape(-1, 3), uv

    def put(ob, co, uv):
        ob.data.vertices.foreach_set('co', co.ravel()); ob.data.uv_layers.active.data.foreach_set('uv', uv)
        ob.data.update()
    old = bpy.data.objects['Buckle']
    new_belt, new = build_belt()
    was, _ = grab(old)
    co, uv = grab(new)
    if co.shape != was.shape or len(uv) != len(old.data.loops) * 2:
        sys.exit('build_details.py -- buckle: the new plate has %d vertices, the old %d - rebuild the details'
                 % (len(co), len(was)))
    for o in (new_belt, new):
        bpy.data.objects.remove(o)
    put(old, co, uv)
    rig.data.pose_position = POSE_POSITION
    bpy.ops.outliner.orphans_purge(do_recursive=True)
    bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
    print('buckle in place: %s (%d vertices moved up to %.1f mm)' % (
        OUT, (np.abs(co - was).max(1) > 1e-6).sum(), np.abs(co - was).max() * 1000))
    leader = os.path.join(HERE, 'alexander_leader.blend')
    bpy.ops.wm.open_mainfile(filepath=leader)
    ob = bpy.data.objects['Buckle']
    posed, _ = grab(ob)
    ca, cb = was.mean(0), posed.mean(0)
    U_, _, Vt = np.linalg.svd((was - ca).T @ (posed - cb))
    R = (U_ @ np.diag([1, 1, np.sign(np.linalg.det(U_ @ Vt))]) @ Vt).T
    res = np.abs((was - ca) @ R.T + cb - posed).max()
    put(ob, (co - ca) @ R.T + cb, uv)
    for img in bpy.data.images:
        if img.name.startswith('Details_'):
            img.reload()
    bpy.ops.wm.save_as_mainfile(filepath=leader, compress=True)
    print('buckle in place: %s (the old plate rest -> stance rigid within %.2f mm)' % (leader, res * 1000))


if BUCKLE_ONLY:
    buckle_in_place()
    sys.exit(0)
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

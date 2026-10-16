# Regalia over the posed uniform of alexander_leader.blend (after build_pose.py), as in art/source/alexander_ii_short.png: general's epaulettes
# with bullion fringe, the light-blue sash of St Andrew over the right shoulder to the left hip, gold aiguillettes on
# the right breast. blender -b art/3d/alexander_leader.blend --python art/3d/build_regalia.py   (after build_pose.py)
# Rewrites the file in place; safe to re-run (removes what it made before).
# One material 'Regalia' with its own atlas (albedo + metal/roughness, textures/regalia_*.png), every part skinned to
# the skeleton: rigid parts take the cloth's weights at one point, the sash and cords the cloth's under each vertex.
# MPFB space: metres, Z up, faces -Y; his right = -X.
import bpy, bmesh, math, os, sys
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mat_util  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'alexander_leader.blend')  # on the posed uniform (build_pose.py), in place
TEXDIR = os.path.join(HERE, 'textures')
TEX = 2048
ALBEDO_OUT = os.path.join(TEXDIR, 'regalia_albedo.png')
MR_OUT = os.path.join(TEXDIR, 'regalia_mr.png')  # R metal, G roughness
NORMAL_OUT = os.path.join(TEXDIR, 'regalia_normal.png')  # tangent space, OpenGL (Y up)

GOLD_SRGB = mat_util.GOLD_SRGB
SASH_SRGB = (46, 96, 196)        # the St Andrew blue moire of the portrait (between its lit and shaded side)
# Epaulettes: an oval field on the shoulder top reaching past the shoulder's end (in the portrait they stand out
# beyond the shoulders by about a quarter of a head), a twisted rim, a strap to the collar with a button, and heavy
# bullion fringe hanging from the outer part of the rim.
EP_OUT, EP_A, EP_B = 0.008, 0.078, 0.062  # centre this far out past the shoulder joint; semi-axes along and across
EP_LIFT, EP_DOME, EP_THICK = 0.006, 0.018, 0.007
EP_TILT = 26.0                   # degrees from level: the field's outer end lower (it follows the shoulder's slope)
EP_FORWARD = 18.0                # ... and its front edge lower (in the portrait the fields face the viewer a little)
STRAP_X, STRAP_W = 0.085, 0.05   # strap from the field to this |x|, by the collar: the epaulette's own broad shoulder
                                 # strap, gold galloon edged in red, as in the portrait
STRAP_T, STRAP_GAP = 0.003, 0.004  # its thickness; off the cloth
STRAP_REPEATS = 3                # the galloon picture along the strap
FRINGE_N, FRINGE_ARC = 30, 240.0  # strands per row over this arc of the rim, centred on the outer end
FRINGE_LEN, FRINGE_R, FRINGE_OUT = 0.095, 0.0105, 0.024
FRINGE_FLARE = 0.03               # a strand stands at most this much further out than its rest to clear the sleeve
FRINGE_JITTER = 0.0015           # strand to strand: length and reach (a neat even fringe, as in the portrait)
FRINGE_TOP = (0.68, 0.0115, 0.6, 0.007)  # the upper row over it: length, radius, outward reach (x FRINGE_*), lift
# Bullion (canitel): coiled gold wire twisted into a rope - each strand a helix of BULLION_STARTS plies, BULLION_PITCH
# apart along it (the portrait's fringe shows slanted twists, not rings: one start made a stack of coins)
BULLION_PITCH, BULLION_STARTS, BULLION_UV_LEN = 0.0065, 4, 0.147
BULLION_RELIEF = 0.14             # the coils' height (x pitch): low - deeper, the fringe read as wickerwork
# Sash: a band 'SASH_W' wide round the torso in the plane through the top of the right shoulder and the left hip.
SASH_SHOULDER = Vector((-0.14, 0.0, 1.76))   # in the portrait it runs up close by the collar
SASH_HIP = Vector((0.17, 0.0, 1.31))   # the lower edge on the belt's top at the side
SASH_W, SASH_GAP, SASH_THICK, SASH_N = 0.095, 0.005, 0.002, 240
SASH_RELAX = 40                  # rounds of smoothing the band and pushing it out of the cloth
SASH_TIGHTEN = 25                # rounds of envelope() of the cloth the sash lies on
SASH_SETTLE = 8                  # rounds of relax() after the lift over the belt
SASH_EVEN = 30                   # rounds of evening out the width along the band
BRIDGE_DZ, BRIDGE_SLOPE, BRIDGE_SPREAD, BRIDGE_SMOOTH = 0.07, 0.001, 10, 12  # over the belt: zone round its centre; lift lost per step to a neighbour; steps
TORSO_ARM_Z = 1.5                # below this the upper arms' sleeves are not part of the torso surface
GOLD_FLOOR = 0.55                # gold albedo: the pictures' shading only darkens it down to this (the relief does the rest)
NORMAL_STRENGTH = {'cord': 3.0, 'pole': 2.0, 'sash': 0.05}  # the pictures' light and dark as relief (the fringe's own)
# Aiguillettes: cords from under the right epaulette's front to the closure, hanging in loops; two loose cords with
# gold tips ('pencils') hang from the closure end over the sash.
AIG_FROM = (-0.215, 1.67)          # (x, z) on the front of the chest
AIG_TO = (-0.03, 1.60)     # under the middle of the sash (the loose cord starts here)
AIG_LOOPS = [(-0.175, 1.55), (-0.165, 1.49), (-0.155, 1.43)]  # lowest point of each loop
AIG_END_ZS, AIG_UNDER = (1.622, 1.602, 1.582), 0.014  # ... and where it ends: at these heights, this far in under
# the sash's edge (sash_edge_x), thinning out there - the three go in under it one below the other, as in the portrait
# (carried on under the band, a cord showed through it as a ridge and a pinch; its thin end poked out through it)
# the loose cord comes out from under the sash's lower edge (emerge), a short way over the cloth to the knot the pencil
# hangs from (end): in the portrait one pencil shows, hanging by the sash's lower edge
AIG_TAILS = [((0.068, 1.588), (0.078, 1.565))]  # (emerge, end), x z
AIG_R, AIG_GAP = 0.0095, 0.002  # the portrait's cords are thick twisted rope (~2 cm)
AIG_STIFF = 12                   # rounds of straightening the cords over the cloth's folds
PENCIL_L = 0.15
# The pencil (the aiguillette's cast tip), top to point: (t along it, radius m, fluted) - a cup the cord goes into, a
# knob, a fluted shaft between ring mouldings, a vase-shaped boss, a second fluted shaft tapering to a pointed finial
PENCIL_PROFILE = [(0.0, 0.0), (0.004, 0.0062), (0.012, 0.0082), (0.045, 0.0088), (0.055, 0.0058), (0.075, 0.0058),
                  (0.095, 0.0092), (0.115, 0.0092), (0.135, 0.0056), (0.15, 0.0056), (0.16, 0.0079), (0.18, 0.0079),
                  (0.19, 0.0062, True), (0.43, 0.0062, True), (0.44, 0.0079), (0.46, 0.0079), (0.47, 0.0060),
                  (0.53, 0.0088), (0.57, 0.0088), (0.62, 0.0060), (0.63, 0.0077), (0.65, 0.0077),
                  (0.66, 0.0058, True), (0.86, 0.0046, True), (0.87, 0.0064), (0.89, 0.0064), (0.90, 0.0045),
                  (0.97, 0.0016), (0.985, 0.0024), (1.0, 0.0)]
PENCIL_FLUTES, PENCIL_FLUTE_D = 10, 0.0009  # flutes round the shafts and their depth
CORD_UV_LEN = 0.6                # metres of cord over the width of its atlas region (the twist repeats along it)

ATLAS = {
    'sash': (0.0, 0.0, 1.0, 0.125),
    'cord': (0.0, 0.125, 1.0, 0.1875),
    'bullion': (0.0, 0.1875, 1.0, 0.25),
    'pole': (0.0, 0.25, 0.5, 0.75),
    'gold': (0.5, 0.25, 0.5625, 0.3125),
    'strap': (0.5, 0.375, 1.0, 0.5),
    'chased': (0.5, 0.5, 1.0, 0.75),
}
# Gold thread (cords, fringe, galloon, the field's embroidery, the tassels) is yellow fibre, not metal: a faint sheen
# on the crests, matt between them (even at 0.25..0.6 metallic it read as polished cast gold in a lit viewport); the cast
# pieces (buttons, pencils) are gilt metal, chased all over (the 'chased' region).
THREAD_METAL, THREAD_ROUGH = (0.0, 0.12), (0.85, 0.6)  # in the gaps, on the crests
CAST_METAL, CAST_ROUGH = 0.9, 0.36
CORD_REPEATS = 8                 # the generated twisted cord picture along its region (seamless: 8 plies)
CHASED_TILES = (6, 14)           # the pencil's chased ornament: tiles round it, along it
# The generated material pictures (textures/gen, see art/prompts.md) and how often they repeat in their regions.
SASH_CONTRAST = 2.5               # the damask's light and dark, stronger than generated (it is faint on the model)
SASH_REPEATS = 12                # mirrored, even: the band's ends meet on the same column

sc = bpy.context.scene
P = sc['uniform'].to_dict()
rig = bpy.data.objects['HumanRig']
rig.data.pose_position = 'REST'
uni = bpy.data.objects['Uniform']
for o in list(bpy.data.objects):  # previous run
    if o.get('regalia'):
        bpy.data.objects.remove(o)
bones = {b.name for b in rig.data.bones}


def smoothstep(x, a, b):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- surfaces and weights
def envelope(bm, rounds):
    """bm smoothed from the outside: each round every vertex moves to its neighbours' mean, but never inside where it
    was (along its normal) - the surface tightens over the folds like a band laid across them, the crests kept."""
    bm.normal_update()
    vs = list(bm.verts)
    orig = [v.co.copy() for v in vs]
    nrm = [v.normal.copy() for v in vs]
    nbs = [[e.other_vert(v) for e in v.link_edges] for v in vs]
    for _ in range(rounds):
        new = []
        for v, o, n, nb in zip(vs, orig, nrm, nbs):
            if v.is_boundary or not nb:
                new.append(v.co.copy()); continue
            q = sum((x.co for x in nb), Vector()) / len(nb)
            h = (q - o).dot(n)
            new.append(q + n * -h if h < 0 else q)
        for v, q in zip(vs, new):
            v.co = q


def bvh_of(obs, torso=False, tighten=0):
    """BVH of the objects; torso: the uniform without its sleeves (the sash and the cords lie on the torso - the hanging
    left arm is right by the sash's end at the hip, which would wrap onto it); tighten: rounds of envelope() on the
    uniform (a band lies across its folds, not into them)."""
    bm = bmesh.new()
    for o in obs:
        me = o.data.copy(); me.transform(o.matrix_world)
        if o == uni:  # the outside only: the lining (material slot 1, build_pose.py) faces inwards
            b2 = bmesh.new(); b2.from_mesh(me)
            bmesh.ops.delete(b2, geom=[f for f in b2.faces if f.material_index == 1], context='FACES')
            b2.to_mesh(me); b2.free()
        if o == uni and torso:
            b2 = bmesh.new(); b2.from_mesh(me)
            dl = b2.verts.layers.deform.active
            names = [g.name for g in uni.vertex_groups]
            fore = {i for i, n in enumerate(names) if n.startswith(('lowerarm', 'hand'))}
            upper = {i for i, n in enumerate(names) if n.startswith('upperarm')}
            # the sleeves by the hips go; not the cloth behind the shoulders (the arms taken back pull it onto the back)
            bmesh.ops.delete(b2, geom=[v for v in b2.verts
                                       if sum(w for g, w in v[dl].items() if g in fore) > 0.3
                                       or (v.co.z < TORSO_ARM_Z and sum(w for g, w in v[dl].items() if g in upper) > 0.5)],
                             context='VERTS')
            b2.to_mesh(me); b2.free()
        if o == uni and tighten:
            b2 = bmesh.new(); b2.from_mesh(me)
            envelope(b2, tighten)
            b2.to_mesh(me); b2.free()
        bm.from_mesh(me); bpy.data.meshes.remove(me)
    t = BVHTree.FromBMesh(bm); bm.free()
    return t


CLOTH = bvh_of([uni] + [bpy.data.objects[n] for n in ('Belt', 'Buckle', 'Buttons')], torso=True)  # the sash lies on these


class Weights:
    """Bone weights of a skinned mesh, looked up at any point (inverse-distance blend of the nearest vertices)."""

    def __init__(self, ob, torso=False):
        """torso: only the vertices the arms do not move (things on the chest and hips lie by the sleeves - the sash's
        end by the left cuff - and must not follow them)."""
        names = [g.name for g in ob.vertex_groups]
        me = ob.data
        arm = lambda n: n.startswith(('upperarm', 'lowerarm', 'hand', 'index', 'middle', 'ring', 'pinky', 'thumb'))  # noqa
        keep = [v for v in me.vertices
                if not torso or sum(g.weight for g in v.groups if arm(names[g.group])) < 0.05]
        self.kd = KDTree(len(keep))
        self.w = []
        for i, v in enumerate(keep):
            self.kd.insert(v.co, i)
            self.w.append({names[g.group]: g.weight for g in v.groups if names[g.group] in bones and g.weight > 0})
        self.kd.balance()

    def at(self, co, k=4):
        acc = {}
        for _, i, d in self.kd.find_n(co, k):
            for n, w in self.w[i].items():
                acc[n] = acc.get(n, 0.0) + w / (d + 1e-4)
        top = sorted(acc.items(), key=lambda x: -x[1])[:4]
        s = sum(w for _, w in top)
        return {n: w / s for n, w in top}


UNI_W = Weights(uni)
TORSO_W = Weights(uni, torso=True)


def outer(bvh, o, d, maxd=0.5):
    """The outermost surface point from o along d (cast back from maxd), its normal; (None, None) if none."""
    loc, nrm, _, _ = bvh.ray_cast(o + d * maxd, -d, maxd)
    return loc, nrm


def front_at(bvh, x, z):
    """Front surface (seen from -Y) at (x, z): point, normal."""
    return bvh.ray_cast(Vector((x, -1.0, z)), Vector((0, 1, 0)), 2.0)[:2]


# ---------------------------------------------------------------- texture atlas (sRGB)
def srgb(c):
    return np.array(c, np.float32) / 255


def gen_picture(name):
    """textures/gen/<name>.png as an sRGB float array, row 0 = bottom (Blender's order)."""
    img = bpy.data.images.load(os.path.join(TEXDIR, 'gen', name + '.png'), check_existing=False)
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


def grid(w, hh):
    return np.meshgrid(np.linspace(0, 1, w), np.linspace(0, 1, hh))


def sash_tex(w, hh):
    """The generated damask moire, its height across the band, mirrored repeats along it; toned to the portrait's
    blue."""
    pic = gen_picture('sash_damask')
    u, v = grid(w, hh)
    t = (u * SASH_REPEATS) % 2.0
    rgb = sample(pic, np.where(t > 1, 2 - t, t), v)
    med = np.median(pic.reshape(-1, 3), 0)
    return np.clip(srgb(SASH_SRGB) * (1 + (rgb / med - 1) * SASH_CONTRAST), 0, 1)  # the damask shows a little more


def cord_tex(w, hh, repeats):
    """The generated twisted cord, its length along u (seamless repeats), its width round the tube."""
    u, v = grid(w, hh)
    return sample(gen_picture('gold_cord'), (u * repeats) % 1.0, v)


def chased_tex(w, hh):
    """Chased gilt ornament for the cast pieces (the pencils), round them along u, along them along v: tiles of
    scrolls (a spiral leaf, turning the other way in the next tile) between bead rows. Returns the height 0..1."""
    u, v = grid(w, hh)
    tu, tv = u * CHASED_TILES[0], v * CHASED_TILES[1]
    lx, ly = (tu % 1.0) * 2 - 1, (tv % 1.0) * 2 - 1
    flip = np.where((np.floor(tu) + np.floor(tv)) % 2 == 0, 1.0, -1.0)
    r, th = np.hypot(lx, ly), np.arctan2(ly, lx) * flip
    leaf = 0.5 + 0.5 * np.sin(2 * th + 8 * r)
    leaf = np.clip(leaf * 1.4 - 0.2, 0, 1) * (1 - np.clip((r - 0.9) * 6, 0, 1))
    bead = (np.abs(ly) > 0.86) * (0.5 + 0.5 * np.cos(u * 2 * np.pi * CHASED_TILES[0] * 6))
    return blur1(np.maximum(leaf * 0.85, bead))


def strap_tex(w, hh):
    """The epaulette's strap: the generated galloon (gold stripes between red borders) along it, its gold graded to
    the portrait's; returns the colour and a gold mask."""
    u, v = grid(w, hh)
    pic = sample(gen_picture('belt_galloon'), (u * STRAP_REPEATS) % 1.0, v)
    gold = np.clip(((pic[..., 1] > 0.45 * pic[..., 0]) & (pic[..., 0] > 0.25)).astype(np.float32), 0, 1)
    gold = blur1(gold)
    return mat_util.gold_grade(np.clip(pic * 1.15, 0, 1), gold), gold


def pole_tex(w, hh):
    """The epaulette's field from above: the generated round plate (rope rim, beads, eagle)."""
    return sample(gen_picture('epaulette_field'), *grid(w, hh))


def bullion_tex(w, hh):
    """A bullion strand, its length along u (BULLION_UV_LEN metres), round it along v: a helix of coiled wire. Returns
    albedo, roughness and the height in metres per pixel (for the normal map)."""
    u, v = grid(w, hh)
    phase = u * BULLION_UV_LEN / BULLION_PITCH + v * BULLION_STARTS
    c = 0.5 + 0.5 * np.cos(2 * np.pi * phase)
    h = c ** 0.6  # round coil tops, narrow dark gaps between the turns
    rgb = srgb(GOLD_SRGB) * (0.68 + 0.32 * h)[..., None]
    return rgb, None, h * BULLION_PITCH * BULLION_RELIEF


def normals(height, mx, my):
    """Tangent-space normals (OpenGL) of a height field in metres, mx / my metres per pixel along u / v."""
    gy, gx = np.gradient(height)
    n = np.stack([-gx / mx, -gy / my, np.ones_like(height)], -1)
    return n / np.linalg.norm(n, axis=-1, keepdims=True)


def blur1(a):
    return (a + np.roll(a, 1, 0) + np.roll(a, -1, 0) + np.roll(a, 1, 1) + np.roll(a, -1, 1)) / 5


def build_atlas():
    rgb = np.zeros((TEX, TEX, 3), np.float32)
    metal = np.zeros((TEX, TEX), np.float32); rough = np.full((TEX, TEX), 0.8, np.float32)
    nrm = np.zeros((TEX, TEX, 3), np.float32); nrm[..., 2] = 1.0

    def px(region):
        u0, v0, u1, v1 = ATLAS[region]
        return int(u0 * TEX), int(v0 * TEX), int(u1 * TEX), int(v1 * TEX)

    def relief(region, c, strength):  # the picture's own light and dark as its relief (raised where bright)
        x0, y0, x1, y1 = px(region)
        lum = blur1(c @ np.array([0.2126, 0.7152, 0.0722], np.float32))
        nrm[y0:y1, x0:x1] = normals(lum * strength, 0.1, 0.1)  # strength x 10: slope per unit of brightness a pixel

    x0, y0, x1, y1 = px('sash')
    pic = sash_tex(x1 - x0, y1 - y0)
    rgb[y0:y1, x0:x1] = pic; rough[y0:y1, x0:x1] = 0.6  # silk moire: a soft sheen, no gloss
    relief('sash', pic, NORMAL_STRENGTH['sash'])

    def thread(region, crest):
        """Metal and roughness of gold thread by how high each texel is (crest 0..1)."""
        x0, y0, x1, y1 = px(region)
        metal[y0:y1, x0:x1] = THREAD_METAL[0] + (THREAD_METAL[1] - THREAD_METAL[0]) * crest
        rough[y0:y1, x0:x1] = THREAD_ROUGH[0] + (THREAD_ROUGH[1] - THREAD_ROUGH[0]) * crest

    def gold(region, c, recolour=True):
        """Gold from a generated picture: its shading only darkens bright gold down to GOLD_FLOOR (dark pictures made
        dull brown metal); bright thread shines a little, the gaps between are rough."""
        x0, y0, x1, y1 = px(region)
        lum = c @ np.array([0.2126, 0.7152, 0.0722], np.float32)
        shade = np.clip(lum / max(float(np.percentile(lum, 95)), 1e-3), 0, 1)
        rgb[y0:y1, x0:x1] = (srgb(GOLD_SRGB) * (GOLD_FLOOR + (1 - GOLD_FLOOR) * shade)[..., None] if recolour
                             else mat_util.gold_grade(np.clip(c * 1.25, 0, 1), np.clip(shade * 3, 0, 1)))
        thread(region, shade)
        relief(region, c, NORMAL_STRENGTH[region])

    x0, y0, x1, y1 = px('cord')
    gold('cord', cord_tex(x1 - x0, y1 - y0, CORD_REPEATS))
    x0, y0, x1, y1 = px('bullion')
    c, r, hgt = bullion_tex(x1 - x0, y1 - y0)
    rgb[y0:y1, x0:x1] = c
    thread('bullion', np.clip((hgt / hgt.max()), 0, 1))
    nrm[y0:y1, x0:x1] = normals(hgt, BULLION_UV_LEN / (x1 - x0), 2 * math.pi * FRINGE_R / (y1 - y0))
    x0, y0, x1, y1 = px('pole')
    gold('pole', pole_tex(x1 - x0, y1 - y0), recolour=False)
    x0, y0, x1, y1 = px('strap')
    c, gm = strap_tex(x1 - x0, y1 - y0)
    rgb[y0:y1, x0:x1] = c
    lum = c @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    shade = np.clip(lum / max(float(np.percentile(lum, 95)), 1e-3), 0, 1)
    thread('strap', shade * gm)
    rough[y0:y1, x0:x1] = np.where(gm > 0.5, rough[y0:y1, x0:x1], 0.75)  # the red borders: silk
    relief('strap', c, 1.0)
    x0, y0, x1, y1 = px('gold')
    rgb[y0:y1, x0:x1] = srgb(GOLD_SRGB); metal[y0:y1, x0:x1] = CAST_METAL; rough[y0:y1, x0:x1] = CAST_ROUGH
    x0, y0, x1, y1 = px('chased')
    h = chased_tex(x1 - x0, y1 - y0)
    rgb[y0:y1, x0:x1] = srgb(GOLD_SRGB) * (0.5 + 0.5 * h)[..., None]  # dark in the recesses (worn bright on top)
    metal[y0:y1, x0:x1] = CAST_METAL; rough[y0:y1, x0:x1] = CAST_ROUGH + 0.2 * (1 - h)
    nrm[y0:y1, x0:x1] = normals(h * 0.00035, PENCIL_L / (y1 - y0), 2 * math.pi * 0.007 / (x1 - x0))
    imgs = []
    for name, data, path, cs in (('Regalia_Albedo', rgb, ALBEDO_OUT, 'sRGB'),
                                 ('Regalia_MR', np.stack([metal, rough, np.zeros_like(metal)], 2), MR_OUT, 'Non-Color'),
                                 ('Regalia_Normal', nrm * 0.5 + 0.5, NORMAL_OUT, 'Non-Color')):
        img = bpy.data.images.get(name) or bpy.data.images.new(name, TEX, TEX)
        img.scale(TEX, TEX)
        img.pixels.foreach_set(np.concatenate([data, np.ones((TEX, TEX, 1), np.float32)], 2).astype(np.float32).ravel())
        img.filepath_raw = path; img.file_format = 'PNG'; mat_util.write(img)
        img.filepath = path; img.source = 'FILE'
        img.colorspace_settings.name = cs
        imgs.append(img)
    mat = bpy.data.materials.get('Regalia') or bpy.data.materials.new('Regalia')
    mat.use_nodes = True
    nt = mat.node_tree
    for nd in [nd for nd in nt.nodes if nd.type in ('TEX_IMAGE', 'SEPARATE_COLOR', 'NORMAL_MAP')]:
        nt.nodes.remove(nd)
    bsdf = next(nd for nd in nt.nodes if nd.type == 'BSDF_PRINCIPLED')
    ta, tm, tn = (nt.nodes.new('ShaderNodeTexImage') for _ in range(3))
    ta.image, tm.image, tn.image = imgs
    sep = nt.nodes.new('ShaderNodeSeparateColor')
    nmap = nt.nodes.new('ShaderNodeNormalMap')
    nt.links.new(ta.outputs['Color'], bsdf.inputs['Base Color'])
    nt.links.new(tm.outputs['Color'], sep.inputs['Color'])
    nt.links.new(sep.outputs[0], bsdf.inputs['Metallic'])
    nt.links.new(sep.outputs[1], bsdf.inputs['Roughness'])
    nt.links.new(tn.outputs['Color'], nmap.inputs['Color'])
    nt.links.new(nmap.outputs['Normal'], bsdf.inputs['Normal'])
    print('atlas', ALBEDO_OUT)
    return mat


MAT = build_atlas()


def uv_in(region, u, v):
    u0, v0, u1, v1 = ATLAS[region]
    pad = 2 / TEX
    return (u0 + pad + (u1 - u0 - 2 * pad) * u, v0 + pad + (v1 - v0 - 2 * pad) * v)


# ---------------------------------------------------------------- mesh helpers
def new_part(name, bm, uvs, weights, solidify=0.0):
    """bm with per-vertex UVs and weights (functions of the vertex) -> skinned object 'name'."""
    if uvs is not None:  # None: bm brings its own 'UVMap'
        for lay in list(bm.loops.layers.uv.values()):
            bm.loops.layers.uv.remove(lay)
        lay = bm.loops.layers.uv.new('UVMap')
        for f in bm.faces:
            for l in f.loops:
                l[lay].uv = uvs(l.vert)
    vw = [weights(v) for v in bm.verts]
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob)
    ob['regalia'] = True
    me.materials.append(MAT)
    for p in me.polygons:
        p.use_smooth = True
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
    print('part %s: %d tris' % (name, sum(len(p.vertices) - 2 for p in me.polygons)))
    return ob


def catmull(pts, step):
    """Catmull-Rom through pts, sampled every ~step."""
    P_ = [pts[0]] + list(pts) + [pts[-1]]
    out = []
    for i in range(1, len(P_) - 2):
        p0, p1, p2, p3 = P_[i - 1], P_[i], P_[i + 1], P_[i + 2]
        n = max(2, int((p2 - p1).length / step))
        for k in range(n):
            s = k / n
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * s + (2 * p0 - 5 * p1 + 4 * p2 - p3) * s * s
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * s ** 3))
    out.append(pts[-1])
    return out


def tube(bm, path, r, sides, region, uv_len=CORD_UV_LEN, cap=True, taper=None):
    """A tube along path into bm (the seam column doubled for the UVs); returns its verts and their UVs."""
    uvs = {}
    prev_u = None
    rings, s = [], 0.0
    for i, p in enumerate(path):
        t = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized()
        if prev_u is None:
            ref = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
            prev_u = t.cross(ref).normalized()
        u = (prev_u - t * prev_u.dot(t)).normalized(); prev_u = u  # parallel transport: no twist
        w = t.cross(u)
        if i:
            s += (p - path[i - 1]).length
        rr = r * (taper(i / (len(path) - 1)) if taper else 1.0)
        ring = []
        for k in range(sides + 1):
            a = 2 * math.pi * k / sides
            v = bm.verts.new(p + rr * (math.cos(a) * u + math.sin(a) * w))
            uvs[v] = uv_in(region, min(s / uv_len, 1.0), k / sides)
            ring.append(v)
        rings.append(ring)
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(sides):
            bm.faces.new((r0[k], r0[k + 1], r1[k + 1], r1[k]))
    if cap:  # rounded end: a dome on the last ring (a cone to a point showed as dark teeth)
        t = (path[-1] - path[-2]).normalized()
        rr = r * (taper(1.0) if taper else 1.0)
        u, w = (rings[-1][0].co - path[-1]).normalized(), None
        w = t.cross(u)
        u_end = min(s / uv_len, 1.0)  # the strand's own texture runs on over the dome (another region's UVs there
        for a in (30, 60):            # made a dark ring: the faces between ran across the atlas)
            ring = []
            for k in range(sides + 1):
                b = 2 * math.pi * k / sides
                v = bm.verts.new(path[-1] + t * rr * 0.8 * math.sin(math.radians(a))
                                 + rr * math.cos(math.radians(a)) * (math.cos(b) * u + math.sin(b) * w))
                uvs[v] = uv_in(region, max(u_end - 0.004 * a / 30, 0.0), k / sides)
                ring.append(v)
            for k in range(sides):
                bm.faces.new((rings[-1][k], rings[-1][k + 1], ring[k + 1], ring[k]))
            rings.append(ring)
        tip = bm.verts.new(path[-1] + t * rr * 0.8)
        uvs[tip] = uv_in(region, max(u_end - 0.012, 0.0), 0.5)
        for k in range(sides):
            bm.faces.new((rings[-1][k], rings[-1][k + 1], tip))
    return [v for ring in rings for v in ring], uvs


# ---------------------------------------------------------------- sash
def build_sash():
    """A band SASH_W wide round the torso. Its middle line: the outermost cloth (tunic, belt, collar) round the plane
    through SASH_SHOULDER and SASH_HIP that holds the front-back axis, smoothed. Across it, at every point, the band
    runs along the cloth square to the line (the cloth's normal x the line's direction), so it keeps its width where
    the torso turns away from that plane; SASH_GAP off the cloth."""
    U = (SASH_SHOULDER - SASH_HIP).normalized()
    Y = Vector((0, 1, 0))
    N = U.cross(Y).normalized()
    c = (SASH_SHOULDER + SASH_HIP) / 2
    rows = 13  # rows across: fine enough to lie over the cords under it (1.4 cm thick)

    def on_cloth(p):
        loc, nrm, _, _ = CLOTH.find_nearest(p, 0.1)
        return (loc + nrm * SASH_GAP, nrm) if loc is not None else (p, N)

    mid = []
    for j in range(SASH_N):
        th = 2 * math.pi * j / SASH_N  # 0: front, pi/2: up the shoulder
        d = -Y * math.cos(th) + U * math.sin(th)
        loc, nrm = outer(CLOTH, c, d)
        mid.append((loc + nrm * SASH_GAP) if loc is not None else c + d * 0.2)
    for _ in range(12):  # the cloth's buttons and seams would show through
        mid = [mid[j] * 0.5 + (mid[j - 1] + mid[(j + 1) % SASH_N]) * 0.25 for j in range(SASH_N)]
        mid = [on_cloth(p)[0] for p in mid]
    sides = []
    for j in range(SASH_N):
        t = (mid[(j + 1) % SASH_N] - mid[j - 1]).normalized()
        side = on_cloth(mid[j])[1].cross(t).normalized()
        sides.append(side if side.dot(N) > 0 else -side)
    for _ in range(4):  # no twisting where the cloth's normal turns quickly (the shoulder)
        sides = [(sides[j] * 2 + sides[j - 1] + sides[(j + 1) % SASH_N]).normalized() for j in range(SASH_N)]
    bm = bmesh.new()
    grid, uvs = [], {}
    for i in range(rows):
        s_ = (i / (rows - 1) - 0.5) * SASH_W
        row = []
        for j in range(SASH_N):
            # the band's width is laid out along the cloth in two steps (it bends round the torso)
            p = on_cloth(mid[j] + sides[j] * s_ * 0.5)[0]
            p = on_cloth(p + sides[j] * s_ * 0.5)[0]
            v = bm.verts.new(p)
            row.append(v)
        row.append(row[0])
        grid.append(row)
    def relax(rounds):
        for _ in range(rounds):  # a smooth band (the projection snaps to the belt's and buttons' edges), and nothing
            # of the cloth through it: every vertex at least SASH_GAP outside the surface nearest to it
            new = {}
            for i, row in enumerate(grid):
                for j in range(SASH_N):
                    ns = [row[j - 1].co, row[(j + 1) % SASH_N].co]
                    if 0 < i < rows - 1:
                        ns += [grid[i - 1][j].co, grid[i + 1][j].co]
                    new[row[j]] = row[j].co * 0.5 + sum(ns, Vector()) / len(ns) * 0.5
            for v, co in new.items():
                v.co = co
            for row in grid:
                for v in row[:-1]:
                    loc, nrm, _, _ = CLOTH.find_nearest(v.co, 0.05)
                    if loc is not None and (v.co - loc).dot(nrm) < SASH_GAP:
                        v.co = loc + nrm * SASH_GAP

    relax(SASH_RELAX)
    # an even width: each row's offset from the middle row smoothed along the band (an edge laid onto a fold of the
    # cloth jumps in or out in a notch), then off the cloth again
    midr = rows // 2
    for _ in range(SASH_EVEN):
        offs = [[grid[i][j].co - grid[midr][j].co for j in range(SASH_N)] for i in range(rows)]
        for i in range(rows):
            if i == midr:
                continue
            for j in range(SASH_N):
                o = (offs[i][j - 1] + offs[i][j] * 2 + offs[i][(j + 1) % SASH_N]) / 4
                v = grid[i][j]
                v.co = grid[midr][j].co + o
                loc, nrm, _, _ = CLOTH.find_nearest(v.co, 0.05)
                if loc is not None and (v.co - loc).dot(nrm) < SASH_GAP:
                    v.co = loc + nrm * SASH_GAP
    # over the belt: the band bridges its raised edges (a band laid on each nearest surface dips in behind them and
    # the edge cuts through): how far out each vertex must be (the outermost surface along the ray from the torso's
    # axis), spread to its neighbours with a gentle slope, the band lifted to it
    zc = P['BELT_ZC']
    need = [[0.0] * SASH_N for _ in range(rows)]
    for i, row in enumerate(grid):
        for j in range(SASH_N):
            p = row[j].co
            if abs(p.z - zc) < BRIDGE_DZ:
                ax = Vector((0.0, 0.0, p.z))
                d = Vector((p.x, p.y, 0.0)).normalized()
                loc = outer(CLOTH, ax, d)[0]
                if loc is not None:
                    need[i][j] = (loc - ax).length + SASH_GAP + 0.001
    for _ in range(BRIDGE_SPREAD):
        need = [[max([need[i][j]] + [need[a][b] - BRIDGE_SLOPE for a, b in
                                     ((i - 1, j), (i + 1, j), (i, j - 1), (i, (j + 1) % SASH_N)) if 0 <= a < rows])
                 for j in range(SASH_N)] for i in range(rows)]
    raw = [r[:] for r in need]
    for _ in range(BRIDGE_SMOOTH):  # no steps in the lift: its mean over the neighbours, never below what is needed
        need = [[max(raw[i][j], sum(need[a][b] for a, b in ((i - 1, j), (i + 1, j), (i, j - 1), (i, (j + 1) % SASH_N))
                                    if 0 <= a < rows) / (4 - (i in (0, rows - 1))))
                 for j in range(SASH_N)] for i in range(rows)]
    lifted = 0
    for i, row in enumerate(grid):
        for j in range(SASH_N):
            v = row[j]
            r = Vector((v.co.x, v.co.y, 0.0))
            if need[i][j] > r.length:
                v.co = Vector((0.0, 0.0, v.co.z)) + r.normalized() * need[i][j]
                lifted += 1
    print('sash: %d vertices lifted over the belt' % lifted)
    relax(SASH_SETTLE)  # the lifted part folds nowhere
    seam = {}
    for i, (r0, r1) in enumerate(zip(grid, grid[1:])):
        for j in range(SASH_N):
            f = bm.faces.new((r0[j], r0[j + 1], r1[j + 1], r1[j]))
            seam[f] = (i, j)
    uvl = bm.loops.layers.uv.new('UVMap')
    for f, (i, j) in seam.items():  # the closing column gets u = 1, not 0
        for l, (di, dj) in zip(f.loops, ((0, 0), (0, 1), (1, 1), (1, 0))):
            l[uvl].uv = uv_in('sash', (j + dj) / SASH_N, (i + di) / (rows - 1))
    bm.normal_update()
    bm.faces.ensure_lookup_table()
    f = bm.faces[0]
    if f.normal.dot(f.calc_center_median() - c) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    return new_part('Sash', bm, None, lambda v: TORSO_W.at(v.co), SASH_THICK)


# ---------------------------------------------------------------- aiguillettes
def sash_edge_x(z, inside):
    """x of the point at height z on the front that is 'inside' in from the sash's lower (his right) edge, on the band
    as build_sash() lays it out: the line through SASH_SHOULDER and SASH_HIP, SASH_W wide (seen from the front)."""
    d = Vector((SASH_HIP.x - SASH_SHOULDER.x, SASH_HIP.z - SASH_SHOULDER.z)).normalized()
    n = Vector((d.y, -d.x)) if d.y < 0 else Vector((-d.y, d.x))  # towards his right and down
    if n.x > 0:
        n = -n
    o = Vector((SASH_SHOULDER.x, SASH_SHOULDER.z)) + n * (SASH_W / 2 - inside)
    t = (z - o.y) / d.y
    return o.x + d.x * t


AIG_ENDS = [(sash_edge_x(z, AIG_UNDER), z) for z in AIG_END_ZS]
print('aiguillette loops end at x %s' % ', '.join('%.3f' % x for x, _ in AIG_ENDS))


def build_aiguillettes(under, over, part, cloth=None):
    """Cords lying on the chest (the front of 'surface' under them), loops from AIG_FROM to AIG_ENDS ('loops': built
    before the sash, which lies over them, each thinning out just in under its edge); the loose cord from under the
    sash's lower edge, ending in a pencil ('tails': on the cloth, its start under the sash)."""
    def on_chest(x, z, lift, surface=over):
        loc, nrm = front_at(surface, x, z)
        return loc + nrm * lift if loc is not None else Vector((x, -0.2, z))

    bm = bmesh.new()
    uvs = {}
    paths = []
    if part == 'loops':
        for (lx, lz), to in zip(AIG_LOOPS, AIG_ENDS):
            paths.append([AIG_FROM, ((AIG_FROM[0] + lx) / 2 - 0.01, (AIG_FROM[1] + lz) / 2 - 0.02), (lx, lz),
                          ((lx + to[0]) / 2 + 0.01, (lz + to[1]) / 2 - 0.02), to])
    else:  # each from just in under the sash's lower edge (found on the band at the cord's height) out over the cloth
        sv = [v.co for v in bpy.data.objects['Sash'].data.vertices if v.co.y < -0.05 and v.co.x > 0]
        tails = []
        for emerge, end in AIG_TAILS:
            ex = max(c.x for c in sv if abs(c.z - emerge[1]) < 0.008)
            dx = ex - emerge[0]
            tails.append(((ex, emerge[1]), (end[0] + dx, end[1])))
            paths.append([(ex - 0.008, emerge[1] + 0.004), (ex, emerge[1]), (end[0] + dx, end[1])])
        print('aiguillette tails: out from under the sash at x %s' % ', '.join('%.3f' % t[0][0] for t in tails))
    surf = under if part == 'loops' else cloth
    for k, ctrl in enumerate(paths):
        pts2 = catmull([Vector((x, 0, z)) for x, z in ctrl], 0.008)
        if part == 'loops':  # the end thins out under the sash's edge: the band lies flat over it
            taper = lambda t: 1.0 - 0.65 * smoothstep(t, 0.82, 0.97)  # noqa: E731
        else:  # comes out from under the band
            taper = lambda t: 0.45 + 0.55 * smoothstep(t, 0.0, 0.35)  # noqa: E731
        n = len(pts2)
        lift = [AIG_R * taper(j / (n - 1)) + AIG_GAP + 0.0015 * k for j in range(n)]  # each over the last
        path = [on_chest(p.x, p.z, lift[j], surf) for j, p in enumerate(pts2)]
        # a thick cord is stiff: it bridges the folds of the cloth in smooth arcs instead of following each one
        for _ in range(AIG_STIFF):
            path = [path[0]] + [(path[j - 1] + path[j] * 2 + path[j + 1]) / 4 for j in range(1, len(path) - 1)] + [path[-1]]
            for j in range(1, len(path) - 1):
                loc, nrm, _, _ = surf.find_nearest(path[j], 0.05)
                if loc is not None and (path[j] - loc).dot(nrm) < lift[j]:
                    path[j] = loc + nrm * lift[j]
        _, u = tube(bm, path, AIG_R, 10, 'cord', cap=False, taper=taper)
        uvs.update(u)
    if part == 'loops':
        return new_part('Aiguillettes', bm, lambda v: uvs[v], lambda v: TORSO_W.at(v.co))
    cords = new_part('AiguilletteTails', bm, lambda v: uvs[v], lambda v: TORSO_W.at(v.co))
    # pencils: the cast tip hanging from the end of each loose cord, along the cord's last direction, clear of what
    # is under it
    bm = bmesh.new(); uvs = {}
    for via, end in tails:
        a = on_chest(*end, AIG_R + AIG_GAP)
        b = on_chest(end[0] + (end[0] - via[0]) * 0.5, end[1] - PENCIL_L, AIG_GAP)
        axis = (b - a).normalized()
        # it hangs from its top (a): its point swung out off the sash and cloth until no part of it comes nearer
        # them than its widest radius (lifting only the point by what the worst place needed left the middle in)
        for _ in range(3):
            lift = 0.0
            for t in range(6, 41):
                p = a.lerp(b, t / 40)
                q = on_chest(p.x, p.z, 0.0)
                n_ = (on_chest(p.x, p.z, 0.01) - q).normalized()
                lift = max(lift, (0.0095 + AIG_GAP - (p - q).dot(n_)) / (t / 40))
            n_ = (on_chest(b.x, b.z, 0.01) - on_chest(b.x, b.z, 0.0)).normalized()
            b = b + n_ * lift
        pencil(bm, uvs, a, (b - a).normalized(), PENCIL_L)
    pencils = new_part('AiguilletteTips', bm, None, lambda v: TORSO_W.at(v.co))
    return cords, pencils


def pencil(bm, uvs, top, axis, length, sides=20):
    """The aiguillette's pencil as a turned piece along axis from top: PENCIL_PROFILE's radii, the fluted stretches
    with PENCIL_FLUTES grooves round them; one closed surface, chased all over (loop UVs in bm's 'UVMap': round it
    along u, along it along v of the 'chased' region)."""
    prof = []
    for k in PENCIL_PROFILE:  # resample: the flutes need rings between the knots
        prof.append(k)
    rows = []
    for (t0, r0, *f0), (t1, r1, *f1) in zip(prof, prof[1:]):
        n = max(1, int((t1 - t0) * length / 0.004))
        for j in range(n):
            s_ = j / n
            rows.append((t0 + (t1 - t0) * s_, r0 + (r1 - r0) * s_, bool(f0 and f1)))
    rows.append((prof[-1][0], prof[-1][1], False))
    ref = Vector((0, 0, 1)) if abs(axis.z) < 0.9 else Vector((1, 0, 0))
    u = axis.cross(ref).normalized(); w = axis.cross(u)
    rings = []
    for t, r, fl in rows:
        ring = []
        for k in range(sides):
            ang = 2 * math.pi * k / sides
            rr = r - (PENCIL_FLUTE_D * (0.5 + 0.5 * math.cos(ang * PENCIL_FLUTES)) if fl else 0.0)
            v = bm.verts.new(top + axis * (t * length) + (u * math.cos(ang) + w * math.sin(ang)) * max(rr, 0.0))
            ring.append(v)
        rings.append(ring)
    lay = bm.loops.layers.uv.get('UVMap') or bm.loops.layers.uv.new('UVMap')
    for i, (r0, r1) in enumerate(zip(rings, rings[1:])):
        for k in range(sides):
            f = bm.faces.new((r0[k], r0[(k + 1) % sides], r1[(k + 1) % sides], r1[k]))
            for l, (a, b) in zip(f.loops, ((k, i), (k + 1, i), (k + 1, i + 1), (k, i + 1))):
                l[lay].uv = uv_in('chased', a / sides, rows[b][0])
    bmesh.ops.remove_doubles(bm, verts=rings[0] + rings[-1], dist=1e-6)  # the two ends close in a point


# ---------------------------------------------------------------- epaulettes
EP_ARM_SHARE = 0.3                # of the upper arm's weight under it the epaulette keeps: it lies on the shoulder


def on_shoulder(ws, side):
    """The cloth's weights for something lying on the shoulder top: most of what the upper arm moves goes to the
    clavicle (raising the arm would tip the whole epaulette up with the sleeve)."""
    ws = dict(ws)
    arm = ws.pop('upperarm_' + side, 0.0)
    ws['upperarm_' + side] = arm * EP_ARM_SHARE
    ws['clavicle_' + side] = ws.get('clavicle_' + side, 0.0) + arm * (1 - EP_ARM_SHARE)
    return {k: v for k, v in ws.items() if v > 0}


def build_epaulette(side):
    """The field over the shoulder joint, in the shoulder's own frame (the stance turns the shoulders: his left one
    back, the right forward), its outer and front edges lower; lifted until no part of it is in the cloth."""
    sign = 1 if side == 'l' else -1
    cb, ub = rig.data.bones['clavicle_' + side], rig.data.bones['upperarm_' + side]
    out = cb.tail_local - cb.head_local
    out = Vector((out.x, out.y, 0)).normalized()
    fwd = Vector((out.y, -out.x, 0))
    fwd = fwd if fwd.y < 0 else -fwd
    at = ub.head_local + out * EP_OUT
    top = CLOTH.ray_cast(Vector((at.x, at.y, 2.2)), Vector((0, 0, -1)), 1.0)[0]
    Z = (Vector((0, 0, 1)) + out * math.tan(math.radians(EP_TILT)) + fwd * math.tan(math.radians(EP_FORWARD)))
    Z.normalize()
    X = (out - Z * out.dot(Z)).normalized()
    Y = Z.cross(X)
    C = top + Z * EP_LIFT
    for _ in range(3):  # the underside clear of the cloth (the shoulder rounds off under the field's outer end)
        need = 0.0
        for k in range(24):
            a = 2 * math.pi * k / 24
            for f in (0.5, 1.0):
                p = C + X * EP_A * f * math.cos(a) + Y * EP_B * f * math.sin(a) - Z * EP_THICK
                hit = CLOTH.ray_cast(p + Z * 0.2, -Z, 0.4)[0]
                if hit is not None:
                    need = max(need, (hit - p).dot(Z) + 0.002)
        C += Z * need
    print('epaulette %s: centre %s, normal %s' % (side, tuple(round(c, 3) for c in C), tuple(round(c, 2) for c in Z)))
    L = lambda x, y, z: C + X * x + Y * y + Z * z  # noqa: E731
    ws = on_shoulder(UNI_W.at(top), side)
    bm = bmesh.new(); uvs = {}
    # field: domed oval with a flat underside
    rings, segs = 6, 48
    topv = bm.verts.new(L(0, 0, EP_DOME)); uvs[topv] = uv_in('pole', 0.5, 0.5)
    grid = []
    for i in range(1, rings + 1):
        f = i / rings
        ring = []
        for k in range(segs):
            a = 2 * math.pi * k / segs
            v = bm.verts.new(L(EP_A * f * math.cos(a), EP_B * f * math.sin(a), EP_DOME * (1 - f * f)))
            uvs[v] = uv_in('pole', 0.5 + 0.5 * f * math.cos(a), 0.5 + 0.5 * f * math.sin(a))
            ring.append(v)
        grid.append(ring)
    for k in range(segs):
        bm.faces.new((topv, grid[0][k], grid[0][(k + 1) % segs]))
    for r0, r1 in zip(grid, grid[1:]):
        for k in range(segs):
            bm.faces.new((r0[k], r1[k], r1[(k + 1) % segs], r0[(k + 1) % segs]))
    bot = []
    for v in grid[-1]:
        b = bm.verts.new(v.co - Z * EP_THICK); uvs[b] = uv_in('gold', 0.5, 0.5); bot.append(b)
    for k in range(segs):
        bm.faces.new((grid[-1][k], bot[k], bot[(k + 1) % segs], grid[-1][(k + 1) % segs]))
    bm.faces.new(list(reversed(bot)))
    # twisted rim round the field
    rim = [L(EP_A * 1.0 * math.cos(a), EP_B * 1.0 * math.sin(a), -EP_THICK * 0.4)
           for a in [2 * math.pi * k / 72 for k in range(73)]]
    _, u = tube(bm, rim, 0.0075, 6, 'cord', uv_len=0.35, cap=False); uvs.update(u)
    # strap to the collar, its end on the cloth, a button on it
    # every point of it on the cloth (the shoulder rises towards the neck: a straight strap would sink into it), under
    # the field at the field's own height; top and bottom faces, STRAP_T thick
    x_end = sign * STRAP_X - C.x
    strap_len = abs(x_end / X.x) if abs(X.x) > 1e-3 else 0.1
    top_rows, bot_rows = [], []
    n_rows = 16
    for i in range(n_rows + 1):
        f = i / n_rows
        x = -EP_A * 0.6 - (strap_len - EP_A * 0.6) * f
        under = 1 - smoothstep(-x, EP_A * 0.6, EP_A * 0.95)  # 1 while under the field
        trow, brow = [], []
        for y in (-STRAP_W / 2, STRAP_W / 2):
            p0 = L(x, y * (1 - 0.15 * f), -EP_THICK)
            hit, hn = CLOTH.ray_cast(p0 + Z * 0.15, -Z, 0.4)[:2]
            lift = ((hit - p0).dot(Z) + STRAP_GAP) if hit is not None else 0.0
            p = p0 + Z * (max(lift, 0.0) * under + lift * (1 - under))
            b = bm.verts.new(p); t = bm.verts.new(p + Z * STRAP_T)
            uvs[b] = uvs[t] = uv_in('strap', f, 0.5 + y / STRAP_W * 0.9)
            brow.append(b); trow.append(t)
        top_rows.append(trow); bot_rows.append(brow)
    for r0, r1 in zip(top_rows, top_rows[1:]):
        bm.faces.new((r0[0], r0[1], r1[1], r1[0]))
    for r0, r1 in zip(bot_rows, bot_rows[1:]):
        bm.faces.new((r1[0], r1[1], r0[1], r0[0]))
    for k in (0, 1):  # the long sides
        for i in range(n_rows):
            q = (bot_rows[i][k], bot_rows[i + 1][k], top_rows[i + 1][k], top_rows[i][k])
            bm.faces.new(q if k == 0 else q[::-1])
    bm.faces.new((top_rows[-1][1], top_rows[-1][0], bot_rows[-1][0], bot_rows[-1][1]))
    srows = top_rows
    btn_at = (srows[-2][0].co + srows[-2][1].co) / 2
    b2 = bmesh.new()
    bmesh.ops.create_uvsphere(b2, u_segments=12, v_segments=6, radius=0.008)
    bmesh.ops.delete(b2, geom=[v for v in b2.verts if v.co.z < -1e-4], context='VERTS')
    for v in b2.verts:
        v.co.z *= 0.6
    bmesh.ops.transform(b2, matrix=Matrix.Translation(btn_at) @ Z.to_track_quat('Z', 'Y').to_matrix().to_4x4(),
                        verts=b2.verts[:])
    me = bpy.data.meshes.new('tmp'); b2.to_mesh(me); b2.free()
    before = set(bm.verts)
    bm.from_mesh(me); bpy.data.meshes.remove(me)
    for v in set(bm.verts) - before:
        uvs[v] = uv_in('gold', 0.5, 0.5)
    field = new_part('Epaulette_' + side, bm, lambda v: uvs[v], lambda v: ws)
    # fringe: bullion strands from under the rim, out and down, fanning, in two rows (the upper shorter, thicker, over
    # the gaps of the lower). Bullion is stiff: each strand a short bend under the rim, then straight; where the sleeve
    # under it is in the way the whole strand stands further out (its outward reach evened out between neighbours, so
    # the fringe flares as one), never bent round the cloth
    bm = bmesh.new(); uvs = {}; wmap = {}
    half = math.radians(FRINGE_ARC) / 2
    down = Vector((0, 0, -1))

    def strand(rim_p, radial, reach, out_end, length, rad):
        p1 = rim_p + radial * reach * 0.6 + down * 0.008
        loc, nrm, _, _ = CLOTH.find_nearest(p1, 0.05)  # the bend clear of the cloth by the strand's thickness
        if loc is not None and (p1 - loc).dot(nrm) < rad + 0.003:
            p1 = loc + nrm * (rad + 0.003)
        end = rim_p + radial * out_end + down * length
        return catmull([rim_p, p1, p1.lerp(end, 0.5), end], 0.012)

    def deficit(path, rad):  # how far the straight part dips into the cloth (or under the clearance) at worst
        worst = 0.0
        for q in path:
            if (q - path[0]).length < 0.025:
                continue
            loc, nrm, _, _ = CLOTH.find_nearest(q, 0.06)
            if loc is not None:
                worst = max(worst, rad + 0.003 - (q - loc).dot(nrm))
        return worst

    for row, (k_len, rad, k_out, lift, shift) in enumerate(((1.0, FRINGE_R, 1.0, 0.0, 0.0), (*FRINGE_TOP, 0.5))):
        specs = []
        for i in range(FRINGE_N):
            a = -half + 2 * half * (i + 0.5 + shift) / (FRINGE_N + shift)
            rim_p = L(EP_A * 0.97 * math.cos(a), EP_B * 0.97 * math.sin(a), -EP_THICK + lift)
            radial = (X * math.cos(a) * EP_B + Y * math.sin(a) * EP_A).normalized()
            radial = Vector((radial.x, radial.y, 0)).normalized()
            jit = FRINGE_JITTER * math.sin(i * 2.399 + row)
            length = (FRINGE_LEN * (0.92 + 0.08 * math.cos(a)) + jit) * k_len  # longest over the shoulder's end
            reach = FRINGE_OUT * k_out
            out_end = reach * 1.3 + jit
            for _ in range(20):
                d = deficit(strand(rim_p, radial, reach, out_end, length, rad), rad)
                if d <= 0 or out_end >= reach * 1.3 + FRINGE_FLARE:
                    break
                out_end = min(out_end + max(0.002, d), reach * 1.3 + FRINGE_FLARE)
            specs.append([rim_p, radial, reach, out_end, length])
        flare = [sp[3] for sp in specs]
        for _ in range(3):  # neighbours stand out alike: never less than their own need, never far below the next
            flare = [max(flare[i], 0.5 * flare[i] + 0.25 * (flare[max(i - 1, 0)] + flare[min(i + 1, len(flare) - 1)]))
                     for i in range(len(flare))]
        print('fringe %s row %d: reach %.3f..%.3f' % (side, row, min(flare), max(flare)))
        for sp, f in zip(specs, flare):
            rim_p = sp[0]
            path = strand(sp[0], sp[1], sp[2], f, sp[4], rad)
            for it in range(4):  # where it still meets the cloth (over the chest and back, by the neck) it lies on it
                if it:
                    path = [path[0]] + [(path[j - 1] + path[j] * 2 + path[min(j + 1, len(path) - 1)]) / 4
                                        for j in range(1, len(path))]
                for j in range(1, len(path)):
                    loc, nrm, _, _ = CLOTH.find_nearest(path[j], 0.05)
                    if loc is not None and (path[j] - loc).dot(nrm) < rad + 0.003:
                        path[j] = loc + nrm * (rad + 0.003)
            vs, u = tube(bm, path, rad, 8, 'bullion', uv_len=BULLION_UV_LEN)
            uvs.update(u)
            wt = on_shoulder(UNI_W.at(rim_p), side)
            for v in u:
                wmap[v] = wt
    fringe = new_part('EpauletteFringe_' + side, bm, lambda v: uvs[v], lambda v: wmap[v])
    return field, fringe


# the loops first: the sash lies over them (in the portrait they go under it), the loose cords over the sash
loops = build_aiguillettes(bvh_of([uni] + [bpy.data.objects[n] for n in ('Buttons',)], torso=True, tighten=SASH_TIGHTEN),
                           None, 'loops')  # on the tightened cloth: over its folds, as the sash
CLOTH = bvh_of([uni, loops] + [bpy.data.objects[n] for n in ('Belt', 'Buckle', 'Buttons')], torso=True,
               tighten=SASH_TIGHTEN)
sash = build_sash()
aig = build_aiguillettes(None, bvh_of([uni, sash] + [bpy.data.objects[n] for n in ('Belt', 'Buckle', 'Buttons')]),
                         'tails', bvh_of([uni] + [bpy.data.objects[n] for n in ('Belt', 'Buckle', 'Buttons')]))
CLOTH = bvh_of([uni, sash, loops] + [bpy.data.objects[n] for n in ('Belt', 'Buckle', 'Buttons', 'Collar')])
eps = [build_epaulette(s) for s in 'lr']

rig.data.pose_position = 'POSE'
bpy.ops.outliner.orphans_purge(do_recursive=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
print('saved', OUT, os.path.getsize(OUT))

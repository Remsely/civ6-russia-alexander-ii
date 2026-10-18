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
SASH_SRGB = (57, 109, 179)       # the St Andrew blue moire of the portrait (between its lit and shaded side)
# The portrait as a view of the model: tools/blender/render_leader.py's 'ref' (orthographic, the figure turned the
# pose's YAW_DEG towards his left, the crown and the soles on these rows of alexander_ii_full.png). The cords, the
# pencil and the epaulettes' reach are read off the portrait in pixels and cast onto the model along the line of sight.
REF_W, REF_CROWN, REF_SOLES, REF_X = 1024, 12, 1510, 515
# Epaulettes: a rigid oval field (a gilt plate, slightly curved over the shoulder - it does not follow the cloth's
# folds) lying on top of the shoulder, centred on it front to back, its outer end a little past the shoulder's end; a
# thick twisted rim; a strap to the collar with a button; bullion fringe hanging from under the rim round its outer
# three quarters, fanning out over the arm (as in the portrait).
EP_A, EP_B = 0.090, 0.070        # semi-axes along the shoulder and across it (the portrait's field: ~16 cm wide
                                 # with its rim, ~24 cm with the fringe fanning out round it)
EP_REF_X = {'r': 356, 'l': 680}  # the fields' middles where the portrait has them (px across alexander_ii_full.png, as
                                 # the 'ref' view frames the figure): on the shoulder's line front to back, out to there
EP_GAP, EP_DOME, EP_THICK = 0.003, 0.012, 0.006  # the field's underside off the cloth at the nearest, its dome, edge
EP_CURVE = (0.30, 0.09)          # radii of the field's curve along and across the shoulder (a plate bent to it)
EP_TILT = {'r': 28.0, 'l': 24.0}  # degrees the field's outer end is lower: in the portrait both fields face the viewer -
                                 # the camera stands to his right, so his left one is tilted out less (as much, it
                                 # showed its edge); the inner end rises over the slope to the collar (tilted 18 deg,
                                 # it rested there and stood 4-5 cm over the shoulder)
EP_FORWARD = {'r': 26.0, 'l': 34.0}  # degrees its front edge is lower (his left one more, turned to the camera) - in the portrait the
                                 # fields face the viewer (their faces show as ovals ~0.45 as high as wide); fitted to
                                 # the shoulder's slope (~25 deg out) the field was edge-on and the fringe stood out
                                 # like wings
EP_RIM_R = 0.011                 # the rim's radius: a thick padded roll of bullion, as in the portrait
EP_PRESS = (0.004, 0.012)        # the rim pressed this far into the padded shoulder, its outer and inner (towards the
                                 # neck) half (resting on it, the field stood 5 cm over the portrait's)
EP_PRESS_FRONT = 0.014           # ... and the quarter towards the neck and the chest this much more: tilted forward to
                                 # the viewer, the field's front edge rested on the chest and held it 4-5 cm up
STRAP_X, STRAP_W = 0.085, 0.05   # strap from the field to this |x|, by the collar: the epaulette's own broad shoulder
                                 # strap, gold galloon edged in red, as in the portrait
STRAP_T, STRAP_GAP = 0.006, 0.002  # its thickness (a stiff padded galloon, not a ribbon); off the cloth
STRAP_REPEATS = 3                # the galloon picture along the strap
FRINGE_N, FRINGE_ARC = 60, 260.0  # strands over this arc of the rim, centred on the outer end (none by the collar)
FRINGE_LEN, FRINGE_R = 0.082, 0.0095  # a strand's length and radius (the portrait's: about the field's half-width
                                 # long, ~1.7 cm thick, side by side)
FRINGE_ROOT = 0.8                # ... at its root under the rim this share of the radius (they crowd there)
FRINGE_DROOP = (88.0, 80.0)      # degrees below level a strand points at the front and back, and at the outer end
                                 # (straight and stiff, hanging from the rim in a bell round the shoulder as in the
                                 # portrait; fanned out at 48 deg over the arm they stood out like wings; pointed along
                                 # the field's plane, the front ones came at the viewer and looked stubby)
                                 # where the arm, the chest or the cords are in the way a strand bends out over
                                 # them, lying on them (turned up to clear them, the outer ones stuck out level like
                                 # a dish's rim and the front ones came short)
FRINGE_LAYER = (0.9, 6.0, 0.95)  # every other strand behind: its root this far in under the field (x the rim), this
                                 # much steeper (closer to the body), this share as long (the two rows of the portrait)
FRINGE_JITTER = 0.001            # strand to strand: length (a neat even fringe, as in the portrait)
FRINGE_STEP = 0.006              # path sampling along a strand (straight: few rings)
FRINGE_TIP = 0.32                # the bright wire end in each strand's rounded tip (x the radius)
# Bullion (canitel): gold wire coiled tight and the coil twisted - the portrait's strands are beaded all over, a slant
# row of grains per turn of the coil, shining (matt, with a rope's twist, they read as moulded rods)
BULLION_COIL, BULLION_GRAINS, BULLION_UV_LEN = 0.0034, 13, 0.147  # the coil's pitch, grains round a turn; metres of
                                 # strand over the width of its atlas region
BULLION_RELIEF = 0.4             # the coil's height (x pitch) in the normal map
BULLION_METAL, BULLION_ROUGH = (0.15, 0.75), (0.7, 0.32)  # in the gaps, on the grains: gold wire catching the light
THREAD_SRGB = (228, 156, 38)     # gold thread: the portrait's saturated yellow gold (the gilt's own hue read pale
                                 # peach on matt thread)
THREAD_SHEEN = (0.6, 0.35)       # thread's sheen (Principled sheen weight, roughness): soft fibre, not metal
# Sash: a band 'SASH_W' wide round the torso in the plane through the top of the right shoulder and the left hip.
SASH_SHOULDER = Vector((-0.14, 0.0, 1.76))   # in the portrait it runs up close by the collar
SASH_HIP = Vector((0.17, 0.0, 1.31))   # the lower edge on the belt's top at the side
SASH_W, SASH_GAP, SASH_THICK, SASH_N = 0.12, 0.005, 0.002, 320  # the portrait's band: ~12.5 cm wide
SASH_RELAX = 40                  # rounds of smoothing the band and pushing it out of the cloth
SASH_TIGHTEN = 25                # rounds of envelope() of the cloth the sash lies on
SASH_SETTLE = 14                 # rounds of relax() after the lift over the belt (the band's rows ~6 mm apart: fewer
                                 # left a crease where the lift began)
SASH_EVEN = 30                   # rounds of evening out the width along the band
BRIDGE_DZ, BRIDGE_SLOPE, BRIDGE_SPREAD, BRIDGE_SMOOTH = 0.07, 0.0007, 18, 30  # over the belt: zone round its centre; lift lost per step to a neighbour; steps
TORSO_ARM_Z = 1.5                # below this the upper arms' sleeves are not part of the torso surface
GOLD_FLOOR = 0.55                # gold albedo: the pictures' shading only darkens it down to this (the relief does the rest)
NORMAL_STRENGTH = {'pole': 2.0, 'sash': 0.05}  # the pictures' light and dark as relief (the fringe's own)
# Aiguillettes, as the portrait shows them (px of alexander_ii_full.png, cast onto the chest): from under the right
# epaulette's fringe three cords hang down the front by the arm and sweep across in loops to the sash, going in under
# its lower edge one below the other (each carried on under the band to AIG_UNDER past the model's own sash edge,
# thinning there - the band lies over them); outside them a fourth hangs in a loop of its own by the arm, both its ends
# under the fringe. Side by side, at least a cord's thickness apart (where two crossed, the later was lifted over the
# other by its thickness and stood 2 cm off the chest; stack_lift() still keeps them apart if they touch).
AIG_REF = [
    [(362, 352), (366, 382), (372, 412), (378, 442), (385, 466), (392, 489), (399, 497), (402, 493), (397, 466),
     (391, 442), (385, 412), (379, 382), (374, 352)],                                 # the hanging loop by the arm
    [(385, 352), (390, 382), (397, 412), (403, 442), (412, 466), (428, 483), (460, 489), (490, 472), (512, 446)],
    [(396, 352), (401, 380), (409, 405), (420, 430), (437, 450), (456, 460), (476, 454), (498, 432)],
    [(407, 350), (414, 370), (423, 386), (437, 402), (454, 414), (468, 410), (478, 394)],
]
AIG_INTO_SASH = (False, True, True, True)  # which cords end in under the sash (the hanging loop ends under the fringe)
AIG_UNDER = 0.022                # a cord's end this far in under the sash's edge
AIG_THIN = (0.004, 0.02, 0.45)   # under the band from the first to the second (m in from its edge) down to this
# The pencil: in the portrait it hangs over the sash from a gilt crook by the band's upper edge (its knob on the
# coat at the band's edge, where the cord it hangs by comes out from under the band - a stub of that cord, pressed
# under the band's edge, showed as a crumpled lump), its point over the band by the buttons.
PENCIL_KNOB, PENCIL_TOP, PENCIL_END = (582, 383), (610, 401), (617, 526)  # px
KNOB_R, CROOK_R = 0.0085, 0.0048  # the crook's knob and its neck (gilt, cast with the pencil)
AIG_R, AIG_GAP = 0.0065, 0.0015  # the portrait's cords: ~1.3 cm thick round braid
AIG_STEP = 0.003                 # path sampling along a cord (its braid is modelled in its surface)
AIG_STACK = 0.001                # crossing cords: the one on top at least this far off the one under it
BRAID_N, BRAID_PITCH, BRAID_SLANT = 2, 0.0072, 1.45  # the braid's chevrons round the cord, their pitch along it, the
                                 # strands' slant (along per half chevron, x pitch): the herringbone of the portrait's
BRAID_FIBRES = 5                 # fibres across a strand
BRAID_AMP = 0.12                 # the strands stand this much of the radius proud
AIG_STIFF = 10                   # rounds of straightening the cords over the cloth's folds
PENCIL_L = 0.17
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
    'cord': (0.0, 0.75, 1.0, 0.875),      # (twice the texels round the cord and the strand of the regions they had)
    'bullion': (0.0, 0.875, 1.0, 1.0),
    'pole': (0.0, 0.25, 0.5, 0.75),
    'gold': (0.5, 0.25, 0.5625, 0.3125),
    'tip': (0.5625, 0.25, 0.625, 0.3125),  # the fringe strands' bright wire ends
    'strap': (0.5, 0.375, 1.0, 0.5),
    'chased': (0.5, 0.5, 1.0, 0.75),
}
# Gold thread (cords, fringe, galloon, the field's embroidery, the tassels) is yellow fibre, not metal: no metal at
# all, matt, a little smoother on the crests (even a faint metallic on the crests read as metal in a lit viewport);
# the cords and the fringe drawn as fibre - braided strands and twisted plies, each of fine fibres of slightly different
# tone (a smooth helix of coils read as moulded metal). The cast pieces (buttons, pencils) are gilt metal, chased all
# over (the 'chased' region).
THREAD_METAL, THREAD_ROUGH = (0.0, 0.0), (0.92, 0.66)  # in the gaps, on the crests
CAST_METAL, CAST_ROUGH = 0.9, 0.36
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


def fibre_noise(shape, seed):
    """Smooth random tone per texel area (0..1): a few octaves of value noise, for the fibres' uneven colour."""
    rng = np.random.default_rng(seed)
    out = np.zeros(shape, np.float32)
    for cells, wgt in ((8, 0.5), (32, 0.3), (128, 0.2)):
        g = rng.random((cells + 1, cells + 1)).astype(np.float32)
        y = np.linspace(0, cells, shape[0]); x = np.linspace(0, cells, shape[1])
        y0 = np.minimum(y.astype(int), cells - 1); x0 = np.minimum(x.astype(int), cells - 1)
        fy = (y - y0)[:, None]; fx = (x - x0)[None, :]
        a = g[y0][:, x0]; b = g[y0][:, x0 + 1]; c = g[y0 + 1][:, x0]; d = g[y0 + 1][:, x0 + 1]
        out += wgt * ((a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy)
    return out


def thread_colour(h, fib, tone):
    """Gold thread: dark ochre deep in the gaps, the gold on the crests, each fibre its own tone."""
    base = srgb(THREAD_SRGB)
    dark = base * np.array([0.42, 0.33, 0.22], np.float32)
    k = np.clip(h, 0, 1)[..., None]
    c = dark * (1 - k) + base * k
    return np.clip(c * (0.93 + 0.07 * fib[..., None]) * (0.9 + 0.2 * tone[..., None]), 0, 1)


def braid_height(along, round_):
    """The round braid's relief (0..1) at 'along' (pitches along the cord) and 'round_' (0..1 round it): BRAID_N
    columns of chevrons, each a pair of strands slanting from the column's middle line out to its sides (the
    herringbone of the portrait's cords), a groove between the strands, between the pairs and along the middle line;
    also the fibre phase across a strand. Shared by the texture and the cord's modelled surface."""
    w = (round_ * BRAID_N) % 1.0
    tri = np.abs(w - 0.5) * 2.0                    # 0 on a chevron's middle line, 1 at its sides
    f = (along + tri * BRAID_SLANT) % 1.0          # across a strand, from groove to groove
    groove = np.abs(np.sin(np.pi * w * 2.0)) ** 0.35  # the middle line and the sides: the strands part there
    h = np.sin(np.pi * f) ** 0.6 * (0.45 + 0.55 * groove)
    return h, f


def braid_tex(w, hh):
    """The aiguillette's braided cord, its length along u (CORD_UV_LEN metres), round it along v (braid_height), each
    strand of BRAID_FIBRES fibres along it. Returns albedo and the height 0..1."""
    u, v = grid(w, hh)
    h, f = braid_height(u * CORD_UV_LEN / BRAID_PITCH, v)
    fib = 0.5 + 0.5 * np.cos(2 * np.pi * f * BRAID_FIBRES)
    h = h * (0.94 + 0.06 * fib)
    tone = fibre_noise(h.shape, 7)
    return thread_colour(h, fib, tone), h


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


def ply_height(phase):
    """A twisted strand's relief (0..1) at the helix phase (turns along it + plies round it): each ply a round
    bulge, a dark seam between; also the phase across the ply. Shared by the texture and the strand's surface."""
    f = np.asarray(phase) % 1.0
    return np.sin(np.pi * f) ** 0.45, f


def bullion_tex(w, hh):
    """A fringe strand, its length along u (BULLION_UV_LEN metres), round it along v: coiled gold wire, a slanting
    turn per BULLION_COIL, each turn a row of BULLION_GRAINS grains (the beaded look of the portrait's fringe), dark in
    the gaps. Returns albedo, roughness (None) and the height in metres per pixel (for the normal map)."""
    u, v = grid(w, hh)
    turns = u * BULLION_UV_LEN / BULLION_COIL + v  # one slanting turn of the coil round the strand per pitch
    f = turns % 1.0
    g = (v * BULLION_GRAINS + np.floor(turns) * 0.5) % 1.0  # grains along each turn, staggered turn to turn
    h = np.sin(np.pi * f) ** 0.7 * (0.5 + 0.5 * np.sin(np.pi * g) ** 0.6)
    tone = fibre_noise(h.shape, 11)
    return thread_colour(h, h, tone), None, h * BULLION_COIL * BULLION_RELIEF


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
    c, hb = braid_tex(x1 - x0, y1 - y0)
    rgb[y0:y1, x0:x1] = c
    thread('cord', hb)
    nrm[y0:y1, x0:x1] = normals(hb * 0.0012, CORD_UV_LEN / (x1 - x0), 2 * math.pi * AIG_R / (y1 - y0))
    x0, y0, x1, y1 = px('bullion')
    c, r, hgt = bullion_tex(x1 - x0, y1 - y0)
    rgb[y0:y1, x0:x1] = c
    crest = np.clip((hgt / hgt.max()), 0, 1)
    metal[y0:y1, x0:x1] = BULLION_METAL[0] + (BULLION_METAL[1] - BULLION_METAL[0]) * crest
    rough[y0:y1, x0:x1] = BULLION_ROUGH[0] + (BULLION_ROUGH[1] - BULLION_ROUGH[0]) * crest
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
    x0, y0, x1, y1 = px('tip')
    rgb[y0:y1, x0:x1] = srgb((236, 226, 196)); metal[y0:y1, x0:x1] = 1.0; rough[y0:y1, x0:x1] = 0.2
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
    for nd in [nd for nd in nt.nodes if nd.type == 'MATH']:
        nt.nodes.remove(nd)
    sheen = nt.nodes.new('ShaderNodeMath'); sheen.operation = 'MULTIPLY_ADD'  # (1 - metal) x weight: thread only
    sheen.inputs[1].default_value = -THREAD_SHEEN[0]; sheen.inputs[2].default_value = THREAD_SHEEN[0]
    nt.links.new(sep.outputs[0], sheen.inputs[0])
    nt.links.new(sheen.outputs[0], bsdf.inputs['Sheen Weight'])
    bsdf.inputs['Sheen Roughness'].default_value = THREAD_SHEEN[1]
    spec = nt.nodes.new('ShaderNodeMath'); spec.operation = 'MULTIPLY_ADD'  # thread: a weak white specular (it
    spec.inputs[1].default_value = 0.35; spec.inputs[2].default_value = 0.15  # washed the gold out to pale peach)
    nt.links.new(sep.outputs[0], spec.inputs[0])
    nt.links.new(spec.outputs[0], bsdf.inputs['Specular IOR Level'])
    nt.links.new(ta.outputs['Color'], bsdf.inputs['Sheen Tint'])
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


def tube(bm, path, r, sides, region, uv_len=CORD_UV_LEN, cap=True, taper=None, relief=None, u0=0.0):
    """A tube along path into bm (the seam column doubled for the UVs); returns its verts and their UVs. relief(s, v):
    the radius' factor at s metres along and v (0..1) round (the strands of a braid, the plies of a twisted cord,
    modelled); u0: where along its atlas region the tube's texture starts."""
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
            rk = rr * (relief(s + u0 * uv_len, k / sides) if relief else 1.0)
            v = bm.verts.new(p + rk * (math.cos(a) * u + math.sin(a) * w))
            uvs[v] = uv_in(region, min(s / uv_len + u0, 1.0), k / sides)
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
        u_end = min(s / uv_len + u0, 1.0)  # the strand's own texture runs on over the dome (another region's UVs there
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


def braid_relief(s, v):
    return 1.0 + BRAID_AMP * (float(braid_height(s / BRAID_PITCH, v)[0]) - 0.6)


def ply_relief(s, v):
    return 1.0 + BULLION_AMP * (float(ply_height(s / BULLION_PITCH + v * BULLION_STARTS)[0]) - 0.6)


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
    rows = 21  # rows across: fine enough to lie over the cords under it (1.3 cm thick; coarser, they came through it)

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
    # the edge cuts through): how far each vertex must go out (to the outermost surface along the ray from the
    # torso's axis), fading out towards the zone's edges, spread to its neighbours with a gentle slope, the band lifted
    # by it (the radius itself spread, the band above the belt was pushed out to the belt's and fell back in a crease)
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
                    need[i][j] = max(0.0, (loc - ax).length + SASH_GAP + 0.001 - Vector((p.x, p.y, 0.0)).length) * (
                        1 - smoothstep(abs(p.z - zc), BRIDGE_DZ * 0.55, BRIDGE_DZ))
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
            if need[i][j] > 1e-5:
                v.co = v.co + r.normalized() * need[i][j]
                lifted += 1
    print('sash: %d vertices lifted over the belt' % lifted)
    relax(SASH_SETTLE)  # the lifted part folds nowhere
    # its edges for the cords that go in under it and the pencil by it: the last row lies towards his right and down
    # (sides[] point that way) - the lower edge
    SASH_EDGES.update(upper=[v.co.copy() for v in grid[0][:-1]], lower=[v.co.copy() for v in grid[-1][:-1]],
                      mid=[v.co.copy() for v in grid[midr][:-1]])
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


# ---------------------------------------------------------------- the portrait's view
YAW = float(sc.get('pose', {}).get('YAW_DEG', 0.0))
_shown = [(o.matrix_world @ v.co).z for o in sc.objects if o.type == 'MESH' and not o.hide_render
          for v in o.data.vertices]
HEIGHT = max(_shown) - min(_shown)


def ref_ray(px, py):
    """The line of sight through pixel (px, py) of the portrait in model space (as render_leader.py's 'ref' frames
    it): a point in front of the figure, the direction."""
    k = HEIGHT / (REF_SOLES - REF_CROWN)
    a = math.radians(YAW)
    right, d = Vector((math.cos(a), -math.sin(a), 0.0)), Vector((math.sin(a), math.cos(a), 0.0))
    return right * ((px - (REF_W - REF_X)) * k) + Vector((0.0, 0.0, (REF_SOLES - py) * k)) - d, d


def ref_hit(bvh, px, py):
    """Where the portrait's pixel lies on bvh's surface: point, normal (None, None if it misses)."""
    o, d = ref_ray(px, py)
    return bvh.ray_cast(o, d, 2.0)[:2]


# ---------------------------------------------------------------- aiguillettes
SASH_EDGES = {}  # build_sash(): its 'lower' and 'upper' edges and its 'mid' line, round the torso


def sash_in(p, edge='lower'):
    """How far p lies in under the sash from its edge (m across the band; negative outside it)."""
    E, M = SASH_EDGES[edge], SASH_EDGES['mid']
    j = min(range(len(E)), key=lambda i: (E[i] - p).length_squared)
    best = None
    for a in (j - 1, j):
        q0, q1 = E[a % len(E)], E[(a + 1) % len(E)]
        t = max(0.0, min(1.0, (p - q0).dot(q1 - q0) / max((q1 - q0).length_squared, 1e-12)))
        q = q0 + (q1 - q0) * t
        if best is None or (p - q).length < (p - best[0]).length:
            best = (q, M[a % len(M)] - E[a % len(E)])
    q, inward = best
    return (p - q).dot(inward.normalized())


def stack_lift(path, below, frames):
    """Extra lift along the cloth's normal per point of a cord so it lies over the cords laid before it ('below':
    (points, radius) of each) where they cross: at least AIG_STACK off them; ramped along the cord to the crossing.
    frames: (normal, radius) per point."""
    pts = [(q, r) for qs, r in below for q in qs]
    if not pts:
        return [0.0] * len(path)
    kd = KDTree(len(pts))
    for i, (q, _) in enumerate(pts):
        kd.insert(q, i)
    kd.balance()
    need = []
    for p, (n, r) in zip(path, frames):
        t_need = 0.0
        for q, i, d in kd.find_range(p, 4 * AIG_R):
            D = r + pts[i][1] + AIG_STACK
            w = p - q
            b = w.dot(n)
            disc = b * b - w.length_squared + D * D
            if disc > 0:
                t_need = max(t_need, -b + math.sqrt(disc))
        need.append(t_need)
    ramp = int(0.03 / AIG_STEP)  # rises over ~3 cm to the crossing
    out = list(need)
    for i, x in enumerate(need):
        for k in range(1, ramp + 1):
            f = x * (1 - (k / (ramp + 1)) ** 2)
            if i - k >= 0:
                out[i - k] = max(out[i - k], f)
            if i + k < len(out):
                out[i + k] = max(out[i + k], f)
    return out


def build_loops(under):
    """The cords of AIG_REF on the cloth 'under' (tightened: they lie over its folds): each cast from the portrait
    onto it (begun 2.5 cm higher, under the fringe), the sash cords carried on along their last direction to AIG_UNDER
    in under the sash (SASH_EDGES of the band laid without them) - or cut there - and thinned under it; lifted off the
    cloth by their radius, straightened (a thick cord bridges the cloth's folds), laid over the ones before where
    they cross."""
    bm = bmesh.new()
    uvs = {}
    laid = []
    for k, (ref, into) in enumerate(zip(AIG_REF, AIG_INTO_SASH)):
        ref = [(ref[0][0], ref[0][1] - 25)] + list(ref) + ([] if into else [(ref[-1][0], ref[-1][1] - 25)])
        ctrl = [h for h in (ref_hit(under, px, py)[0] for px, py in ref) if h is not None]
        pts = catmull(ctrl, AIG_STEP)
        if into:
            cut = next((i for i, p in enumerate(pts) if sash_in(p) >= AIG_UNDER), None)
            if cut is not None:
                pts = pts[:cut + 1]
            else:
                for _ in range(80):
                    d = (pts[-1] - pts[-3]).normalized()
                    loc = under.find_nearest(pts[-1] + d * AIG_STEP, 0.05)[0]
                    if loc is None:
                        break
                    pts.append(loc)
                    if sash_in(loc) >= AIG_UNDER:
                        break
        n = len(pts)
        thin = [1.0 - (1.0 - AIG_THIN[2]) * smoothstep(sash_in(p), *AIG_THIN[:2]) if into else 1.0 for p in pts]
        nrm = []
        for p in pts:
            nn = under.find_nearest(p, 0.05)[1]
            nrm.append(nn if nn is not None else Vector((0, -1, 0)))
        base = [AIG_R * t + AIG_GAP for t in thin]
        extra = stack_lift(pts, laid, [(nn, AIG_R * t) for nn, t in zip(nrm, thin)])
        lift = [b + e for b, e in zip(base, extra)]
        path = [p + nn * l for p, nn, l in zip(pts, nrm, lift)]
        for _ in range(AIG_STIFF):  # a thick cord is stiff: smooth arcs over the cloth's folds, never into it
            path = [path[0]] + [(path[j - 1] + path[j] * 2 + path[j + 1]) / 4 for j in range(1, n - 1)] + [path[-1]]
            for j in range(1, n - 1):
                loc, nn, _, _ = under.find_nearest(path[j], 0.05)
                if loc is not None and (path[j] - loc).dot(nn) < lift[j]:
                    path[j] = loc + nn * lift[j]
        laid.append((path, AIG_R))
        _, u = tube(bm, path, AIG_R, 12, 'cord', cap=False, taper=lambda t, th=thin: th[round(t * (len(th) - 1))],
                    relief=braid_relief, u0=0.13 * k)
        uvs.update(u)
        print('aiguillette %d: %d points, %.2f m, %s, lifted over the others up to %.4f' % (
            k, n, sum((b - a).length for a, b in zip(path, path[1:])),
            'in under the sash %.3f' % sash_in(pts[-1]) if into else 'a loop', max(extra)))
    return new_part('Aiguillettes', bm, lambda v: uvs[v], lambda v: TORSO_W.at(v.co))


def press_under(ob, cloth, sash):
    """Vertices of ob under the sash that came out through it (a cord passes between the band's vertices) pressed in
    under its inner side, along the cloth's normal."""
    moved = 0
    for v in ob.data.vertices:
        p = v.co.copy()
        loc, nn, _, _ = cloth.find_nearest(p, 0.06)
        if loc is None:
            continue
        hit = sash.ray_cast(loc + nn * 0.0003, nn, 0.06)[0]
        if hit is None:
            continue
        t = (hit - loc).dot(nn)
        h = (p - loc).dot(nn)
        if h > t - 0.0008:
            v.co = p - nn * (h - max(t - 0.0008, 0.0003))
            moved += 1
    ob.data.update()
    print('%s: %d vertices pressed in under the sash' % (ob.name, moved))


def build_pencil(coat, over):
    """The pencil hanging from its crook, as in the portrait: the knob on the coat just off the sash's upper edge (by
    PENCIL_KNOB), where the cord it hangs by comes out from under the band; the crook's neck arching from the knob
    over to the pencil's top (PENCIL_TOP); the pencil hanging straight down from there over the band, resting on it
    where it would touch (its outline lifted off the surface by its own radius: the line over all of it that comes
    nearest)."""
    k_ref = ref_hit(coat, *PENCIL_KNOB)[0]
    E, M = SASH_EDGES['upper'], SASH_EDGES['mid']
    j = min(range(len(E)), key=lambda i: (E[i] - k_ref).length_squared)
    edge, inward = E[j], (M[j] - E[j]).normalized()
    loc, nn, _, _ = coat.find_nearest(edge - inward * (KNOB_R * 0.9), 0.05)
    knob = loc + nn * (KNOB_R + 0.001)
    a = ref_hit(over, *PENCIL_TOP)[0]

    def on_over(q, lift):
        loc, nn, _, _ = over.find_nearest(q, 0.06)
        return loc + nn * lift if loc is not None else q
    n0 = over.find_nearest(a, 0.05)[1]
    d0 = (Vector((0, 0, -1)) - n0 * -n0.z).normalized()
    sh = []
    for k in range(41):
        t = k / 40
        q = on_over(a + d0 * (t * PENCIL_L), pencil_r(t) + AIG_GAP)
        sh.append(((q - a).dot(d0), (q - a).dot(n0)))
    best = None
    for i in range(len(sh)):
        for j2 in range(i + 1, len(sh)):
            (si, hi), (sj, hj) = sh[i], sh[j2]
            if sj - si < 1e-6:
                continue
            beta = (hj - hi) / (sj - si); alpha = hi - beta * si
            if all(alpha + beta * sk >= hk - 1e-6 for sk, hk in sh):
                cost = sum(alpha + beta * sk - hk for sk, hk in sh)
                if best is None or cost < best[0]:
                    best = (cost, alpha, beta)
    _, alpha, beta = best
    top = a + n0 * alpha
    axis = (d0 + n0 * beta).normalized()
    bm = bmesh.new(); uvs = {}
    pencil(bm, uvs, top, axis, PENCIL_L)
    # the crook: the knob, then its neck arching up and over into the pencil's cup
    b2 = bmesh.new()
    bmesh.ops.create_uvsphere(b2, u_segments=24, v_segments=14, radius=KNOB_R)
    bmesh.ops.translate(b2, vec=knob, verts=b2.verts[:])
    up = Vector((0, 0, 1))
    P0, P3 = knob, top + axis * 0.003
    P1, P2 = P0 + up * 0.013 + (P3 - P0) * 0.2, P3 - axis * 0.016
    path = []
    for k in range(25):
        t = k / 24
        q = (1 - t) ** 3 * P0 + 3 * (1 - t) ** 2 * t * P1 + 3 * (1 - t) * t * t * P2 + t ** 3 * P3
        loc, nn, _, _ = over.find_nearest(q, 0.05)
        if 0 < k < 24 and loc is not None and (q - loc).dot(nn) < CROOK_R + AIG_GAP:
            q = loc + nn * (CROOK_R + AIG_GAP)
        path.append(q)
    tube(b2, path, CROOK_R, 10, 'gold', cap=False)
    me = bpy.data.meshes.new('tmp'); b2.to_mesh(me); b2.free()
    before = set(bm.verts)
    bm.from_mesh(me); bpy.data.meshes.remove(me)
    lay = bm.loops.layers.uv.get('UVMap')
    gu = uv_in('gold', 0.5, 0.5)
    for f in bm.faces:
        if any(v not in before for v in f.verts):
            for l in f.loops:
                l[lay].uv = gu
    pencils = new_part('AiguilletteTips', bm, None, lambda v: TORSO_W.at(v.co))
    print('pencil: top %.4f off the sash, leaning out %.1f deg; knob %.3f from the band edge, %.3f from the top' % (
        alpha, math.degrees(math.atan(beta)), (knob - edge).length, (knob - top).length))
    return pencils


def pencil_r(t):
    """The pencil's radius at t along it (PENCIL_PROFILE)."""
    for (t0, r0, *_), (t1, r1, *_) in zip(PENCIL_PROFILE, PENCIL_PROFILE[1:]):
        if t0 <= t <= t1:
            return r0 + (r1 - r0) * (t - t0) / max(t1 - t0, 1e-9)
    return 0.0


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
    """The field: a rigid gilt plate on top of the shoulder - centred on it front to back, its outer end EP_OVER past
    the shoulder's end, tilted out and forward (EP_TILT, EP_FORWARD), bent to it by EP_CURVE, lifted till nothing of
    the cloth (and sash, collar) under it is nearer than EP_GAP (it rests on the shoulder's highest points, standing
    off the rest as a plate does). Laid on the cloth's heights it followed every fold and came out soft and crooked.
    The strap from under it to the collar on the cloth; the fringe round its outer three quarters."""
    sign = 1 if side == 'l' else -1
    cb, ub = rig.data.bones['clavicle_' + side], rig.data.bones['upperarm_' + side]
    out = cb.tail_local - cb.head_local
    out = Vector((out.x, out.y, 0)).normalized()
    fwd = Vector((out.y, -out.x, 0))
    fwd = fwd if fwd.y < 0 else -fwd
    joint = ub.head_local.copy()

    def top_at(p):  # the cloth's top over p (x, y)
        return FIELD_CLOTH.ray_cast(Vector((p.x, p.y, 2.3)), Vector((0, 0, -1)), 1.0)[0]

    def outermost(o, d):
        return FIELD_CLOTH.ray_cast(o + d * 0.4, -d, 0.4)[0]
    # along the shoulder's line (its middle front to back, a little under its top) to where the portrait's field
    # middle shows: bisection on the distance out from the joint
    def on_line(d):
        q = joint + out * d
        t = top_at(q)
        zt = t.z if t is not None else joint.z + 0.05
        q = Vector((q.x, q.y, zt - 0.03))
        f_, b_ = outermost(q, fwd), outermost(q, -fwd)
        return q + fwd * (((f_ + b_) / 2 - q).dot(fwd)) if f_ is not None and b_ is not None else q
    # the field's middle where the portrait shows it across the picture: bisection on the distance out from the joint
    k = HEIGHT / (REF_SOLES - REF_CROWN)
    right = Vector((math.cos(math.radians(YAW)), -math.sin(math.radians(YAW)), 0.0))
    px = lambda q: (REF_W - REF_X) + q.dot(right) / k  # noqa: E731
    lo_, hi_ = -0.06, 0.10
    for _ in range(30):
        mid = (lo_ + hi_) / 2
        if (px(on_line(mid)) - EP_REF_X[side]) * sign > 0:
            hi_ = mid
        else:
            lo_ = mid
    c = on_line((lo_ + hi_) / 2)
    e = outermost(Vector((c.x, c.y, c.z)), out)
    print('epaulette %s: middle %.3f out from the shoulder joint, the shoulder ends %.3f out' % (
        side, (c - joint).dot(out), (e - joint).dot(out) if e is not None else float('nan')))
    Z = (Vector((0, 0, 1)) + out * math.tan(math.radians(EP_TILT[side])) + fwd * math.tan(math.radians(EP_FORWARD[side])))
    Z.normalize()
    X = (out - Z * out.dot(Z)).normalized()
    Y = Z.cross(X)
    C = top_at(c) or c
    L = lambda x, y, z: C + X * x + Y * y + Z * z  # noqa: E731
    shell = lambda x, y: -(x * x / (2 * EP_CURVE[0]) + y * y / (2 * EP_CURVE[1]))  # noqa: E731
    rings, segs = 6, 48

    def cloth_h(x, y):
        hit = FIELD_CLOTH.ray_cast(L(x, y, 0.2), -Z, 0.5)[0]
        return (hit - C).dot(Z) if hit is not None else -1.0
    # the lift: by its edge and rim the plate clears the cloth by EP_GAP; inside, the padded field presses the cloth
    # down - nothing of it may come up through the field's face (cleared everywhere, the field stood 3-4 cm over the
    # round of the shoulder)
    h0 = -1.0
    for i in range(0, 10):
        f = i / 8  # to 1.125: the rim's outside
        for k in range(segs):
            a = 2 * math.pi * k / segs
            x, y = EP_A * f * math.cos(a), EP_B * f * math.sin(a)
            if f >= 0.85:  # (the inner half of the rim, towards the neck, presses into the padded cloth)
                need = ((EP_GAP if f <= 1.0 else EP_RIM_R - EP_THICK * 0.5 + EP_GAP) - EP_PRESS[math.cos(a) < 0]
                        - (EP_PRESS_FRONT if (Y * math.sin(a)).dot(fwd) > 0 else 0.0))
            else:
                need = 0.003 - EP_THICK - EP_DOME * (1 - f * f)
            hh = cloth_h(x, y) - shell(x, y) + need
            if hh > h0:
                h0, worst = hh, (round(f, 2), round(math.degrees(a)), tuple(round(v, 3) for v in L(x, y, 0)))
    U = lambda x, y: h0 + shell(x, y)  # noqa: E731  the plate's underside
    print('epaulette %s: centre %s, normal %s (%.0f deg), plate %.3f over the shoulder top (held up at %s)' % (
        side, tuple(round(v, 3) for v in C), tuple(round(v, 2) for v in Z), math.degrees(Z.angle(Vector((0, 0, 1)))),
        h0, worst))
    ws = on_shoulder(UNI_W.at(C), side)
    bm = bmesh.new(); uvs = {}
    topv = bm.verts.new(L(0, 0, U(0, 0) + EP_THICK + EP_DOME)); uvs[topv] = uv_in('pole', 0.5, 0.5)
    grid = []
    for i in range(1, rings + 1):
        f = i / rings
        ring = []
        for k in range(segs):
            a = 2 * math.pi * k / segs
            x, y = EP_A * f * math.cos(a), EP_B * f * math.sin(a)
            v = bm.verts.new(L(x, y, U(x, y) + EP_THICK + EP_DOME * (1 - f * f)))
            uvs[v] = uv_in('pole', 0.5 + 0.5 * f * math.cos(a), 0.5 + 0.5 * f * math.sin(a))
            ring.append(v)
        grid.append(ring)
    for k in range(segs):
        bm.faces.new((topv, grid[0][k], grid[0][(k + 1) % segs]))
    for r0, r1 in zip(grid, grid[1:]):
        for k in range(segs):
            bm.faces.new((r0[k], r1[k], r1[(k + 1) % segs], r0[(k + 1) % segs]))
    bot = []
    for k, v in enumerate(grid[-1]):
        a = 2 * math.pi * k / segs
        x, y = EP_A * math.cos(a), EP_B * math.sin(a)
        b = bm.verts.new(L(x, y, U(x, y))); uvs[b] = uv_in('gold', 0.5, 0.5); bot.append(b)
    for k in range(segs):
        bm.faces.new((grid[-1][k], bot[k], bot[(k + 1) % segs], grid[-1][(k + 1) % segs]))
    botc = bm.verts.new(L(0, 0, U(0, 0))); uvs[botc] = uv_in('gold', 0.5, 0.5)
    for k in range(segs):
        bm.faces.new((bot[(k + 1) % segs], bot[k], botc))
    # the twisted rim round the field's edge
    rim = []
    for k in range(97):
        a = 2 * math.pi * k / 96
        x, y = EP_A * math.cos(a), EP_B * math.sin(a)
        rim.append(L(x, y, U(x, y) + EP_THICK * 0.5))
    _, u = tube(bm, rim, EP_RIM_R, 12, 'bullion', uv_len=BULLION_UV_LEN * 3, cap=False); uvs.update(u)
    # strap to the collar, from under the field, a button on its end: every point of it on the cloth (and the sash)
    # under it; top, bottom and side faces, STRAP_T thick
    x_end = sign * STRAP_X - C.x
    strap_len = abs(x_end / X.x) if abs(X.x) > 1e-3 else 0.1
    top_rows, bot_rows = [], []
    n_rows = 16
    for i in range(n_rows + 1):
        f = i / n_rows
        x = -EP_A * 0.6 - (strap_len - EP_A * 0.6) * f
        trow, brow = [], []
        for y in (-STRAP_W / 2, STRAP_W / 2):
            p0 = L(x, y * (1 - 0.15 * f), 0.0)
            hit = FIELD_CLOTH.ray_cast(p0 + Z * 0.15, -Z, 0.4)[0]
            p = hit + Z * STRAP_GAP if hit is not None else p0
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
    btn_at = (top_rows[-2][0].co + top_rows[-2][1].co) / 2
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
    # fringe: straight stiff bullion strands from under the rim radiating out and down like a fan (every other one a
    # row behind, rooted further in, steeper, a little shorter: the two rows of the portrait), each ending in a rounded
    # tip with the wire's bright end in it. Where the arm (or the cords, the chest) is in the way a strand bends out
    # over it, lying on it; where it is buried (on the inner end the field rests on the shoulder) there is none.
    bm = bmesh.new(); uvs = {}; wmap = {}
    half = math.radians(FRINGE_ARC) / 2

    def strand(root, radial, droop, length):
        flat = Vector((radial.x, radial.y, 0.0)).normalized()
        d = (flat * math.cos(math.radians(droop)) - Vector((0, 0, 1)) * math.sin(math.radians(droop))).normalized()
        n = max(4, int(length / FRINGE_STEP))
        return [root + d * (length * j / n) for j in range(n + 1)], d

    def deficit(path, rad):  # how far the strand dips into the cloth (or under its clearance) at worst
        worst = 0.0
        for q in path[2:]:
            loc, nrm, _, _ = CLOTH.find_nearest(q, 0.06)
            if loc is not None:
                worst = max(worst, rad + 0.002 - (q - loc).dot(nrm))
        return worst
    specs = []
    for i in range(FRINGE_N):
        a = -half + 2 * half * (i + 0.5) / FRINGE_N
        back = i % 2  # every other strand in the row behind
        rf = FRINGE_LAYER[0] if back else 1.0
        x, y = EP_A * rf * math.cos(a), EP_B * rf * math.sin(a)
        root = L(x, y, U(x, y) - 0.002)
        radial = (X * math.cos(a) * EP_B + Y * math.sin(a) * EP_A).normalized()  # square to the rim, in the plane
        ends = 0.7 + 0.3 * smoothstep(half - abs(a), 0.0, 0.5)  # shorter towards the arc's ends (by the collar)
        length = (FRINGE_LEN + FRINGE_JITTER * math.sin(i * 2.399)) * (FRINGE_LAYER[2] if back else 1.0) * ends
        droop = (FRINGE_DROOP[1] + (FRINGE_DROOP[0] - FRINGE_DROOP[1]) * math.sin(a) ** 2
                 + (FRINGE_LAYER[1] if back else 0.0))
        loc, nrm, _, _ = CLOTH.find_nearest(root, 0.06)
        if loc is not None and (root - loc).dot(nrm) < -FRINGE_R * 0.5:
            continue  # its root buried (on the inner end the field rests on the shoulder)
        specs.append([root, radial, droop, length, back, a])
    print('fringe %s: %d strands, droop %.0f..%.0f deg' % (side, len(specs), min(sp[2] for sp in specs),
                                                          max(sp[2] for sp in specs)))
    def drape(path, rad):  # where it still meets the cloth the strand bends out over it, smoothly
        path = list(path)
        for _ in range(10):
            for j in range(1, len(path)):
                loc, nrm, _, _ = CLOTH.find_nearest(path[j], 0.06)
                if loc is not None and (path[j] - loc).dot(nrm) < rad + 0.002:
                    path[j] = loc + nrm * (rad + 0.002)
            path = [path[0]] + [(path[j - 1] + path[j] * 2 + path[min(j + 1, len(path) - 1)]) / 4
                                for j in range(1, len(path))]
        return path
    for i, (root, radial, droop, length, back, a) in enumerate(specs):
        path, d = strand(root, radial, droop, length)
        if deficit(path, FRINGE_R) > 0:
            path = drape(path, FRINGE_R)
            d = (path[-1] - path[-2]).normalized()
        vs, u = tube(bm, path, FRINGE_R, 10, 'bullion', uv_len=BULLION_UV_LEN,
                     taper=lambda t: FRINGE_ROOT + (1 - FRINGE_ROOT) * smoothstep(t, 0.0, 0.25),
                     u0=0.3 * ((i * 0.618) % 1.0))
        uvs.update(u)
        b2 = bmesh.new()  # the wire's bright end in the tip
        bmesh.ops.create_uvsphere(b2, u_segments=8, v_segments=5, radius=FRINGE_R * FRINGE_TIP)
        bmesh.ops.translate(b2, vec=path[-1] + d * (FRINGE_R * 0.72), verts=b2.verts[:])
        me = bpy.data.meshes.new('tmp'); b2.to_mesh(me); b2.free()
        before = set(bm.verts)
        bm.from_mesh(me); bpy.data.meshes.remove(me)
        for v in set(bm.verts) - before:
            uvs[v] = uv_in('tip', 0.5, 0.5)
        wt = on_shoulder(UNI_W.at(root), side)
        for v in uvs:
            if v not in wmap:
                wmap[v] = wt
    fringe = new_part('EpauletteFringe_' + side, bm, lambda v: uvs[v], lambda v: wmap[v])
    return field, fringe


O = bpy.data.objects
# the sash laid once without the cords: where its edges run (the cords go in under its lower edge, the pencil hangs by
# its upper one); then the cords on the tightened cloth (over its folds, as the sash), the sash over them (in the
# portrait they go under it), whatever of them still comes through it pressed in under it
CLOTH = bvh_of([uni, O['Belt'], O['Buckle'], O['Buttons']], torso=True, tighten=SASH_TIGHTEN)
O.remove(build_sash())
loops = build_loops(bvh_of([uni, O['Buttons']], torso=True, tighten=SASH_TIGHTEN))
CLOTH = bvh_of([uni, loops, O['Belt'], O['Buckle'], O['Buttons']], torso=True, tighten=SASH_TIGHTEN)
sash = build_sash()
UNDER_SASH, SASH_BVH = bvh_of([uni], torso=True), bvh_of([sash])
press_under(loops, UNDER_SASH, SASH_BVH)
pencils = build_pencil(bvh_of([uni, O['Belt'], O['Buckle'], O['Buttons']]),
                       bvh_of([uni, sash, O['Belt'], O['Buckle'], O['Buttons']]))
# what the fringe clears (the cords' tops go in under it) and what the field and strap lie on
CLOTH = bvh_of([uni, sash, loops] + [O[n] for n in ('Belt', 'Buckle', 'Buttons', 'Collar')])
FIELD_CLOTH = bvh_of([uni, sash, O['Collar']])
eps = [build_epaulette(s) for s in 'lr']

rig.data.pose_position = 'POSE'
bpy.ops.outliner.orphans_purge(do_recursive=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
print('saved', OUT, os.path.getsize(OUT))

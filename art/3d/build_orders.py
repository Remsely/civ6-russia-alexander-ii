# Orders, medals and the sabre, as in art/source/alexander_ii_short.png and alexander_ii_full.png, on the posed uniform.
# blender -b art/3d/alexander_leader.blend --python art/3d/build_orders.py   (after build_regalia.py; rewrites in place)
#   -- textures: the atlas and the material only;  -- orders: the Orders pieces placed afresh in the built leader (their
#   vertices moved in place: weights, dangles and the sabre kept - same pieces only)
# - a Maltese cross in dark blue enamel and silver with silver rays lying on the chest, its crown leaning from the
#   cross's notch onto the collar's lower edges and the ring on the collar;
# - six pentagonal ribbon mounts on the left breast, each overlapping the one to its left (tops in a line), a medal
#   hanging by a round ring from each one's point (the white St George cross first; each over the one to its left), a small gold crowned cartouche with a monogram, two silver eight-pointed order stars one above
#   the other - each piece on the plane of the cloth under it;
# - the sabre, straight from the pommel in his left palm down in front of the thigh (the axis chosen clear of the
#   skirt, upright in the leader camera's view): wire-bound grip, knuckle bow, guard with roundels, langets, black
#   scabbard with chased gilt mounts and suspension rings; the sword knot (braided cord, ball, tassel) down along it,
#   and the hanger's cord with its tassel from under the belt (Regalia material: build_regalia.py's braid and bullion).
# Own material 'Orders' and atlas textures/orders_{albedo,mr,normal}.png: a palette row of flat colours, the ribbons,
# chased ornament, drawn faces of the star, the cross and the medals (planar UVs). Every piece rides rigidly on the
# bone weights of the cloth under it (the sabre on the pelvis).
import bpy, bmesh, math, os, sys
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mat_util  # noqa: E402
from mathutils.geometry import tessellate_polygon

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'alexander_leader.blend')
TEXDIR = os.path.join(HERE, 'textures')
TEX = 2048
# palette: name -> (sRGB, metal, roughness)
PALETTE = {
    'gold': (mat_util.GOLD_SRGB, 1.0, 0.3), 'silver': ((222, 224, 230), 0.55, 0.22), 'red': ((165, 18, 24), 0.0, 0.15),
    'blue': ((38, 82, 172), 0.0, 0.15), 'white': ((236, 234, 228), 0.0, 0.2), 'leather': ((14, 14, 16), 0.0, 0.35),
    'navy': ((20, 30, 78), 0.0, 0.15), 'dark_gold': ((150, 95, 38), 1.0, 0.45),
    'pale_blue': ((112, 138, 192), 0.0, 0.15), 'bronze': ((120, 88, 58), 1.0, 0.45),
}
# the palette's cells are big (128 px): small ones bleed into the ribbons in the mipmaps
ATLAS = {'pal': (0.0, 0.0, 1.0, 0.125), 'ribbons': (0.0, 0.125, 0.25, 0.25), 'scrown': (0.25, 0.125, 0.5, 0.25),
         'ornate': (0.5, 0.125, 0.875, 0.25), 'grip': (0.875, 0.125, 1.0, 0.25),
         'star': (0.0, 0.25, 0.5, 0.75),
         'cross': (0.5, 0.25, 1.0, 0.75), 'medal': (0.0, 0.75, 0.1875, 0.9375), 'wcross': (0.1875, 0.75, 0.375, 0.9375),
         'smedal': (0.375, 0.75, 0.5625, 0.9375), 'bmedal': (0.5625, 0.75, 0.75, 0.9375),
         'badge': (0.75, 0.75, 0.9375, 0.9375)}  # the bottom row: five square cells (384 px) - a round piece goes
# elliptical in a cell of any other shape
# Ribbons left to right (stripes as (colour, share)): St George, St Alexander Nevsky, St Andrew, St Vladimir, St Anna,
# the Crimean war medal.
RIBBON_SRGB = {'O': (215, 140, 45), 'K': (18, 18, 20), 'R': (215, 40, 42), 'B': (52, 96, 182), 'Y': (198, 165, 62),
               'L': (120, 170, 225), 'C': (82, 120, 190), 'W': (236, 234, 228)}
STAR_RING_SRGB, STAR_CENTRE_SRGB = (200, 72, 40), (52, 62, 84)  # the stars' medallion: enamel ring, centre
CROSS_PANEL_SRGB = (78, 87, 108)    # the neck cross's arms: dusty slate-blue enamel - in the portrait the cross hangs in
                                     # the collar's shadow and reads dark (its panels' median there); royal blue was a
                                     # bright new toy, the first grey-blue (95, 110, 135) still lighter than the painting
CROSS_SILVER = ((152, 149, 142), 0.5, 0.38)  # the cross's own silver, aged and warm, duller than the palette's (the
                                     # palette's bright mirror read as costume jewellery beside the portrait's worn one)
CROSS_WHITE_SRGB = (198, 195, 186)  # the white border inside the silver edge, aged with it
WCROSS_DOT_SRGB = (172, 66, 50)     # the St George cross's centre: the portrait's dusty dark red, not crimson
RIBBONS = [[('O', 1), ('K', 1), ('O', 1), ('K', 1), ('O', 1)], [('R', 1)], [('B', 1)], [('R', 1)],
           [('Y', 2), ('K', 1), ('Y', 2), ('K', 1), ('Y', 2)], [('C', 1)]]  # six, as in the portrait (its colours
                                   # sampled there: ochre and black, bright scarlet, blue, scarlet, yellow and black, blue)
MEDALS = ['wcross', 'medal', 'medal', 'medal', 'smedal', 'bmedal']  # the portrait's: the white cross, two golds by it,
# a third gold over the silver (the rightmost seen whole), the sixth the Crimean war's dark bronze behind the cords
# (gold-silver-gold from the fourth on before: the silver sat one medal too far left, the last stuck out bright)
# Measured on alexander_ii_full.png (1 px ~ 1.4 mm of the model): the bar ~105 mm wide, its ribbons ~50 mm long, the
# medals ~28 mm across, the St George cross ~40 mm; the neck cross ~62 mm; the stars ~80 mm across.
# The portrait's bar: seven ribbons side by side, edge to edge (overlapping, the stripes of one ran into the next),
# straight strips with their tops in a line, the medals hanging from them and overlapping.
BAR_PX = (565, 300)                # the bar's top left corner in the portrait (px, cast onto the chest): just right of
                                   # the closure's piping, its top level with the cross's lower arm (at a fixed x in the
                                   # model it lay 2.5 cm left, on the piping)
BAR_END_PX = 651                   # ... its right end (the last ribbon's edge): in under the epaulette's fringe (the
                                   # bar 15% larger than first fitted: the portrait's ribbons ~35 px long, ours were 30)
RIB_W, RIB_SIDE, RIB_V = 0.0276, 0.046, 0.0092  # a pentagonal mount (the Russian ribbon folded over its bar):
                                   # 28 mm wide, its sides 46 mm long, the point 9 mm under them
RIB_STEP = (0.0184, 0.0265)         # the step from one mount to the next is found in this range so the bar ends at
                                   # BAR_END_PX: each overlaps the one to its left (as mounts are worn: the bar is not
                                   # stretched with extra ribbons to reach the fringe)
MEDAL_R, WCROSS_S = 0.0195, 0.027  # the medals ~3.7 cm across, the St George cross ~4.7 cm: in the portrait the
                                   # cross is ~1.3 times a medal (~34 and 26 px; at 2.9 and 4.4 cm the medals were small
                                   # for their ribbons and the cross stood out); each overlaps its neighbours, in two
                                   # layers turn about, the cross over both
MEDAL_RING = 0.0028                # the ring a medal hangs by from its mount's point
MEDAL_STEP = 0.0003                # between a medal and the one it overlaps (front to back)
RIB_T, MEDAL_T, MEDAL_DOME = 0.0006, 0.0014, 0.0008  # thicknesses: a ribbon on its mount, a medal (and its dome)
# The bar tilts as the chest does under it as a whole (one slope: tops in a line, all parallel), each ribbon turned
# about the upright to the cloth behind it (round the chest - a flat mount stood off at its ends); the medals likewise,
# each turned about the same upright to the cloth under it, hanging at one height (on one plane, the ones towards his
# middle and his arm stood 1-2 cm off the chest), in two layers turn about, the St George cross over both
CROWN_OUTLINE = [(-0.8, -1.0), (0.8, -1.0), (0.9, -0.55), (1.0, 0.25), (0.7, 0.05), (0.45, 0.6), (0.2, 0.2),
                 (0.08, 0.75), (0.08, 1.0), (-0.08, 1.0), (-0.08, 0.75), (-0.2, 0.2), (-0.45, 0.6), (-0.7, 0.05),
                 (-1.0, 0.25), (-0.9, -0.55)]  # the badge's crown, flat (band, three arches, a cross)
NECK_CROSS_S = 0.037                 # half-size of the neck cross (the portrait's: ~43 px across, 6 cm, on the turned
                                     # chest; at 3.1 cm it came out 35 px); its crown lies
NECK_CROWN_S = 0.011                 # in the collar's opening over its lower edge, the ring on the dark stand (as in the
                                     # portrait); the crown's half-size
NECK_CROSS_UP = -0.004               # ... and the whole cross this much lower (in the portrait its middle is ~25 px
                                     # under the halves' lower corners, the crown just over them)
NECK_RING_R = 0.0032                 # the ring it hangs by
NECK_CROSS_RAYS = 0.8                # the silver rays between its arms reach this far (of the half-size)
BADGE = (630, 396, 0.015, 0.0195)     # px of the portrait (cast onto the cloth), half-width, half-height of the gold
                                     # badge under the bar's right end: a crowned openwork cartouche with a monogram (the
                                     # portrait's), its crown above that
SEAT_N = 5                           # seat(): rays across a piece's footprint each way
STARS = [(666, 400, 0.042), (666, 468, 0.042)]  # px of the portrait (cast onto the cloth), radius: one above the
                                     # other between the sash and the arm, as there (~8.5 cm across, ~1 cm apart, the
                                     # lower one by the sash's edge - over it, it stood 1.6 cm off the cloth; seen at a
                                     # slant on the turning chest: at 7 cm they were specks)
STAR_X = (0.165, 0.155)              # the stars' middles at these x: one over the other on the chest (matched in the
                                     # portrait's view only, the lower one sits deeper on the chest's turn and stood 2.6
                                     # cm further out - a diagonal pair seen from the front or below; at the same x it
                                     # still looked further out from in front, a little from his left); between the
                                     # badge (the upper one's top under its lower right edge) and the sash's edge
STAR_LIFT = 0.0015                   # off the cloth at the nearest
STAR_FACING = 60.0                   # degrees: the cloth under a star faces the viewer at least this squarely
STAR_TURN = 0.1                      # ... and the star turned this much further towards the viewer (pinned on the
                                     # chest's round, the lower one stood edge-on; at 0.25-0.45 its far edge stood off
                                     # the cloth, floating)
LIFT = 0.003
MEDAL_LIFT = 0.002                   # a medal off the cloth at the nearest (at 1 mm the breath brought the cloth through)
# Sabre: pommel under the left palm, the blade hanging down and a little back along the left hip and leg.
POMMEL = Vector((0.24, -0.15, 1.125))   # where the left palm is not found (no rig): fallback
GRIP_L = 0.105                      # pommel to guard
GRIP_IN_PALM = 0.022                # the pommel this far from the hand's axis towards the palm (the fingers close round)
HILT_K = 1.3                        # the hilt's thickness (grip, pommel, guard) times its first build's: the portrait's
                                    # hilt is a big gilt one, the grip filling the fist
BOW_R, BOW_BULGE = 0.0045, 0.028    # the knuckle bow's radius, how far it bows out (a thin wire close to the grip did not
                                    # show under the hand)
BOW_SIDE = Vector((-0.6, -0.8, 0.0))  # ... towards the front and his middle: in the portrait it curves to the left of the
                                    # grip down to the guard
SCABBARD_L, SCABBARD_W, SCABBARD_D = 0.86, 0.048, 0.028
SWORD_CLEAR = 0.012                 # off the skirt, trousers and boot
SWORD_DROP = Vector((0.035, 0.03, -1.0))  # the scabbard hangs nearly straight down, a little out and back
SWORD_TIP_PX = (684, 1388)          # ... its tip where the portrait has it (alexander_ii_full.png, the 'ref' view): the
                                    # sabre slants a little down to the right of the picture
# Its gilt mounts (s along the scabbard from the throat, m): the long locket, two bands carrying the suspension rings,
# the long chape at the tip - chased (the 'ornate' region), standing a little proud of the black leather.
MOUNTS = [(0.0, 0.10), (0.25, 0.285), (0.50, 0.535), (SCABBARD_L - 0.17, SCABBARD_L + 0.05)]
MOUNT_PROUD = 1.08
# Slings: the scabbard hangs by its two rings from the sword belt under the tunic - two narrow straps of black lacquered
# leather out from under the belt at the left hip (without them it hung in the air, held only by the hand)
SLING_W, SLING_T = 0.016, 0.0025     # width, thickness
SLING_TOP_Z = 0.014                  # their tops this far under the belt's lower edge, looped through the clasp's ring
CLASP_W, CLASP_H = 0.024, 0.020      # the gilt clasp they hang from: a plate on the belt's face over its lower edge
                                    # (ending on the skirt 3.5 cm under the belt, it was not clear what held them)
CLASP_RING = (0.011, 0.006, 0.0017)  # ... and the ring hanging from it: half-width, half-height, wire radius
SLING_JOIN = 0.07                    # ... down onto the scabbard's back edge this far under the guard, along it to the rings
SLING_RING_R = 0.007                 # the suspension rings, lying flat on the bands
# Sword knot (temlyak) and the hanger's cord from the belt (both in the portrait): braided gold cord to a knotted ball
# and a tassel of fine bullion (the Regalia material: build_regalia.py's braid and bullion). Heights of the balls.
KNOT_BALL_Z, KNOT_CORD_R = 0.70, 0.0042
BELT_KNOT_X, BELT_KNOT_BALL_Z, BELT_KNOT_R = 0.075, 0.97, 0.0048  # (at x 0.13 it ran into the fist on the hilt, at 0.112
                                    # it pressed into its thumb side, at 0.088 still touched it: the fist reaches in to 0.095)
HAND_CLEAR = 0.003                 # the hanger's cord this far off the skin of the hand it passes: the whole cord moved in
                                    # towards the buckle till it does, 3 mm a step (pushed off the skin point by point,
                                    # it bent in a hook round the little finger)
BELT_KNOT_TUCK = 0.003             # its top on the tunic this far up in under the belt's lower edge (on the belt's face 6
                                    # mm over the edge, its cut end showed there)
TASSEL_LEN, TASSEL_R, TASSEL_STRANDS = 0.07, 0.0125, 40
# build_regalia.py's atlas (TEX 2048) and its texture lengths: the cords' braid and the fringe's bullion
REG_ATLAS = {'cord': (0.0, 0.75, 1.0, 0.875), 'bullion': (0.0, 0.875, 1.0, 1.0)}  # build_regalia.py's ATLAS
REG_CORD_LEN, REG_BULLION_LEN = 0.6, 0.147
GRIP_TURNS, GRIP_BEADS = 16, 22     # the grip's wire: turns pommel to guard, the twist's beads round each turn (the
                                    # portrait's grip is gold wire wound close; per face gold / dark gold, its 12 x 14
                                    # faces read as a chequer)
ORNATE_TILES = (16, 2)              # the ornament's scrolls across / along its region

sc = bpy.context.scene
rig = bpy.data.objects['HumanRig']
POSE_POSITION = rig.data.pose_position
TEXTURES_ONLY = 'textures' in (sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])  # (-- textures)
PLACE_ONLY = 'orders' in (sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])  # (-- orders: the orders'
# pieces placed afresh in the built leader, its vertices moved in place - weights, dangles and the sabre as they are)


def palm_l():
    """The left palm in the stance (the rig's rest is the stance): between the wrist and the knuckles, moved towards
    the side the fingers curl to."""
    bs = rig.data.bones
    if 'hand_l' not in bs or 'middle_01_l' not in bs:
        return POMMEL
    wrist, knuck = bs['hand_l'].head_local, bs['middle_01_l'].head_local
    tips = sum((bs[n].tail_local for n in ('index_03_l', 'middle_03_l', 'ring_03_l') if n in bs), Vector()) / 3
    axis = (knuck - wrist).normalized()
    to_palm = tips - knuck
    to_palm = (to_palm - axis * to_palm.dot(axis)).normalized()
    return wrist.lerp(knuck, 0.65) + to_palm * GRIP_IN_PALM


POMMEL = palm_l()
uni = bpy.data.objects['Uniform']
for o in [] if TEXTURES_ONLY or PLACE_ONLY else list(bpy.data.objects):
    if o.get('orders'):
        bpy.data.objects.remove(o)
bones = {b.name for b in rig.data.bones}


def smoothstep(x, a, b):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def bvh_of(obs):
    bm = bmesh.new()
    for o in obs:
        me = o.data.copy(); me.transform(o.matrix_world); bm.from_mesh(me); bpy.data.meshes.remove(me)
    t = BVHTree.FromBMesh(bm); bm.free()
    return t


def obj(name):
    return bpy.data.objects.get(name)


CHEST = bvh_of([o for o in (uni, obj('Sash'), obj('Belt'), obj('Buttons'), obj('Aiguillettes')) if o])
NO_SASH = bvh_of([o for o in (uni, obj('Belt'), obj('Buttons')) if o])  # the cloth's own slope under the stars
LOWER = bvh_of([o for o in (uni, obj('Belt'), obj('Boot_l'), obj('Boot_r'), obj('Buckle')) if o])
UNI = bvh_of([uni])


def hand_bvh(side):
    """The hand (and fingers) of the body in the stance: what a cord hanging past it must go round."""
    h = obj('Human')
    if h is None:
        return None
    names = [g.name for g in h.vertex_groups]
    part = lambda n: n.endswith('_' + side) and n.split('_')[0] in ('hand', 'index', 'middle', 'ring', 'pinky', 'thumb')  # noqa
    keep = {v.index for v in h.data.vertices if sum(g.weight for g in v.groups if part(names[g.group])) > 0.3}
    mw = h.matrix_world
    vs = [mw @ v.co for v in h.data.vertices]
    fs = [tuple(f.vertices) for f in h.data.polygons if all(i in keep for i in f.vertices)]
    return BVHTree.FromPolygons(vs, fs) if fs else None


HAND_L = hand_bvh('l')


class Weights:
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


TORSO_W = Weights(uni, torso=True)


def blocked(p, r, out=Vector((0.35, -1.0, 0.0)).normalized()):
    """p is under the skirt, trousers, boots or belt (a ray outwards meets them), or nearer them than r + clear."""
    if LOWER.ray_cast(p + out * 1e-4, out, 0.4)[0] is not None:
        return True
    return LOWER.find_nearest(p, r + SWORD_CLEAR)[0] is not None


def sword_axis():
    """The sabre is straight, from the pommel in the palm down through the guard to the scabbard's tip: of the
    directions round SWORD_DROP the nearest one along which nothing of it runs into the skirt or the leg (pushed out
    point by point, it bent into an S over the skirt)."""
    base = SWORD_DROP.normalized()
    # the tip where the portrait has it, seen as the 'ref' view frames the figure
    shown = [(o.matrix_world @ v.co).z for o in sc.objects if o.type == 'MESH' and not o.hide_render
             and not o.get('orders') for v in o.data.vertices]
    k = (max(shown) - min(shown)) / (1510 - 12)
    a = math.radians(float(sc.get('pose', {}).get('YAW_DEG', 0.0)))
    right = Vector((math.cos(a), -math.sin(a), 0.0))

    def px_of(p):
        return Vector(((1024 - 515) + p.dot(right) / k, 1510 - (p.z - min(shown)) / k))
    best = None
    for dx in np.linspace(-0.1, 0.45, 12):
        for dy in np.linspace(-0.32, 0.16, 13):  # held in front of the thigh: the tip a little forward
            d = Vector((float(dx), float(dy), -1.0)).normalized()
            g = POMMEL + d * GRIP_L
            hits = sum(blocked(g + d * (SCABBARD_L * i / 30), SCABBARD_W / 2) for i in range(4, 31))  # the throat
            # may touch the skirt: the hand holds the hilt against the hip
            cost = hits * 10 + (px_of(g + d * SCABBARD_L) - Vector(SWORD_TIP_PX)).length / 10 + abs(d.y)
            if best is None or cost < best[0]:
                best = (cost, d, hits)
    print('sword: axis %s, %d points still in the cloth, tip at px %s (portrait %s)' % (
        tuple(round(c, 3) for c in best[1]), best[2],
        tuple(round(c) for c in px_of(POMMEL + best[1] * (GRIP_L + SCABBARD_L))), SWORD_TIP_PX))
    return best[1]


AXIS = sword_axis()
GUARD = POMMEL + AXIS * GRIP_L
print('hilt: pommel %s guard %s' % (tuple(round(c, 3) for c in POMMEL), tuple(round(c, 3) for c in GUARD)))


# ---------------------------------------------------------------- atlas
def grid(w, hh):
    return np.meshgrid(np.linspace(0, 1, w), np.linspace(0, 1, hh))


def srgb(c):
    return np.array(c, np.float32) / 255


def blur1(a):
    return (a + np.roll(a, 1, 0) + np.roll(a, -1, 0) + np.roll(a, 1, 1) + np.roll(a, -1, 1)) / 5


def in_poly(x, y, poly):
    """Mask of the points (x, y arrays) inside the polygon [(x, y)] (even-odd)."""
    inside = np.zeros(x.shape, bool)
    n = len(poly)
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        cross = ((y1 > y) != (y2 > y)) & (x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1)
        inside ^= cross
    return inside


def erode(mask, k):
    out = mask.copy()
    for _ in range(k):
        out = out & np.roll(out, 1, 0) & np.roll(out, -1, 0) & np.roll(out, 1, 1) & np.roll(out, -1, 1)
    return out


def _maltese():
    arm = [(0.09, 0.09), (0.55, 1.0), (0.0, 0.72), (-0.55, 1.0)]
    out = []
    for k in range(4):
        a = math.pi / 2 * k
        out += [(x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)) for x, y in arm]
    return out


MALTESE = _maltese()


def build_atlas():
    rgb = np.zeros((TEX, TEX, 3), np.float32)
    metal = np.zeros((TEX, TEX), np.float32); rough = np.full((TEX, TEX), 0.6, np.float32)
    height = np.zeros((TEX, TEX), np.float32)

    def px(region):
        u0, v0, u1, v1 = ATLAS[region]
        return int(u0 * TEX), int(v0 * TEX), int(u1 * TEX), int(v1 * TEX)

    def put(region, col, met, rou, hgt):
        x0, y0, x1, y1 = px(region)
        rgb[y0:y1, x0:x1] = col; metal[y0:y1, x0:x1] = met; rough[y0:y1, x0:x1] = rou; height[y0:y1, x0:x1] = hgt

    def pal(name):
        c, m, r = PALETTE[name]
        return srgb(c), m, r

    # palette cells
    x0, y0, x1, y1 = px('pal')
    cw = (x1 - x0) // 8
    for k, name in enumerate(PALETTE):
        c, m, r = pal(name)
        rgb[y0:y1, x0 + k * cw:x0 + (k + 1) * cw] = c; metal[y0:y1, x0 + k * cw:x0 + (k + 1) * cw] = m
        rough[y0:y1, x0 + k * cw:x0 + (k + 1) * cw] = r
    # ribbons: six side by side, each its stripes; a fine rib across (moire silk)
    x0, y0, x1, y1 = px('ribbons')
    u, v = grid(x1 - x0, y1 - y0)
    col = np.zeros(u.shape + (3,), np.float32)
    for k, stripes in enumerate(RIBBONS):
        a = k / len(RIBBONS)
        tot = sum(sh for _, sh in stripes)
        acc = a
        for c, sh in stripes:
            b = acc + sh / tot / len(RIBBONS)
            col[(u >= acc) & (u < b + 1e-6)] = srgb(RIBBON_SRGB[c])
            acc = b
    rib = 0.5 + 0.5 * np.sin(v * 2 * np.pi * 40)
    put('ribbons', col * (0.85 + 0.15 * rib)[..., None], 0.0, 0.45, rib * 0.15)

    def polar(region):
        x0, y0, x1, y1 = px(region)
        u, v = grid(x1 - x0, y1 - y0)
        x, y = u * 2 - 1, v * 2 - 1
        return np.hypot(x, y), np.arctan2(y, x), x, y

    # star: silver rays with fine grooves round an oval medallion as the portrait's - a thin silver rim, an orange-red
    # enamel ring, a dark slate-blue centre with a pale figure in it (a red field with a gold cross was not it)
    r, th, x, y = polar('star')
    c = np.tile(srgb(PALETTE['silver'][0]), r.shape + (1,))
    groove = 0.5 + 0.5 * np.cos(th * 128)  # the rays are cut in fine facets (brilliants), each catching the light
    c = c * (0.7 + 0.3 * groove)[..., None]
    m = np.full_like(r, PALETTE['silver'][1]); ro = 0.2 + 0.15 * (1 - groove); hg = groove * 0.3
    ring = (r > 0.34) & (r < 0.38)
    enamel = (r > 0.25) & (r <= 0.34)
    centre = r <= 0.25
    c[ring] = srgb(PALETTE['silver'][0]); hg = np.where(ring, 0.8, hg)
    c[enamel] = srgb(STAR_RING_SRGB); m = np.where(enamel, 0.0, m); ro = np.where(enamel, 0.12, ro)
    c[centre] = srgb(STAR_CENTRE_SRGB); m = np.where(centre, 0.0, m); ro = np.where(centre, 0.15, ro)
    hg = np.where(enamel, 0.7, np.where(centre, 0.6, hg))
    figure = centre & (np.abs(x) < 0.06) & (np.abs(y) < 0.17)
    c[figure] = srgb((205, 205, 212)); hg = np.where(figure, 0.75, hg)
    put('star', c, m, ro, hg)

    def cross_mask(x, y, inset=0.0):
        """Cross pattee in [-1, 1]: arms flaring from 0.18 at the centre to 0.5 at the ends."""
        ax, ay = np.abs(x), np.abs(y)
        arm_v = (ay <= 1 - inset) & (ax <= 0.18 + 0.32 * ay - inset)
        arm_h = (ax <= 1 - inset) & (ay <= 0.18 + 0.32 * ax - inset)
        return arm_v | arm_h

    def enamel_cross(region, fill):
        r, th, x, y = polar(region)
        c = np.tile(srgb(PALETTE['gold'][0]), r.shape + (1,)); m = np.ones_like(r); ro = np.full_like(r, 0.3)
        hg = np.full_like(r, 0.5)
        inner = cross_mask(x, y, 0.08)
        c[inner] = srgb(PALETTE[fill][0]); m[inner] = 0.0; ro[inner] = 0.12; hg[inner] = 0.7
        if fill == 'blue':  # a white border inside the gold edge, as in the portrait
            edge = inner & ~cross_mask(x, y, 0.16)
            c[edge] = srgb(PALETTE['white'][0])
        med = r < 0.21
        c[med] = srgb(PALETTE['gold'][0]); m[med] = 1.0; ro[med] = 0.3; hg[med] = 0.9
        dot = r < 0.17
        c[dot] = srgb(WCROSS_DOT_SRGB if fill == 'white' else PALETTE['red'][0]); m[dot] = 0.0; ro[dot] = 0.12
        put(region, c, m, ro, hg)

    enamel_cross('wcross', 'white')

    # the neck cross: Maltese (eight points), as in the portrait - aged silver, its arms' enamel dusty slate blue in a
    # broad worn border, a thin dark blue line down each arm's middle, a dark blue medallion in a thin aged silver ring
    # (in the portrait it all hangs in the collar's shadow: bright silver and royal blue read as a new toy)
    r, th, x, y = polar('cross')
    inside = in_poly(x, y, MALTESE)
    inner = erode(inside, 14)
    panel = erode(inside, 52)
    c = np.tile(srgb(CROSS_SILVER[0]), r.shape + (1,)); m = np.full_like(r, CROSS_SILVER[1])
    ro = np.full_like(r, CROSS_SILVER[2])
    hg = np.where(inside, 0.6, 0.0)
    c[inner] = srgb(CROSS_WHITE_SRGB); m[inner] = 0.0; ro[inner] = 0.25; hg[inner] = 0.5
    c[panel] = srgb(CROSS_PANEL_SRGB); hg[panel] = 0.45
    line = inner & ((np.abs(x) < 0.025) | (np.abs(y) < 0.025))
    c[line] = srgb(PALETTE['navy'][0])
    for rr, col, met, h in ((0.27, CROSS_SILVER[0], CROSS_SILVER[1], 0.85), (0.18, PALETTE['navy'][0], 0.0, 0.95),
                            (0.05, CROSS_SILVER[0], CROSS_SILVER[1], 1.0)):
        d = r < rr
        c[d] = srgb(col); m[d] = met; ro[d] = 0.15 if not met else CROSS_SILVER[2]; hg[d] = h
    put('cross', c, m, ro, hg)

    # the badge under the bar: a gold openwork cartouche - a frame of scrolls round a dark field with the monogram
    # (two gold strokes) - as in the portrait
    r, th, x, y = polar('badge')
    scroll = 0.5 + 0.5 * np.sin(th * 7 + r * 14)
    frame = r > 0.58
    relief = np.where(frame, 0.55 + 0.45 * scroll, 0.2)
    c = srgb(PALETTE['gold'][0]) * (0.55 + 0.45 * relief)[..., None]
    m = np.ones_like(r); ro = 0.45 - 0.2 * relief
    lip = (r > 0.5) & (r < 0.58)
    relief = np.where(lip, 0.9, relief); c[lip] = srgb(PALETTE['gold'][0])
    field = r <= 0.5
    c[field] = srgb(PALETTE['navy'][0]) * 0.6; m[field] = 0.0; ro = np.where(field, 0.2, ro)
    mono = field & (np.abs(np.abs(x) - 0.13) < 0.055) & (np.abs(y) < 0.36)
    c[mono] = srgb(PALETTE['gold'][0]); m[mono] = 1.0; ro = np.where(mono, 0.3, ro); relief = np.where(mono, 0.8, relief)
    put('badge', c, m, ro, relief)

    def medal(region, metal_name):
        r, th, x, y = polar(region)
        base = srgb(PALETTE[metal_name][0])
        rim = (r > 0.85)
        relief = np.where(rim, 1.0, 0.4 + 0.3 * np.exp(-((r - 0.45) / 0.18) ** 2) + 0.15 * (r < 0.25))
        c = base * (0.7 + 0.3 * relief)[..., None]
        put(region, c, PALETTE[metal_name][1], 0.3 - 0.1 * relief, relief)

    medal('medal', 'gold')
    medal('smedal', 'silver')
    medal('bmedal', 'bronze')

    # chased gilt ornament for the sabre's mounts: tiles of scrolls (each a spiral leaf, turning the other way in the
    # next tile), a bead border along the long edges - the portrait's mounts are worked all over, not polished
    x0, y0, x1, y1 = px('ornate')
    u, v = grid(x1 - x0, y1 - y0)
    tu, tv = u * ORNATE_TILES[0], v * ORNATE_TILES[1]
    lx, ly = (tu % 1.0) * 2 - 1, (tv % 1.0) * 2 - 1
    flip = np.where((np.floor(tu) + np.floor(tv)) % 2 == 0, 1.0, -1.0)
    r, th = np.hypot(lx, ly), np.arctan2(ly, lx) * flip
    leaf = 0.5 + 0.5 * np.sin(2 * th + 9 * r)
    leaf = np.clip(leaf * 1.4 - 0.2, 0, 1) * (1 - np.clip((r - 0.95) * 8, 0, 1))
    bead = (np.abs(v - 0.5) > 0.44) * (0.5 + 0.5 * np.cos(u * 2 * np.pi * ORNATE_TILES[0] * 4))
    hgt = np.maximum(leaf * 0.8, bead)
    col = srgb(PALETTE['gold'][0]) * (0.5 + 0.5 * hgt)[..., None]
    put('ornate', col, 1.0, 0.5 - 0.22 * hgt, hgt)
    # the grip: twisted gold wire wound round it, u round the grip, v pommel to guard - each turn a rounded wire,
    # beaded by its twist, dark in the grooves between the turns
    x0, y0, x1, y1 = px('grip')
    u, v = grid(x1 - x0, y1 - y0)
    t = (v * GRIP_TURNS + u) % 1.0
    wire = np.sin(np.pi * t) ** 0.6
    hgt = wire * (0.75 + 0.25 * np.cos(2 * np.pi * (u * GRIP_BEADS + 2 * t)))
    col = srgb(PALETTE['gold'][0]) * (0.4 + 0.6 * hgt)[..., None]
    put('grip', col, 1.0, 0.45 - 0.2 * hgt, hgt)
    # the neck cross's crown: gold, chased (the same scrolls, finer), its arches picked out in dark blue - in the
    # portrait it is a small warm gold crown over the collar's lower edge (silver there read as bare metal)
    x0, y0, x1, y1 = px('scrown')
    u, v = grid(x1 - x0, y1 - y0)
    lx, ly = ((u * 5) % 1.0) * 2 - 1, ((v * 5) % 1.0) * 2 - 1
    r, th = np.hypot(lx, ly), np.arctan2(ly, lx)
    hgt = np.clip((0.5 + 0.5 * np.sin(2 * th + 8 * r)) * 1.4 - 0.2, 0, 1) * (1 - np.clip((r - 0.95) * 8, 0, 1))
    col = srgb(PALETTE['gold'][0]) * (0.6 + 0.4 * hgt)[..., None]
    band = (np.abs(u - 0.5) % 0.25 < 0.03) & (v > 0.3)
    col[band] = srgb(PALETTE['navy'][0])
    put('scrown', col, np.where(band, 0.0, PALETTE['gold'][1]), np.where(band, 0.15, 0.3 - 0.1 * hgt), hgt)
    gy, gx = np.gradient(blur1(blur1(height)))
    n = np.stack([-gx * 12, -gy * 12, np.ones_like(height)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    imgs = []
    for name, data, file, cs in (('Orders_Albedo', rgb, 'orders_albedo.png', 'sRGB'),
                                 ('Orders_MR', np.stack([metal, rough, np.zeros_like(metal)], 2), 'orders_mr.png',
                                  'Non-Color'),
                                 ('Orders_Normal', n * 0.5 + 0.5, 'orders_normal.png', 'Non-Color')):
        path = os.path.join(TEXDIR, file)
        img = bpy.data.images.get(name) or bpy.data.images.new(name, TEX, TEX)
        img.scale(TEX, TEX)
        img.pixels.foreach_set(np.concatenate([data, np.ones((TEX, TEX, 1), np.float32)], 2).astype(np.float32).ravel())
        img.filepath_raw = path; img.file_format = 'PNG'; mat_util.write(img)
        img.filepath = path; img.source = 'FILE'; img.colorspace_settings.name = cs
        imgs.append(img)
    mat = bpy.data.materials.get('Orders') or bpy.data.materials.new('Orders')
    mat.use_nodes = True
    nt = mat.node_tree
    for nd in [nd for nd in nt.nodes if nd.type in ('TEX_IMAGE', 'SEPARATE_COLOR', 'NORMAL_MAP')]:
        nt.nodes.remove(nd)
    bsdf = next(nd for nd in nt.nodes if nd.type == 'BSDF_PRINCIPLED')
    ta, tm, tn = (nt.nodes.new('ShaderNodeTexImage') for _ in range(3))
    ta.image, tm.image, tn.image = imgs
    sep = nt.nodes.new('ShaderNodeSeparateColor'); nmap = nt.nodes.new('ShaderNodeNormalMap')
    nt.links.new(ta.outputs['Color'], bsdf.inputs['Base Color'])
    nt.links.new(tm.outputs['Color'], sep.inputs['Color'])
    nt.links.new(sep.outputs[0], bsdf.inputs['Metallic']); nt.links.new(sep.outputs[1], bsdf.inputs['Roughness'])
    nt.links.new(tn.outputs['Color'], nmap.inputs['Color']); nt.links.new(nmap.outputs['Normal'], bsdf.inputs['Normal'])
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
    return (u0 + pad + (u1 - u0 - 2 * pad) * min(max(u, 0), 1), v0 + pad + (v1 - v0 - 2 * pad) * min(max(v, 0), 1))


def pal_uv(name):
    k = list(PALETTE).index(name)
    return uv_in('pal', (k + 0.5) / 8, 0.5)


# ---------------------------------------------------------------- mesh helpers
class Part:
    """Geometry collected into one object: faces with per-corner UVs, flat or smooth, one weight set per piece."""

    def __init__(self, mat=None):
        self.mat = mat
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new('UVMap')
        self.wts = {}

    def face(self, verts, uvs, smooth=True):
        f = self.bm.faces.new(verts)
        for l, uv in zip(f.loops, uvs):
            l[self.uv].uv = uv
        f.smooth = smooth
        return f

    def vert(self, co, w):
        v = self.bm.verts.new(co)
        self.wts[v] = w
        return v

    def build(self, name):
        bm = self.bm
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        wl = [self.wts[v] for v in bm.verts]
        me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
        ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob)
        ob['orders'] = True
        me.materials.append(self.mat or MAT)
        for i, ws in enumerate(wl):
            for n, w in ws.items():
                g = ob.vertex_groups.get(n) or ob.vertex_groups.new(name=n)
                g.add([i], w, 'REPLACE')
        ob.modifiers.new('Armature', 'ARMATURE').object = rig
        print('part %s: %d tris' % (name, sum(len(p.vertices) - 2 for p in me.polygons)))
        return ob


REF_W, REF_CROWN, REF_SOLES, REF_X = 1024, 12, 1510, 515  # as build_regalia.py: the portrait as the 'ref' view
YAW = float(sc.get('pose', {}).get('YAW_DEG', 0.0))
_shown = [(o.matrix_world @ v.co).z for o in sc.objects if o.type == 'MESH' and not o.hide_render
          and o.name != 'Orders' for v in o.data.vertices]
HEIGHT = max(_shown) - min(_shown)


def ref_hit(bvh, px, py):
    """Where the portrait's pixel (px, py) lies on bvh's surface along the line of sight: point, normal."""
    k = HEIGHT / (REF_SOLES - REF_CROWN)
    a = math.radians(YAW)
    right, d = Vector((math.cos(a), -math.sin(a), 0.0)), Vector((math.sin(a), math.cos(a), 0.0))
    o = right * ((px - (REF_W - REF_X)) * k) + Vector((0.0, 0.0, (REF_SOLES - py) * k)) - d
    return bvh.ray_cast(o, d, 2.0)[:2]


def ref_px(q):
    """The portrait's pixel (column, row) where q shows in the 'ref' view (ref_hit's inverse)."""
    k = HEIGHT / (REF_SOLES - REF_CROWN)
    a = math.radians(YAW)
    return (REF_W - REF_X) + q.dot(Vector((math.cos(a), -math.sin(a), 0.0))) / k, REF_SOLES - q.z / k


def chest_frame(x, z, bvh=CHEST):
    """Point on the front of the chest at (x, z) and its frame: X along the cloth to his left, Y up it, N out."""
    loc, nrm = bvh.ray_cast(Vector((x, -1.0, z)), Vector((0, 1, 0)), 2.0)[:2]
    if loc is None:
        loc, nrm = Vector((x, -0.2, z)), Vector((0, -1, 0))
    X = (Vector((1, 0, 0)) - nrm * nrm.x).normalized()
    Y = nrm.cross(X).normalized()
    if Y.z < 0:
        Y = -Y
    return loc, X, Y, nrm


def seat(x, z, hw, hh, bvh, lift=LIFT, up=Vector((0, 0, 1))):
    """A flat piece's frame on the cloth: the plane through the cloth across its footprint (hw x hh round (x, z), seen
    from the front), Y the upright on it, X to his left, N out; the origin moved out till no point of the cloth under
    it is nearer than lift (laid on the tangent at one point, a piece on a slope or by a fold sank into it at one end
    and stood off at the other)."""
    pts = []
    for i in range(SEAT_N):
        for j in range(SEAT_N):
            px_ = x + hw * (2 * i / (SEAT_N - 1) - 1)
            pz = z + hh * (2 * j / (SEAT_N - 1) - 1)
            hit = bvh.ray_cast(Vector((px_, -1.0, pz)), Vector((0, 1, 0)), 2.0)[0]
            if hit is not None:
                pts.append(hit)
    if len(pts) < 3:
        return chest_frame(x, z, bvh)
    A = np.array([p[:] for p in pts])
    c = A.mean(0)
    N = Vector(np.linalg.svd(A - c)[2][2].tolist())
    if N.y > 0:
        N = -N
    Y = (up - N * N.dot(up)).normalized()
    X = Y.cross(N).normalized()
    o = Vector(c.tolist())
    o = o + N * (max((p - o).dot(N) for p in pts) + lift)
    return o, X, Y, N


def lifted(c, X, Y, N, half_w, half_h, need, n=3):
    """c moved out along N until the cloth (CHEST) under the piece's footprint (n x n rays) is at least need behind it."""
    worst = -1.0
    for dx in np.linspace(-half_w, half_w, n):
        for dy in np.linspace(-half_h, half_h, n):
            q = c + X * dx + Y * dy
            hit = CHEST.ray_cast(q + N * 0.05, -N, 0.1)[0]
            if hit is not None:
                worst = max(worst, (hit - q).dot(N))
    return c + N * max(0.0, worst + need)


def plaque(part, outline, frame, size, thick, region, dome=0.0, w=None, flat=False):
    """A flat piece: the 2-D outline (in [-1, 1]) extruded thick, its face mapped onto region (planar), domed up to
    dome at the centre. frame: (origin, X, Y, N)."""
    o, X, Y, N = frame
    P = lambda x, y, h: o + X * (x * size) + Y * (y * size) + N * h  # noqa: E731
    # the face as a fan of triangles from a centre vertex for the dome
    pts = [Vector((x, y, 0)) for x, y in outline]
    tris = tessellate_polygon([pts])
    top = [part.vert(P(x, y, thick + dome * max(0.0, 1 - math.hypot(x, y))), w) for x, y in outline]
    bot = [part.vert(P(x, y, 0.0), w) for x, y in outline]
    for t in tris:
        part.face([top[i] for i in t], [uv_in(region, outline[i][0] * 0.5 + 0.5, outline[i][1] * 0.5 + 0.5) for i in t],
                  smooth=not flat)
    n = len(outline)
    edge = uv_in(region, 0.0, 0.0) if region not in ('star',) else uv_in(region, 0.5, 0.95)
    for i in range(n):
        j = (i + 1) % n
        part.face([bot[i], bot[j], top[j], top[i]], [edge] * 4, smooth=False)
    return top


def star_piece(part, frame, radius, w):
    """Eight-pointed order star of brilliants: eight long rays with shorter ones between, each ray a faceted ridge
    (flat shaded, so the silver catches the light facet by facet); a raised enamel centre."""
    o, X, Y, N = frame
    P = lambda x, y, h: o + X * (x * radius) + Y * (y * radius) + N * h  # noqa: E731
    centre = part.vert(P(0, 0, radius * 0.13), w)
    ring = []
    for k in range(32):
        a = math.pi / 2 + 2 * math.pi * k / 32
        rr, hh = ((1.0, 0.003) if k % 4 == 0 else (0.78, 0.003) if k % 4 == 2 else (0.5, 0.006))
        ring.append((math.cos(a) * rr, math.sin(a) * rr, hh))
    # a ridge line half way out on each ray: the facets fold along it
    mid = []
    for k in range(32):
        x, y, _ = ring[k]
        mid.append((x * 0.55, y * 0.55, radius * (0.08 if k % 2 == 0 else 0.055)))
    rv = [part.vert(P(x, y, h), w) for x, y, h in ring]
    mv = [part.vert(P(x, y, h), w) for x, y, h in mid]
    uv = lambda q: uv_in('star', q[0] * 0.5 + 0.5, q[1] * 0.5 + 0.5)  # noqa: E731
    for k in range(32):
        k2 = (k + 1) % 32
        part.face([centre, mv[k], mv[k2]], [uv((0, 0)), uv(mid[k]), uv(mid[k2])], smooth=False)
        part.face([mv[k], rv[k], rv[k2], mv[k2]], [uv(mid[k]), uv(ring[k]), uv(ring[k2]), uv(mid[k2])], smooth=False)
    # the enamel centre: a low dome over the ridges
    medal = []
    cen = part.vert(P(0, 0, radius * 0.17), w)
    for k in range(24):
        a = 2 * math.pi * k / 24
        medal.append(part.vert(P(math.cos(a) * 0.38, math.sin(a) * 0.38, radius * 0.12), w))
    uvc = uv_in('star', 0.5, 0.5)
    for k in range(24):
        a1, a2 = 2 * math.pi * k / 24, 2 * math.pi * (k + 1) / 24
        part.face([cen, medal[k], medal[(k + 1) % 24]],
                  [uvc, uv_in('star', 0.5 + 0.19 * math.cos(a1), 0.5 + 0.19 * math.sin(a1)),
                   uv_in('star', 0.5 + 0.19 * math.cos(a2), 0.5 + 0.19 * math.sin(a2))])


def lathe(part, axis_o, axis_d, profile, uv_of, w, segs=16, ref=None):
    """A surface of revolution: profile [(t along the axis in m, radius)], uv_of(i, k) per ring i and segment k."""
    d = axis_d.normalized()
    ref = ref or (Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0)))
    a = d.cross(ref).normalized(); b = d.cross(a)
    rings = []
    for i, (t, r) in enumerate(profile):
        rings.append([part.vert(axis_o + d * t + (a * math.cos(2 * math.pi * k / segs) + b * math.sin(2 * math.pi * k / segs)) * r, w)
                      for k in range(segs)])
    for i in range(len(rings) - 1):
        for k in range(segs):
            k2 = (k + 1) % segs
            part.face([rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]],
                      [uv_of(i, k), uv_of(i, k2), uv_of(i + 1, k2), uv_of(i + 1, k)])
    return rings


def tube(part, path, r, uvf, w, sides=8, rx=None, ref=None):
    """Tube along path, elliptical if rx is given (rx along the frame's first axis); uvf(i, k) per ring and side."""
    prev = None
    rings = []
    for i, p in enumerate(path):
        t = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized()
        if prev is None:
            rr = ref or (Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((0, 1, 0)))
            prev = (rr - t * rr.dot(t)).normalized()
        u = (prev - t * prev.dot(t)).normalized(); prev = u
        v = t.cross(u)
        rad = r(i / (len(path) - 1)) if callable(r) else r
        ring = []
        for k in range(sides):
            a = 2 * math.pi * k / sides
            ring.append(part.vert(p + u * math.cos(a) * (rx or rad) + v * math.sin(a) * rad, w(i) if callable(w) else w))
        rings.append(ring)
    for i in range(len(rings) - 1):
        for k in range(sides):
            k2 = (k + 1) % sides
            # one palette cell per face (by its first ring): corners in different cells would run through the palette
            part.face([rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]],
                      [uvf(i, k), uvf(i, k2), uvf(i, k2), uvf(i, k)])
    return rings


def cap(part, ring, centre, uv):
    c = part.vert(centre, part.wts[ring[0]])
    for k in range(len(ring)):
        part.face([ring[k], ring[(k + 1) % len(ring)], c], [uv] * 3)


# ---------------------------------------------------------------- orders
CROSS_OUTLINE = [(0.18, 0.18), (0.5, 1), (-0.5, 1), (-0.18, 0.18), (-1, 0.5), (-1, -0.5), (-0.18, -0.18), (-0.5, -1),
                 (0.5, -1), (0.18, -0.18), (1, -0.5), (1, 0.5)]
DISC = [(math.cos(2 * math.pi * k / 24), math.sin(2 * math.pi * k / 24)) for k in range(24)]


def rays(n_arms=4, width=0.3, inner=0.22, outer=NECK_CROSS_RAYS, off=math.pi / 4):
    """Outline of bundles of rays between a cross's arms: per gap a fan of three points, in [-1, 1]."""
    pts = []
    for k in range(n_arms):
        c = off + 2 * math.pi * k / n_arms
        for j, (da, rr) in enumerate(((-width, inner), (-width * 0.55, outer * 0.86), (-width * 0.2, inner * 1.3),
                                      (0.0, outer), (width * 0.2, inner * 1.3), (width * 0.55, outer * 0.86),
                                      (width, inner))):
            pts.append((math.cos(c + da) * rr, math.sin(c + da) * rr))
    return pts


def build_orders():
    part = Part()
    # neck cross: its crown over the collar's lower edge, the ring it hangs by on the collar, as in the portrait (no
    # ribbon shows): Maltese cross in dark blue enamel and silver, silver rays between the arms; the cross on the chest,
    # the crown on the collar, each on the plane of what is under it
    s = NECK_CROSS_S
    col = obj('Collar')
    me = col.data
    front = min(v.co.y for v in me.vertices)
    edge = [v.co for v in me.vertices if v.co.y < front + 0.03]
    x = sum(p.x for p in edge) / len(edge)
    z_open = min(p.z for p in edge if abs(p.x - x) < 0.05)  # the halves' corners
    # across the middle of the opening: the widest gap between the halves' vertices over their corners (the mean of
    # the front's vertices lay 1.2 cm to his right - the halves come forward unevenly with the turned neck)
    xs = sorted(p.x for p in edge if z_open < p.z < z_open + 0.04 and abs(p.x - x) < 0.05)
    x = max(zip(xs, xs[1:]), key=lambda g: g[1] - g[0])
    x = (x[0] + x[1]) / 2
    z_open += col.get('dip', 0.0)  # ... a little over their foot (the portrait's cross hangs between them)
    cs = NECK_CROWN_S
    notch = 0.74  # the top arm's notch, where the crown stands (MALTESE: its points at 1.0, the notch at 0.72)
    zc = z_open + NECK_CROSS_UP - cs * 0.4 - s * notch  # the crown's upper half over the collar's edge, the ring on it
    collar = bvh_of([col, obj('CollarStand'), uni])  # over the halves' dipped corners too (it lies on them)
    o, X, Y, N = seat(x, zc, s * 0.9, s * 0.9, collar, LIFT + 0.0015)
    print('neck cross at x %.3f z %.3f y %.3f (collar edge z %.3f)' % (x, zc, o.y, z_open))

    def crown_on(o, X, Y, N):
        """The crown from the notch up along the collar, lying on what is under it - the halves' rolled lower edges
        at its sides, the stand between them (seated on the plane over the notch's height it stood upright, 1-2 cm out
        in front of the neck with the ring on top): of the tilts back or forward from the cross's own, the one it lies
        closest on (back only, its foot left the notch by 1 cm, and turning the cross out to it stood the cross off).
        Returns cost, tilt, its centre, X, Y, N, how far out it had to go off the notch."""
        notch_at = o + Y * (s * notch) + N * 0.0015
        samples = [(a_, b_) for a_ in (-0.9, -0.45, 0.0, 0.45, 0.9) for b_ in (-0.9, -0.3, 0.3, 0.9)]
        best = None
        for tilt in range(-60, 61, 2):  # back towards the neck (+) or forward over the halves' edges (-)
            t_ = math.radians(tilt)
            cY = (Y * math.cos(t_) - N * math.sin(t_)).normalized()
            cN = (N * math.cos(t_) + Y * math.sin(t_)).normalized()
            cX = cY.cross(cN).normalized()
            base = notch_at + cY * cs
            gaps = []
            for a_, b_ in samples:
                q = base + cX * (cs * a_) + cY * (cs * b_)
                hit = collar.ray_cast(q + cN * 0.05, -cN, 0.1)[0]
                if hit is not None:
                    gaps.append((q - hit).dot(cN))
            if not gaps:
                continue
            lift_ = max(0.0, LIFT - min(gaps))  # out till nothing under it is nearer than LIFT
            cost = sum(g_ + lift_ for g_ in gaps) / len(gaps) + 2 * lift_  # (its foot off the notch counts double)
            if best is None or cost < best[0]:
                best = (cost, tilt, base + cN * lift_, cX, cY, cN, lift_)
        return best

    # the cross lies on the chest; should the crown still have to leave its notch, the cross is turned out about its
    # lower point till they meet (forward tilts let it lean onto the halves' edges from the notch: none needed)
    for _ in range(6):
        best = crown_on(o, X, Y, N)
        if best[6] < 0.0003:
            break
        foot = o - Y * s
        t_ = math.atan2(best[6], s * (1 + notch))
        Y, N = (Y * math.cos(t_) + N * math.sin(t_)).normalized(), (N * math.cos(t_) - Y * math.sin(t_)).normalized()
        o = foot + Y * s
    _, tilt, co_, cX, cY, cN, lift_ = best
    w = TORSO_W.at(o)
    plaque(part, rays(), (o - N * 0.0022, X, Y, N), s, 0.0015, 'ornate', w=w, flat=True)  # gold, as in the portrait;
    # wholly under the cross (1 mm under it, the rays' fans came up through its enamel as needles)
    plaque(part, MALTESE, (o, X, Y, N), s, 0.003, 'cross', dome=0.003, w=w)
    print('neck cross crown: tilted %d deg back from the cross, %.0f deg from upright, its foot %.4f off the notch; '
          'the cross %.0f deg from upright' % (tilt, math.degrees(math.acos(max(-1.0, min(1.0, cY.z)))), lift_,
                                              math.degrees(math.acos(max(-1.0, min(1.0, Y.z))))))
    plaque(part, CROWN_OUTLINE, (co_, cX, cY, cN), cs, 0.003, 'scrown', dome=0.0015, w=w)
    top = co_ + cY * (cs + NECK_RING_R * 0.8) + cN * 0.0015
    ring = [top + cX * (math.cos(a) * NECK_RING_R) + cY * (math.sin(a) * NECK_RING_R)
            for a in (2 * math.pi * k / 16 for k in range(17))]
    tube(part, ring, 0.0009, lambda i, k: pal_uv('silver'), w, sides=6)
    # ribbon bar: six pentagonal mounts, their tops in one line along the cloth, each on the plane of the cloth under
    # it, every one over the one to its left; a medal hangs by a ring from each one's point, on the cloth under it, in
    # two layers turn about, the cross over both
    n = len(RIBBONS)
    corner = ref_hit(NO_SASH, *BAR_PX)[0]
    BAR_X, BAR_Z = corner.x, corner.z
    H = RIB_SIDE + RIB_V
    span = RIB_STEP[1] * (n - 1) + RIB_W
    Yb = seat(BAR_X + span / 2, BAR_Z - H / 2, span / 2, H / 2, NO_SASH)[2]

    def march(step):
        out, p = [], corner
        for k in range(n):
            o, _, _, N = seat(p.x + RIB_W / 2, p.z - H / 2, RIB_W / 2, H / 2, NO_SASH, 0.0)
            N = (N - Yb * N.dot(Yb)).normalized()
            X = Yb.cross(N).normalized()
            out.append((p, X, N))
            nxt = p + X * step  # the next mount: step on along the cloth, back onto it, its top on the line
            hit = NO_SASH.ray_cast(nxt + N * 0.05, -N, 0.1)[0]
            p = hit if hit is not None else nxt
            p = p + Yb * ((BAR_Z - p.z) / max(Yb.z, 0.5))
        return out
    lo_, hi_ = RIB_STEP
    for _ in range(20):
        step = (lo_ + hi_) / 2
        last = march(step)[-1]
        if ref_px(last[0] + last[1] * RIB_W)[0] > BAR_END_PX:
            hi_ = step
        else:
            lo_ = step
    mounts = march(step)
    outline = [(0.0, 0.0), (RIB_W, 0.0), (RIB_W, -RIB_SIDE), (RIB_W / 2, -H), (0.0, -RIB_SIDE)]
    tris = tessellate_polygon([[Vector((x, y, 0.0)) for x, y in outline]])
    w = TORSO_W.at(corner)
    tips, lifts = [], []
    for k, (p, X, N) in enumerate(mounts):
        # off the cloth under its whole face by LIFT, and over the one to its left
        worst = -1.0
        for i in range(5):
            for j in range(6):
                q = p + X * (RIB_W * i / 4) - Yb * (H * j / 5)
                hit = NO_SASH.ray_cast(q + N * 0.05, -N, 0.1)[0]
                if hit is not None:
                    worst = max(worst, (hit - q).dot(N))
        o = p + N * (max(worst, 0.0) + LIFT + (RIB_T + 0.0003) * k)
        lifts.append(max(worst, 0.0))
        P = lambda x, y, h: o + X * x + Yb * y + N * h  # noqa: E731
        top = [part.vert(P(x, y, RIB_T), w) for x, y in outline]
        bot = [part.vert(P(x, y, 0.0), w) for x, y in outline]
        uv = [uv_in('ribbons', (k + x / RIB_W) / n, 1 + y / H) for x, y in outline]
        for t in tris:
            part.face([top[i] for i in t], [uv[i] for i in t])
            part.face([bot[i] for i in t[::-1]], [uv[i] for i in t[::-1]])
        edge = uv_in('ribbons', (k + 0.02) / n, 0.5)
        for i in range(len(outline)):
            j = (i + 1) % len(outline)
            part.face([bot[i], bot[j], top[j], top[i]], [edge] * 4, smooth=False)
        tips.append((P(RIB_W / 2, -H, RIB_T * 0.5), X, N))
    # the medals: each hung by its ring from its mount's point (the ring round, its top there), turned about the bar's
    # upright to the cloth under it and swung about its top in onto the cloth, MEDAL_LIFT off it at the nearest (moved
    # flat onto the cloth the ones nearer the arm sank under their mounts and their rings stretched; left on the bar's
    # plane the ones nearer the middle stood off); as in the portrait each over the one to its left, the cross over
    # all, each turned about its upright through its top (its left edge out) as little as lies it on that one - none
    # moved off its ring (in two layers turn about, the front ones stood 3-4 mm off their rings: seen from above the
    # row came apart)
    def face_pts(kind, n_):
        """Points over a medal's face (in its own [-1, 1]), its outline's corners included (sampled in a circle, the
        cross's arm tips went through the medal beside it)."""
        outline = CROSS_OUTLINE if kind == 'wcross' else DISC

        def inside(x, y):
            c_ = False
            for i_ in range(len(outline)):
                (x1, y1), (x2, y2) = outline[i_], outline[i_ - 1]
                if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                    c_ = not c_
            return c_
        g = np.linspace(-0.99, 0.99, n_)
        return [(x, y) for x in g for y in g if inside(x, y)] + [(x * 0.98, y * 0.98) for x, y in outline]

    def gaps(mc, X, Y, N, size, kind):
        out = []
        for du, dv in face_pts(kind, 7):
            q = mc + X * (du * size) + Y * (dv * size)
            hit = CHEST.ray_cast(q + N * 0.05, -N, 0.1)[0]
            if hit is not None:
                out.append((q - hit).dot(N))
        return out

    def over(mc, X, Y, N, size, kind, under):
        """How far short of clearing the medals under it the face is (<= 0: clear)."""
        short = -1.0
        for sa, ca, Xa, Ya, Na, ka in under:
            if (ca - mc).length > (sa + size) * 1.15:
                continue
            for du, dv in face_pts(kind, 13):
                rel = mc + X * (du * size) + Y * (dv * size) - ca
                ra = math.hypot(rel.dot(Xa), rel.dot(Ya)) / sa
                lim = 1.0 if ka != 'wcross' else 1.12
                if ra < lim:  # over a's face there, its dome included
                    short = max(short, MEDAL_T + MEDAL_DOME * max(0.0, 1 - ra) + MEDAL_STEP - rel.dot(Na))
        return short

    first = MEDALS.index('wcross')
    order = [k for k in range(len(tips)) if k != first] + [first]  # bottom up: left to right, the cross last
    frames = []
    for k, (tip, X, N) in enumerate(tips):
        size = WCROSS_S if MEDALS[k] == 'wcross' else MEDAL_R
        pts = [h for h in (CHEST.ray_cast(tip - Yb * (MEDAL_RING * 2 + size) + X * du + Yb * dv + N * 0.05, -N, 0.1)[0]
                           for du in np.linspace(-size, size, 5) for dv in np.linspace(-size, size, 5)) if h]
        if len(pts) >= 3:  # turned about the upright to the cloth under the medal itself
            A = np.array([q[:] for q in pts])
            n_ = Vector(np.linalg.svd(A - A.mean(0))[2][2].tolist())
            n_ = (n_ - Yb * n_.dot(Yb)).normalized()
            N = n_ if n_.dot(N) > 0 else -n_
            X = Yb.cross(N).normalized()
        frames.append((tip - Yb * (MEDAL_RING * 2) - N * (MEDAL_T / 2), X, N, size))  # its top: the ring round

    def hang(deg):
        """All swung alike by deg (foot in +), each turned about its upright (left edge out +) as little as clears the
        cloth and the one it lies on; moved out along its face only if no turn does. Returns the medals, the moves,
        the turns, how far the faces stand off the cloth over MEDAL_LIFT."""
        a = math.radians(deg)
        out, moves, turns, off = [None] * len(tips), [0.0] * len(tips), [0] * len(tips), 0.0
        for k in order:
            pivot, X0, N0, size = frames[k]
            kind = MEDALS[k]
            on = [k - 1] if 0 < k - 1 != first else ([] if k != first else [first + 1])
            under = [(out[u][3], out[u][4], out[u][5], out[u][6], out[u][7], out[u][2]) for u in on if out[u] is not None]
            pick = None
            for t in sorted(range(-12, 21), key=abs):
                f_ = math.radians(t)
                X = X0 * math.cos(f_) - N0 * math.sin(f_)
                N = N0 * math.cos(f_) + X0 * math.sin(f_)
                mY = Yb * math.cos(a) + N * math.sin(a)
                mN = N * math.cos(a) - Yb * math.sin(a)
                mc = pivot - mY * (size * (1.0 if kind == 'wcross' else 0.98))
                g = gaps(mc, X, mY, mN, size, kind)
                short = max(MEDAL_LIFT - min(g or [MEDAL_LIFT]), over(mc, X, mY, mN, size, kind, under))
                if pick is None or short < pick[0] - 1e-5:
                    pick = (short, t, mc, X, mY, mN, g)
                if short <= 0:
                    break
            short, t, mc, X, mY, mN, g = pick
            push = max(0.0, short)
            mc = mc + mN * push
            moves[k], turns[k] = push, t
            if kind != 'wcross':
                off += max(0.0, sum(g) / max(len(g), 1) - MEDAL_LIFT - 0.004)  # standing off past 4 mm
            out[k] = [0, k, kind, size, mc, X, mY, mN]
        return out, moves, turns, off

    best = None
    for deg in range(-30, 31, 2):
        out, moves, turns, off = hang(deg)
        cost = 20 * (sum(moves) + max(moves)) + 0.5 * off + 0.00002 * sum(abs(t) for t in turns)
        if best is None or cost < best[0]:
            best = (cost, deg, out, moves, turns)
    _, swing, medals, moves, turns = best
    for k, (tip, X, N) in enumerate(tips):
        _, _, kind, size, mc, mX, mY, mN = medals[k]
        top_pt = mc + mY * (size * (1.0 if kind == 'wcross' else 0.98)) + mN * (MEDAL_T / 2)
        plaque(part, CROSS_OUTLINE if kind == 'wcross' else DISC, (mc, mX, mY, mN), size, MEDAL_T, kind,
               dome=MEDAL_DOME, w=w)
        # the ring: from the mount's point down to the medal's top
        rc = (tip + top_pt) / 2
        rr = max((tip - top_pt).length / 2, MEDAL_RING)
        ax = (tip - top_pt).normalized() if (tip - top_pt).length > 1e-5 else mY
        # (a medal moved out off its mount: the ring larger, not drawn out)
        ring = [rc + ax * (math.cos(a) * rr) + mX * (math.sin(a) * rr * 0.8)
                for a in (2 * math.pi * q / 16 for q in range(17))]
        tube(part, ring, 0.0007, lambda i, q: pal_uv('gold'), w, sides=6)
    print('ribbon bar: %d mounts %.4f apart from x %.3f to %.3f (px %d..%d), tops at z %.3f, cloth up to %.4f in front '
          'of a mount plane, medals %.4f off the cloth at the nearest, all swung in %d deg, turned %s deg, moved out '
          'off their rings %s mm' % (n, step, BAR_X, (mounts[-1][0] + mounts[-1][1] * RIB_W).x, ref_px(corner)[0],
                                     ref_px(mounts[-1][0] + mounts[-1][1] * RIB_W)[0], BAR_Z, max(lifts), MEDAL_LIFT,
                                     swing, turns, ' '.join('%.1f' % (m_ * 1000) for m_ in moves)))
    # the gold badge under the bar: the cartouche, scalloped round, its crown standing on it, both on the cloth's plane
    bpx, bpy, bw, bh = BADGE
    hit = ref_hit(CHEST, bpx, bpy)[0]
    x, z = hit.x, hit.z
    cs = bw * 0.8
    o, X, Y, N = seat(x, z + cs * 0.8, bw, bh + cs * 0.8, CHEST)
    o = o - Y * (cs * 0.8)
    w = TORSO_W.at(o)
    cart = [((1 + 0.07 * math.cos(10 * a)) * math.cos(a), (1 + 0.07 * math.cos(10 * a)) * math.sin(a))
            for a in (2 * math.pi * k / 40 for k in range(40))]
    plaque(part, cart, (o, X * (bw / bh), Y, N), bh, 0.0025, 'badge', dome=0.002, w=w)
    badge_x = o.x
    plaque(part, CROWN_OUTLINE, (o + N * 0.0008 + Y * (bh + cs * 0.75), X, Y, N), cs, 0.0025, 'ornate',
           dome=0.001, w=w)
    # stars: where the portrait shows them, on the cloth's plane under each (on the tangent at one point a star
    # sank into the cloth at one side)
    a = math.radians(YAW)
    view = Vector((math.sin(a), math.cos(a), 0.0))
    cols = []
    for px, py, r in STARS:
        for _ in range(60):  # the model's chest is narrower than the painted one: in from its side to where the cloth
            p, nrm = ref_hit(NO_SASH, px, py)  # still faces the viewer (past it, under the arm, a star stood edgeways)
            if p is not None and nrm.dot(-view) > math.cos(math.radians(STAR_FACING)):
                break
            px -= 2
        cols.append(px)
    # one straight above the other on the chest (the same x: cast at the same column of the portrait, the lower one
    # landed further round the chest's turn and the pair ran diagonally), each on the cloth's turn under it, a little
    # further towards the viewer
    # (each cast at its own column, where it meets the cloth: the line of sight is level, so its height is the
    # portrait's either way; cast at the leftmost, the lower one's missed the cloth)
    hits = [ref_hit(NO_SASH, c, py)[0] for c, (_, py, _) in zip(cols, STARS)]
    print('stars: the column of the portrait lands at x %.3f, the badge at %.3f' % (
        sum(p.x for p in hits) / len(hits), badge_x))

    def placed(xs, z, r):  # on the cloth's turn under it, a little further towards the viewer, down onto the cloth
        o, _, _, Nc = seat(xs, z, r * 0.8, r * 0.8, NO_SASH, STAR_LIFT)
        N = (Nc - view * STAR_TURN).normalized()
        Y = (Vector((0, 0, 1)) - N * N.z).normalized()
        X = Y.cross(N).normalized()
        return lifted(o - N * 0.03, X, Y, N, r * 0.75, r * 0.75, STAR_LIFT), X, Y, N
    for p, (_, _, r), x in zip(hits, STARS, STAR_X):
        xs = x
        for _ in range(8):  # seated afresh at each try (only lifted after a move, it stood 1.5 cm off the cloth)
            o, X, Y, N = placed(xs, p.z, r)
            if abs(o.x - x) < 0.0003:
                break
            xs -= o.x - x
        star_piece(part, (o, X, Y, N), r, TORSO_W.at(o))
        under = NO_SASH.ray_cast(o + N * 0.05, -N, 0.2)[0]
        print('star at px %d: x %.3f z %.3f, %.4f off the cloth at its middle' % (
            ref_px(o)[0], o.x, o.z, (o - under).dot(N) if under is not None else -1))
    return part.build('Orders')


# ---------------------------------------------------------------- sabre
def clear_path(path, r, rounds=6, out=Vector((0.35, -1.0, 0.0))):
    """Path points brought out from under the skirt, trousers, boots and belt: a ray from each point outwards (out,
    to the front and his left) that meets them means the point is under them - it goes to r + SWORD_CLEAR beyond the
    last surface the ray meets; then smoothed. The first point (at the hilt) stays."""
    out = out.normalized()
    for _ in range(rounds):
        for i in range(1, len(path)):
            p = path[i]
            for _ in range(4):  # through every layer (lining, cloth)
                hit = LOWER.ray_cast(p + out * 1e-4, out, 0.4)
                if hit[0] is None:
                    break
                p = hit[0] + out * (r + SWORD_CLEAR)
            path[i] = p
        path[1:-1] = [path[i] * 0.5 + (path[i - 1] + path[i + 1]) * 0.25 for i in range(1, len(path) - 1)]
    return path


def reg_uv(region, u, v):
    u0, v0, u1, v1 = REG_ATLAS[region]
    pad = 2 / 2048
    return (u0 + pad + (u1 - u0 - 2 * pad) * min(max(u, 0), 1), v0 + pad + (v1 - v0 - 2 * pad) * min(max(v, 0), 1))


def frames(path, ref=None):
    """Per path point: tangent and two normals, parallel transported (no twist)."""
    out, prev = [], None
    for i, p in enumerate(path):
        t = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized()
        if prev is None:
            rr = ref or (Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((0, 1, 0)))
            prev = (rr - t * rr.dot(t)).normalized()
        u = (prev - t * prev.dot(t)).normalized(); prev = u
        out.append((t, u, t.cross(u)))
    return out


def loft(part, rings, face_uv):
    """Quads between consecutive rings (each a list of verts, closed round); face_uv(i, k) -> 4 corner UVs."""
    sides = len(rings[0])
    for i in range(len(rings) - 1):
        for k in range(sides):
            k2 = (k + 1) % sides
            part.face([rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]], face_uv(i, k))


def rope(part, path, r, w, sides=8, region='cord', length=REG_CORD_LEN):
    """A textured cord (Regalia material) along path: its braid along u by the length run, round it along v."""
    fr = frames(path)
    acc = [0.0]
    for a, b in zip(path, path[1:]):
        acc.append(acc[-1] + (b - a).length)
    rings = [[part.vert(p + (u * math.cos(2 * math.pi * k / sides) + v * math.sin(2 * math.pi * k / sides))
                        * (r(i / (len(path) - 1)) if callable(r) else r), w) for k in range(sides)]
             for i, (p, (t, u, v)) in enumerate(zip(path, fr))]

    def uv(i, k):
        return reg_uv(region, acc[i] / length, k / sides)
    loft(part, rings, lambda i, k: [uv(i, k), uv(i, k + 1), uv(i + 1, k + 1), uv(i + 1, k)])
    return rings


def build_sabre():
    """The sabre of the portrait: gilt hilt - a wire-bound grip under the palm, a capped pommel, a slender knuckle bow
    to the cross-guard's front, the guard with a roundel at each end of its bar, shield-shaped langets on the
    scabbard's mouth; black leather scabbard with chased gilt locket, two bands with suspension rings, a long chape."""
    part = Part()
    w = TORSO_W.at(Vector((0.2, 0.0, 1.2)))  # the pelvis and the left hip, like the belt it hangs from
    axis = (GUARD - POMMEL).normalized()
    fwd = BOW_SIDE.normalized(); fwd = (fwd - axis * fwd.dot(axis)).normalized()
    side = axis.cross(fwd).normalized()
    tip = GUARD + AXIS * SCABBARD_L
    n = 60
    path = [GUARD.lerp(tip, i / n) for i in range(n + 1)]
    acc = [0.0]
    for a, b in zip(path, path[1:]):
        acc.append(acc[-1] + (b - a).length)
    length = acc[-1]

    def mount(sv):
        for k, (m0, m1) in enumerate(MOUNTS):
            if m0 <= sv <= min(m1, length):
                return k, (sv - m0) / (min(m1, length) - m0)
        return None, 0.0
    sides = 16
    fr = frames(path, fwd)
    rings = []
    for i, (p, (t, u, v)) in enumerate(zip(path, fr)):
        tq = acc[i] / length
        k_m, _ = mount(acc[i])
        proud = MOUNT_PROUD if k_m is not None else 1.0
        if k_m == len(MOUNTS) - 1:  # the chape narrows to a rounded drag
            proud *= 1 - 0.35 * smoothstep(acc[i], length - 0.05, length)
        ring = []
        for k in range(sides):
            a = 2 * math.pi * k / sides
            rw = SCABBARD_W / 2 * (1 - 0.3 * tq) * proud  # wide front-back (along u, forward), tapering to the tip
            rd = SCABBARD_D / 2 * (1 - 0.2 * tq) * proud
            ring.append(part.vert(p + u * math.cos(a) * rw + v * math.sin(a) * rd, w))
        rings.append(ring)

    def vv(kk):  # round the scabbard, mirrored: no seam where it closes
        return abs(kk / sides * 2 - 1)

    def scab_uv(i, k):
        m0, f0 = mount(acc[i]); m1, f1 = mount(acc[i + 1])
        if m0 is None or m1 is None or m0 != m1:
            return [pal_uv('leather' if m0 is None and m1 is None else 'gold')] * 4
        return [uv_in('ornate', f0, vv(k)), uv_in('ornate', f0, vv(k + 1)), uv_in('ornate', f1, vv(k + 1)),
                uv_in('ornate', f1, vv(k))]
    loft(part, rings, scab_uv)
    cap(part, rings[-1], path[-1] + (path[-1] - path[-2]).normalized() * 0.008, pal_uv('gold'))
    cap(part, list(reversed(rings[0])), path[0], pal_uv('gold'))
    # suspension rings lying flat on the bands' back edge, and the slings from the belt down onto that edge and along
    # it to them, the long one (to the lower ring) over the short one (hung straight from the belt to rings 3 cm off
    # the scabbard, the long one ran down beside it like a loose rod)

    def at(s):
        return min(range(len(acc)), key=lambda j: abs(acc[j] - s))

    def edge(s, off):  # the back edge at s down the scabbard, off out from its (banded) surface
        i = at(s)
        return path[i] - fr[i][1] * (SCABBARD_W / 2 * (1 - 0.3 * acc[i] / length) * MOUNT_PROUD + off)
    ring_s = [(m0 + m1) / 2 for m0, m1 in MOUNTS[1:3]]
    ring_off = 0.0018  # the flat ring's wire (r 1.6 mm) on the surface
    strap_off = (ring_off + 0.0021 + SLING_T / 2, ring_off + 0.0021 + SLING_T * 1.5 + 0.0008)
    top_at = edge(SLING_JOIN, strap_off[1])
    # the belt's lower edge over there (it goes down to his left and to the front: its lowest point on that side is
    # further round, in front)
    belt_lo = min(v.co.z for v in obj('Belt').data.vertices
                  if v.co.x > 0.1 and (v.co.xy - top_at.xy).length < (top_at.xy.length - v.co.xy.length) + 0.03)
    q = Vector((top_at.x, top_at.y, belt_lo - SLING_TOP_Z))
    loc, nrm, _, _ = LOWER.find_nearest(q, 0.3)
    top = loc + nrm * (SLING_T + 0.002) if loc is not None else q
    # the clasp on the belt: a chased gilt plate on its face down to its lower edge, a ring hanging from the plate's
    # foot over the skirt, the slings' tops looped through it
    bl, bn, _, _ = bvh_of([obj('Belt')]).find_nearest(Vector((q.x, q.y, belt_lo + CLASP_H / 2)), 0.3)
    bn = Vector((bn.x, bn.y, 0.0)).normalized()
    bx = Vector((0, 0, 1)).cross(bn).normalized()
    hh = CLASP_H / CLASP_W
    plaque(part, [(-1, -hh), (1, -hh), (1, hh), (-1, hh)],
           (Vector((bl.x, bl.y, belt_lo + CLASP_H / 2 - 0.004)) + bn * 0.0008, bx, Vector((0, 0, 1)), bn),
           CLASP_W / 2, 0.0022, 'ornate', dome=0.001, w=w)
    rw, rh, rr = CLASP_RING
    rc = Vector((bl.x, bl.y, belt_lo - 0.004 - rh * 0.7)) + bn * (rr + 0.0015)
    tube(part, [rc + bx * (rw * math.cos(2 * math.pi * j / 20)) + Vector((0, 0, rh * math.sin(2 * math.pi * j / 20)))
                for j in range(21)], rr, lambda ii, kk: pal_uv('gold'), w, sides=6)
    top = rc - Vector((0, 0, rh)) + bn * (SLING_T / 2 + rr)  # through the ring's foot
    for n_, s_r in enumerate(ring_s):
        i = at(s_r)
        t, u, v = fr[i]
        c = edge(s_r, ring_off)
        loop = [c + (t * math.cos(2 * math.pi * j / 16) + v * math.sin(2 * math.pi * j / 16)) * SLING_RING_R
                for j in range(17)]
        tube(part, loop, 0.0016, lambda ii, kk: pal_uv('gold'), w, sides=6)

        def off(s):  # the long strap stands over the short one down to its ring, then lies on the edge
            return strap_off[0] + (strap_off[1] - strap_off[0]) * n_ * (1 - smoothstep(s, ring_s[0] + 0.03,
                                                                                        ring_s[0] + 0.07))
        down_s = np.linspace(SLING_JOIN, s_r - SLING_RING_R * 0.6, 24)
        down = [edge(s, off(s)) for s in down_s]
        sp = [top.lerp(down[0], j / 10) for j in range(10)] + down
        for _ in range(6):  # the bend onto the edge rounded off
            sp[1:12] = [sp[j] * 0.5 + (sp[j - 1] + sp[j + 1]) * 0.25 for j in range(1, 12)]
        sp[:12] = clear_path(sp[:12], SLING_T + 0.002)  # out over the skirt from under the belt
        sp[:12] = clear_hand(sp[:12], SLING_W / 2 + HAND_CLEAR)  # behind the fist on the hilt, not through it
        # flat on the skirt where it comes out, turning to lie flat on the scabbard's edge (one frame all along, it
        # stood edge-on in the skirt)
        flat0 = nrm.cross(Vector((0, 0, 1))).normalized() if loc is not None else v
        ss = [SLING_JOIN] * 10 + list(down_s)
        rings = []
        for j, p in enumerate(sp):
            tj = (sp[min(j + 1, len(sp) - 1)] - sp[max(j - 1, 0)]).normalized()
            vj = fr[at(ss[j])][2]
            vj = vj if vj.dot(flat0) >= 0 else -vj
            wd = flat0.lerp(vj, smoothstep(j, 2, 11))
            wd = (wd - tj * wd.dot(tj)).normalized()
            th = tj.cross(wd)
            rings.append([part.vert(p + wd * (math.cos(2 * math.pi * k / 8) * SLING_W / 2)
                                    + th * (math.sin(2 * math.pi * k / 8) * SLING_T / 2), w) for k in range(8)])
        loft(part, rings, lambda ii, kk: [pal_uv('leather')] * 4)
    # hilt: the grip, oval, bound with gold wire in a spiral (the 'grip' texture: dark between the turns), swelling a
    # little
    grip_n, gs = 14, 12
    grip = [POMMEL.lerp(GUARD, i / grip_n) for i in range(grip_n + 1)]
    g_rings = []
    for i, p in enumerate(grip):
        swell = 1 + 0.12 * math.sin(math.pi * i / grip_n)
        g_rings.append([part.vert(p + (fwd * math.cos(2 * math.pi * k / gs) * 0.0105
                                       + side * math.sin(2 * math.pi * k / gs) * 0.0088) * swell * HILT_K, w)
                        for k in range(gs)])
    loft(part, g_rings, lambda i, k: [uv_in('grip', kk / gs, ii / grip_n) for ii, kk in
                                       ((i, k), (i, k + 1), (i + 1, k + 1), (i + 1, k))])
    lathe(part, POMMEL, -axis, [(a * HILT_K, r * HILT_K) for a, r in
                                ((-0.004, 0.0105), (0.004, 0.012), (0.011, 0.0115), (0.016, 0.008), (0.019, 0.0))],
          lambda i, k: uv_in('ornate', i / 4, abs(k / 12 * 2 - 1)), w, 12)
    # guard: an oval plate, a bar across it front to back ending in a roundel either end
    lathe(part, GUARD, axis, [(a * HILT_K, r * HILT_K) for a, r in
                              ((-0.004, 0.0), (-0.004, 0.016), (0.003, 0.017), (0.005, 0.013), (0.005, 0.0))],
          lambda i, k: pal_uv('gold'), w, 16, ref=fwd)
    bar = [GUARD - fwd * 0.03 * HILT_K + fwd * (0.066 * HILT_K * j / 6) - axis * 0.001 for j in range(7)]
    tube(part, bar, 0.0042 * HILT_K, lambda i, k: pal_uv('gold'), w, sides=10)
    for end in (bar[0], bar[-1]):
        lathe(part, end - side * 0.0035 * HILT_K, side, [(a * HILT_K, r * HILT_K) for a, r in
                                                       ((0.0, 0.0), (0.0, 0.0085), (0.007, 0.0085), (0.007, 0.0))],
              lambda i, k: uv_in('ornate', 0.5 + 0.5 * math.cos(2 * math.pi * k / 14), 0.5), w, 14, ref=fwd)
    # langets: shield-shaped plates down over the scabbard's mouth either side
    shield = [(-0.6, 1.0), (0.6, 1.0), (0.6, -0.15), (0.0, -1.0), (-0.6, -0.15)]
    for sg in (1, -1):
        o = GUARD + axis * 0.022 + side * sg * (SCABBARD_D / 2 * MOUNT_PROUD + 0.0005)
        plaque(part, shield, (o, fwd, -axis, side * sg), 0.019, 0.0018, 'ornate', w=w)
    # knuckle bow: from the bar's front end up to the pommel, bowed forward
    a0, a1 = bar[-1], POMMEL + fwd * 0.012 * HILT_K + axis * 0.004
    bow = [a0.lerp(a1, j / 16) + fwd * BOW_BULGE * math.sin(math.pi * j / 16) for j in range(17)]
    tube(part, bow, BOW_R, lambda i, k: pal_uv('gold'), w, sides=10)
    sabre = part.build('Sabre')
    # sword knot (its own object, build_dangles.py lets it swing): a braided cord from the bow's foot down along the
    # scabbard to its ball and tassel
    part = Part(bpy.data.materials.get('Regalia'))
    start = bar[-1] + fwd * 0.002 - axis * 0.004
    on_axis = GUARD + AXIS * ((KNOT_BALL_Z - GUARD.z) / AXIS.z)  # the scabbard's middle at the ball's height
    ball = clear_tassel(on_axis + fwd * (SCABBARD_W / 2 * MOUNT_PROUD + TASSEL_R + 0.012), fwd)
    kp = [start.lerp(ball, j / 30) + fwd * 0.015 * math.sin(math.pi * j / 30) for j in range(31)]
    kp = clear_path(kp, KNOT_CORD_R + 0.004)
    for j, p in enumerate(kp):  # in front of the scabbard, not through it
        t = max(0.0, (p - GUARD).dot(AXIS))
        c = GUARD + AXIS * t
        d = p - c
        need = SCABBARD_W / 2 * MOUNT_PROUD + KNOT_CORD_R + 0.002
        if j > 2 and d.length < need:
            d = d if d.length > 1e-6 and d.dot(fwd) > 0 else fwd
            kp[j] = c + d.normalized() * need
    rope(part, kp, KNOT_CORD_R, w)
    tassel(part, kp[-1], w)
    knot = part.build('SwordKnot')
    # the hanger's cord: from under the belt in front of the left hip down to its own tassel, straight, in past the
    # fist on the hilt
    part = Part(bpy.data.materials.get('Regalia'))
    belt = obj('Belt')

    def hanger(x):
        bz = min(v.co.z for v in belt.data.vertices if abs(v.co.x - x) < 0.006 and v.co.y < 0) + BELT_KNOT_TUCK
        top = UNI.ray_cast(Vector((x, -1.0, bz)), Vector((0, 1, 0)), 2.0)[0] + Vector((0, -BELT_KNOT_R, 0))
        ball = clear_tassel(Vector((x + 0.008, top.y - 0.012, BELT_KNOT_BALL_Z)), Vector((0.35, -1.0, 0.0)))
        return clear_path([top.lerp(ball, j / 24) for j in range(25)], BELT_KNOT_R + 0.003)

    def off_hand(path):
        return min((p - loc).dot(nrm) for p in path for loc, nrm, _, _ in [HAND_L.find_nearest(p)]) if HAND_L else 1.0
    x = BELT_KNOT_X
    bp = hanger(x)
    while off_hand(bp) < BELT_KNOT_R + HAND_CLEAR and x > BELT_KNOT_X - 0.04:
        x -= 0.003
        bp = hanger(x)
    top = bp[0]
    bp = clear_hand(bp, BELT_KNOT_R + HAND_CLEAR)
    wb = TORSO_W.at(top)
    rope(part, bp, BELT_KNOT_R, wb)
    tassel(part, bp[-1], wb)
    belt_knot = part.build('BeltKnot')
    print('sword knot ball at z %.2f, belt knot from %s' % (KNOT_BALL_Z, tuple(round(c, 3) for c in top)))
    return sabre, knot, belt_knot


def clear_hand(path, r, rounds=40, away=None):
    """Path points out of the left hand: a point nearer its skin than r (or inside it) goes to r off the nearest
    point, then the path is smoothed; the ends stay. (Straight from the belt to its tassel the hanger's cord ran
    through the fist on the hilt; in the portrait it passes behind the hand.) away: first carried that way, 2 mm a
    step, till clear of the hand (pushed to the nearest skin, a cord between the thumb and the fingers stayed there)."""
    if HAND_L is None:
        return path

    def near(p):
        loc, nrm, _, d = HAND_L.find_nearest(p)
        return loc is not None and (d < r or (p - loc).dot(nrm) < r)
    if away is not None:
        for _ in range(8):
            for i in range(1, len(path) - 1):
                for _ in range(40):
                    if not near(path[i]):
                        break
                    path[i] = path[i] + away * 0.002
            path[1:-1] = [path[i] * 0.5 + (path[i - 1] + path[i + 1]) * 0.25 for i in range(1, len(path) - 1)]
    for _ in range(rounds):
        moved = 0
        for i in range(1, len(path) - 1):
            loc, nrm, _, d = HAND_L.find_nearest(path[i])
            if loc is not None and (path[i] - loc).dot(nrm) < r:
                path[i] = loc + nrm * r
                moved += 1
        if not moved:
            break
        path[1:-1] = [path[i] * 0.5 + (path[i - 1] + path[i + 1]) * 0.25 for i in range(1, len(path) - 1)]
    for i in range(1, len(path) - 1):  # the last smoothing must not take it back in
        loc, nrm, _, d = HAND_L.find_nearest(path[i])
        if loc is not None and (path[i] - loc).dot(nrm) < r:
            path[i] = loc + nrm * r
    offs = [(p - HAND_L.find_nearest(p)[0]).dot(HAND_L.find_nearest(p)[1]) for p in path]
    print('cord past the hand: %.4f off its skin at the nearest (point %d of %d)' % (
        min(offs), offs.index(min(offs)), len(offs)))
    return path


def clear_tassel(top, out):
    """A tassel's top moved along out until the whole tassel under it (its ball, cap and splayed threads) is clear of
    the skirt, trousers, boots and the scabbard."""
    out = Vector((out.x, out.y, 0.0)).normalized()
    ring = [Vector((math.cos(a), math.sin(a), 0.0)) for a in (2 * math.pi * k / 8 for k in range(8))]
    for _ in range(40):
        pts = [top + Vector((0, 0, -dz)) + d * (TASSEL_R + 0.004) for dz in (0.0, 0.03, 0.06, TASSEL_LEN + 0.02)
               for d in ring]
        bad = any(blocked(p, 0.0) for p in pts) or any(
            (p - (GUARD + AXIS * max(0.0, (p - GUARD).dot(AXIS)))).length < SCABBARD_W / 2 * MOUNT_PROUD + 0.003
            for p in pts)
        if not bad:
            break
        top = top + out * 0.004
    return top


def tassel(part, top, w):
    """A knotted ball of braided cord under top, a bell-shaped cap, then a skirt of fine bullion threads round a core
    (Regalia material: the braid and the bullion's coiled wire), splaying a little at the bottom."""
    down = Vector((0, 0, -1))
    rb = TASSEL_R * 0.85
    c = top + down * rb
    lat, lon = 8, 14
    rings = []
    for i in range(1, lat):
        th = math.pi * i / lat
        rings.append([part.vert(c + Vector((math.sin(th) * math.cos(2 * math.pi * k / lon) * rb,
                                            math.sin(th) * math.sin(2 * math.pi * k / lon) * rb,
                                            math.cos(th) * rb)), w) for k in range(lon)])

    def uvb(i, k):
        return reg_uv('cord', 0.1 + i * 0.012, k / lon)
    loft(part, rings, lambda i, k: [uvb(i, k), uvb(i, k + 1), uvb(i + 1, k + 1), uvb(i + 1, k)])
    for ring, pole in ((rings[0], c + Vector((0, 0, rb))), (list(reversed(rings[-1])), c - Vector((0, 0, rb)))):
        cv = part.vert(pole, w)
        for k in range(lon):
            part.face([ring[k], ring[(k + 1) % lon], cv], [uvb(0, k), uvb(0, k + 1), uvb(0, k)])
    # the cap (a bell over the threads' heads) and the core under it
    c2 = c + down * rb * 0.8
    prof = [(0.0, 0.004), (0.004, 0.0075), (0.011, 0.0112), (0.016, TASSEL_R), (0.019, TASSEL_R * 0.9),
            (TASSEL_LEN * 0.9, TASSEL_R * 0.8), (TASSEL_LEN * 0.92, 0.0)]
    lathe(part, c2, down, prof, lambda i, k: reg_uv('cord', 0.3 + i * 0.02, abs(k / 16 * 2 - 1)), w, 16)
    # the skirt: TASSEL_STRANDS threads in two rings from under the cap, splaying out
    for j in range(TASSEL_STRANDS):
        outer = j % 3 != 0
        a = 2 * math.pi * (j + 0.37 * (j % 3)) / TASSEL_STRANDS
        d = Vector((math.cos(a), math.sin(a), 0))
        r0 = TASSEL_R * (0.92 if outer else 0.6)
        L = TASSEL_LEN * (0.93 + 0.07 * math.sin(j * 2.3))
        p0 = c2 + down * 0.016 + d * r0
        path = [p0 + down * (L * q / 6) + d * (0.006 * (q / 6) ** 2) for q in range(7)]
        rope(part, path, 0.0017, w, sides=5, region='bullion', length=REG_BULLION_LEN)


if PLACE_ONLY:
    old = bpy.data.objects['Orders']
    new = build_orders()
    if len(new.data.vertices) != len(old.data.vertices):
        sys.exit('build_orders.py -- orders: %d vertices against the leader has %d - rebuild (build_all.py --from orders)'
                 % (len(new.data.vertices), len(old.data.vertices)))
    co = np.zeros(len(new.data.vertices) * 3, np.float32)
    new.data.vertices.foreach_get('co', co)
    was = np.zeros_like(co)
    old.data.vertices.foreach_get('co', was)
    moved = np.linalg.norm((co - was).reshape(-1, 3), axis=1)
    old.data.vertices.foreach_set('co', co)
    old.data.update()
    bpy.data.objects.remove(new)
    print('orders placed afresh: %d vertices moved, up to %.1f mm' % ((moved > 1e-5).sum(), moved.max() * 1000))
    rig.data.pose_position = POSE_POSITION
else:
    orders = build_orders()
    sabre, knot, belt_knot = build_sabre()
bpy.ops.outliner.orphans_purge(do_recursive=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
print('saved', OUT, os.path.getsize(OUT))

# Orders, medals and the sabre, as in art/source/alexander_ii_short.png and alexander_ii_full.png, on the posed uniform.
# blender -b art/3d/alexander_leader.blend --python art/3d/build_orders.py   (after build_regalia.py; rewrites in place)
# - a white enamel Maltese cross with silver rays and a crown, hanging from the foot of the collar's opening;
# - a bar of seven ribbons folded into pentagons on the left breast, the medals hanging from their points (the white St
#   George cross first), a small enamel badge, two silver eight-pointed order stars one above the other;
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
    'steel': ((120, 122, 128), 1.0, 0.3), 'dark_gold': ((150, 95, 38), 1.0, 0.45),
}
# the palette's cells are big (128 px): small ones bleed into the ribbons in the mipmaps
ATLAS = {'pal': (0.0, 0.0, 1.0, 0.125), 'ribbons': (0.0, 0.125, 0.5, 0.25), 'ornate': (0.5, 0.125, 1.0, 0.25),
         'star': (0.0, 0.25, 0.5, 0.75),
         'cross': (0.5, 0.25, 1.0, 0.75), 'medal': (0.0, 0.75, 0.25, 1.0), 'wcross': (0.25, 0.75, 0.5, 1.0),
         'smedal': (0.5, 0.75, 0.75, 1.0), 'badge': (0.75, 0.75, 1.0, 1.0)}
# Ribbons left to right (stripes as (colour, share)): St George, St Alexander Nevsky, St Andrew, St Vladimir, St Anna,
# the Crimean war medal.
RIBBON_SRGB = {'O': (232, 118, 18), 'K': (18, 18, 20), 'R': (176, 22, 30), 'B': (60, 110, 200), 'Y': (230, 190, 40),
               'L': (120, 170, 225)}
RIBBONS = [[('O', 1), ('K', 1), ('O', 1), ('K', 1), ('O', 1)], [('R', 1)], [('B', 1)], [('K', 1), ('R', 1), ('K', 1)],
           [('Y', 0.15), ('R', 0.7), ('Y', 0.15)], [('L', 1)], [('K', 1), ('O', 1), ('K', 1)]]
MEDALS = ['wcross', 'medal', 'medal', 'smedal', 'smedal', 'medal', 'smedal']
# Measured on alexander_ii_full.png (1 px ~ 1.4 mm of the model): the bar ~105 mm wide, its ribbons ~50 mm long, the
# medals ~28 mm across, the St George cross ~40 mm; the neck cross ~62 mm; the stars ~80 mm across.
# Imperial Russian orders and medals were worn in full, the lower classes' ribbons folded into pentagons on the bar
# (medals.pl, 'Russia': no service ribbons; pentagonal folds) - the portrait's bar: seven of them side by side, each a
# little behind the one before, the medals hanging from their points and overlapping the same way.
BAR_X, BAR_Z, RIB_STEP = 0.05, 1.69, 0.0152  # left end of the bar (just right of the closure's piping), its top;
                                             # from one ribbon to the next
PENT_W, PENT_H, PENT_SHOULDER = 0.022, 0.046, -0.3  # a folded ribbon: width, height, where its sides turn to the point
MEDAL_R, WCROSS_S = 0.015, 0.021
NECK_CROSS_S = 0.031                 # half-size of the neck cross; it hangs from its crown at the collar's opening
NECK_CROSS_RAYS = 0.8                # the silver rays between its arms reach this far (of the half-size)
BADGE = (0.128, 1.582, 0.012, 0.017)  # x, z, half-width, half-height of the gold badge under the bar
STARS = [(0.15, 1.555, 0.045), (0.15, 1.475, 0.045)]  # x, z, radius; one above the other, as in the portrait - both
                                     # moved out past the sash's edge as far as the one that needs it most
STAR_OVER_SASH = 0.45                # how much of a star's radius may lie over the sash's edge
LIFT = 0.003
# Sabre: pommel under the left palm, the blade hanging down and a little back along the left hip and leg.
POMMEL = Vector((0.24, -0.15, 1.125))   # where the left palm is not found (no rig): fallback
GRIP_L = 0.105                      # pommel to guard
GRIP_IN_PALM = 0.022                # the pommel this far from the hand's axis towards the palm (the fingers close round)
SCABBARD_L, SCABBARD_W, SCABBARD_D = 0.86, 0.048, 0.028
SWORD_CLEAR = 0.012                 # off the skirt, trousers and boot
SWORD_DROP = Vector((0.035, 0.03, -1.0))  # the scabbard hangs nearly straight down, a little out and back
# Its gilt mounts (s along the scabbard from the throat, m): the long locket, two bands carrying the suspension rings,
# the long chape at the tip - chased (the 'ornate' region), standing a little proud of the black leather.
MOUNTS = [(0.0, 0.10), (0.25, 0.285), (0.50, 0.535), (SCABBARD_L - 0.17, SCABBARD_L + 0.05)]
MOUNT_PROUD = 1.08
# Sword knot (temlyak) and the hanger's cord from the belt (both in the portrait): braided gold cord to a knotted ball
# and a tassel of fine bullion (the Regalia material: build_regalia.py's braid and bullion). Heights of the balls.
KNOT_BALL_Z, KNOT_CORD_R = 0.70, 0.0042
BELT_KNOT_X, BELT_KNOT_BALL_Z, BELT_KNOT_R = 0.13, 0.97, 0.0048
TASSEL_LEN, TASSEL_R, TASSEL_STRANDS = 0.07, 0.0125, 40
# build_regalia.py's atlas (TEX 2048) and its texture lengths: the cords' braid and the fringe's bullion
REG_ATLAS = {'cord': (0.0, 0.125, 1.0, 0.1875), 'bullion': (0.0, 0.1875, 1.0, 0.25)}
REG_CORD_LEN, REG_BULLION_LEN = 0.6, 0.147
ORNATE_TILES = (16, 2)              # the ornament's scrolls across / along its region

sc = bpy.context.scene
rig = bpy.data.objects['HumanRig']


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
for o in list(bpy.data.objects):
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
    # in the portrait the scabbard runs straight down the picture: across the leader camera's view as little as can be
    yaw = math.radians(90 + float(sc.get('pose', {}).get('YAW_DEG', 0.0)))
    view = Vector((-math.cos(yaw), math.sin(yaw), 0.0))  # from the camera towards the figure, in model space
    across = view.cross(Vector((0, 0, 1))).normalized()
    best = None
    for dx in np.linspace(-0.1, 0.45, 12):
        for dy in np.linspace(-0.32, 0.16, 13):  # held in front of the thigh: the tip a little forward
            d = Vector((float(dx), float(dy), -1.0)).normalized()
            g = POMMEL + d * GRIP_L
            hits = sum(blocked(g + d * (SCABBARD_L * i / 30), SCABBARD_W / 2) for i in range(4, 31))  # the throat
            # may touch the skirt: the hand holds the hilt against the hip
            cost = hits * 10 + 3 * abs(d.dot(across)) + abs(d.y) + (d - base).length
            if best is None or cost < best[0]:
                best = (cost, d, hits)
    print('sword: axis %s, %d points still in the cloth' % (tuple(round(c, 3) for c in best[1]), best[2]))
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

    # star: silver rays with fine grooves, a gold ring round a red enamel centre with a small gold cross
    r, th, x, y = polar('star')
    c = np.tile(srgb(PALETTE['silver'][0]), r.shape + (1,))
    groove = 0.5 + 0.5 * np.cos(th * 128)  # the rays are cut in fine facets (brilliants), each catching the light
    c = c * (0.7 + 0.3 * groove)[..., None]
    m = np.full_like(r, PALETTE['silver'][1]); ro = 0.2 + 0.15 * (1 - groove); hg = groove * 0.3
    ring = (r > 0.30) & (r < 0.38)
    centre = r <= 0.30
    c[ring] = srgb(PALETTE['gold'][0]); hg = np.where(ring, 0.8, hg)
    c[centre] = srgb(PALETTE['red'][0]); m = np.where(centre, 0.0, m); ro = np.where(centre, 0.12, ro)
    hg = np.where(centre, 0.6, hg)
    small = centre & (((np.abs(x) < 0.05) & (np.abs(y) < 0.2)) | ((np.abs(y) < 0.05) & (np.abs(x) < 0.2)))
    c[small] = srgb(PALETTE['gold'][0]); m = np.where(small, 1.0, m); hg = np.where(small, 0.9, hg)
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
        med = r < 0.26
        c[med] = srgb(PALETTE['gold'][0]); m[med] = 1.0; ro[med] = 0.3; hg[med] = 0.9
        dot = r < 0.17
        c[dot] = srgb(PALETTE['red'][0] if fill == 'blue' else PALETTE['red'][0]); m[dot] = 0.0; ro[dot] = 0.12
        put(region, c, m, ro, hg)

    enamel_cross('wcross', 'white')

    # the neck cross: Maltese (eight points), white enamel arms edged in gold with a blue line inside, a blue medallion
    r, th, x, y = polar('cross')
    inside = in_poly(x, y, MALTESE)
    inner = erode(inside, 6); line = erode(inside, 10) & ~erode(inside, 14)
    c = np.tile(srgb(PALETTE['gold'][0]), r.shape + (1,)); m = np.ones_like(r); ro = np.full_like(r, 0.3)
    hg = np.where(inside, 0.5, 0.0)
    c[inner] = srgb(PALETTE['white'][0]); m[inner] = 0.0; ro[inner] = 0.12; hg[inner] = 0.75
    c[line] = srgb(PALETTE['blue'][0])
    for rr, col, met, h in ((0.27, 'gold', 1.0, 0.85), (0.23, 'white', 0.0, 0.9), (0.19, 'blue', 0.0, 0.95),
                            (0.06, 'gold', 1.0, 1.0)):
        d = r < rr
        c[d] = srgb(PALETTE[col][0]); m[d] = met; ro[d] = 0.12 if not met else 0.3; hg[d] = h
    put('cross', c, m, ro, hg)

    # the badge under the bar: a gold oval with a raised rim and an enamelled red centre
    r, th, x, y = polar('badge')
    e = np.hypot(x, y * 13 / 19)
    rim = e > 0.82
    relief = np.where(rim, 1.0, 0.45 + 0.25 * np.cos(th * 12) * (e > 0.45))
    c = srgb(PALETTE['gold'][0]) * (0.75 + 0.25 * relief)[..., None]
    m = np.ones_like(r); ro = np.full_like(r, 0.28)
    cen = e < 0.4
    c[cen] = srgb(PALETTE['red'][0]); m[cen] = 0.0; ro[cen] = 0.12
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
    centre = part.vert(P(0, 0, radius * 0.2), w)
    ring = []
    for k in range(32):
        a = math.pi / 2 + 2 * math.pi * k / 32
        rr, hh = ((1.0, 0.003) if k % 4 == 0 else (0.78, 0.003) if k % 4 == 2 else (0.5, 0.006))
        ring.append((math.cos(a) * rr, math.sin(a) * rr, hh))
    # a ridge line half way out on each ray: the facets fold along it
    mid = []
    for k in range(32):
        x, y, _ = ring[k]
        mid.append((x * 0.55, y * 0.55, radius * (0.12 if k % 2 == 0 else 0.08)))
    rv = [part.vert(P(x, y, h), w) for x, y, h in ring]
    mv = [part.vert(P(x, y, h), w) for x, y, h in mid]
    uv = lambda q: uv_in('star', q[0] * 0.5 + 0.5, q[1] * 0.5 + 0.5)  # noqa: E731
    for k in range(32):
        k2 = (k + 1) % 32
        part.face([centre, mv[k], mv[k2]], [uv((0, 0)), uv(mid[k]), uv(mid[k2])], smooth=False)
        part.face([mv[k], rv[k], rv[k2], mv[k2]], [uv(mid[k]), uv(ring[k]), uv(ring[k2]), uv(mid[k2])], smooth=False)
    # the enamel centre: a low dome over the ridges
    medal = []
    cen = part.vert(P(0, 0, radius * 0.26), w)
    for k in range(24):
        a = 2 * math.pi * k / 24
        medal.append(part.vert(P(math.cos(a) * 0.38, math.sin(a) * 0.38, radius * 0.18), w))
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


def sash_edge(z, r):
    """The sash's outer edge (largest x) on the front of his left breast between z - r and z + r, or None."""
    sash = obj('Sash')
    if sash is None:
        return None
    xs = [v.co.x for v in sash.data.vertices if abs(v.co.z - z) < r and v.co.y < -0.05 and v.co.x > 0]
    return max(xs) if xs else None


def rays(n_arms=4, width=0.16, inner=0.22, outer=NECK_CROSS_RAYS, off=math.pi / 4):
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
    # neck cross: hung from its crown right at the bottom of the collar's opening (as in the portrait - no ribbon
    # shows): white enamel Maltese cross edged in gold with a blue line, silver rays between the arms, a blue medallion
    s = NECK_CROSS_S
    col = obj('Collar')
    me = col.data
    front = min(v.co.y for v in me.vertices)
    edge = [v.co for v in me.vertices if v.co.y < front + 0.012]
    x = sum(p.x for p in edge) / len(edge)
    z_open = min(v.co.z for v in me.vertices if abs(v.co.x - x) < 0.025 and v.co.y < front + 0.03)
    crown_h = 0.016
    z = z_open - crown_h * 0.6 - s * 1.02  # the crown's top at the opening's foot
    # it lies on the chest along the cloth between its lower and upper arm (the chest curves back up under the collar:
    # laid along the tangent at its centre the upper arm and the crown sank into the cloth); the crown above it plumb
    def cloth_at(zz):
        hit = NO_SASH.ray_cast(Vector((x, -1.0, zz)), Vector((0, 1, 0)), 2.0)[0]  # the cloth (the sash runs by)
        return hit if hit is not None else Vector((x, -0.12, zz))
    lo, hi = cloth_at(z - s), cloth_at(z + s)
    Y = (hi - lo).normalized()
    X = Vector((1, 0, 0))
    N = Y.cross(X).normalized()
    if N.y > 0:
        N = -N
    X = N.cross(Y).normalized()
    if X.x < 0:
        X = -X
    o = (lo + hi) / 2 + N * 0.0015
    print('neck cross at x %.3f z %.3f y %.3f (collar opening z %.3f)' % (x, z, o.y, z_open))
    w = TORSO_W.at(o)
    plaque(part, rays(), (o + N * (LIFT + 0.0005), X, Y, N), s, 0.0015, 'star', w=w, flat=True)
    plaque(part, MALTESE, (o + N * (LIFT + 0.0015), X, Y, N), s, 0.003, 'cross', dome=0.003, w=w)
    crown = o + N * (LIFT + 0.004) + Y * (s * 1.0)
    # the crown: a band, arches swelling to an orb on top (a turned piece seen face on)
    lathe(part, crown, Vector((0, 0, 1)), [(0.0, 0.0), (0.0, 0.0055), (0.003, 0.0065), (0.006, 0.0058),
                                           (0.0095, 0.0068), (0.0125, 0.0045), (0.0135, 0.002), (0.0145, 0.0026),
                                           (0.016, 0.0)],
          lambda i, k: pal_uv('gold'), w, 12)
    # ribbon bar: folded pentagons side by side, each a little behind the one before; the medals from their points
    n = len(RIBBONS)
    pent = [(-1, 1), (1, 1), (1, PENT_SHOULDER), (0, -1), (-1, PENT_SHOULDER)]
    for k in range(n):
        cx = BAR_X + PENT_W / 2 + RIB_STEP * k
        o, X, Y, N = chest_frame(cx, BAR_Z - PENT_H / 2)
        w = TORSO_W.at(o)
        u0 = k / n
        top = plaque(part, pent, (o + N * (LIFT + 0.0011 * (n - k)), X * (PENT_W / PENT_H), Y, N), PENT_H / 2, 0.0015,
                     'ribbons', w=w)
        for v, (px_, py_) in zip(top, pent):  # the ribbon's own stripes: its share of the region
            for l in v.link_loops:
                l[part.uv].uv = uv_in('ribbons', u0 + (px_ * 0.5 + 0.5) / n, py_ * 0.5 + 0.5)
        kind = MEDALS[k]
        size = WCROSS_S if kind == 'wcross' else MEDAL_R
        mo, mX, mY, mN = chest_frame(cx, BAR_Z - PENT_H - size * 0.85)
        outline = CROSS_OUTLINE if kind == 'wcross' else DISC
        plaque(part, outline, (mo + mN * (LIFT + 0.003 + 0.0012 * (n - k)), mX, mY, mN), size, 0.0025, kind,
               dome=0.002, w=w)
    # the gold badge under the bar, a small crown over it
    x, z, bw, bh = BADGE
    o, X, Y, N = chest_frame(x, z)
    w = TORSO_W.at(o)
    plaque(part, [(math.cos(a) * 1.0, math.sin(a) * 1.0) for a in (2 * math.pi * k / 24 for k in range(24))],
           (o + N * LIFT, X * (bw / bh), Y, N), bh, 0.003, 'badge', dome=0.003, w=w)
    lathe(part, o + N * (LIFT + 0.003) + Y * (bh * 1.1), N, [(0.0, 0.0), (0.0, 0.006), (0.004, 0.007), (0.008, 0.0)],
          lambda i, k: pal_uv('gold'), w, 10)
    # stars: on the cloth beside the sash, not on it; one above the other
    x_all = max(max(x, (sash_edge(z, r * 0.8) or -1) + r * (1 - STAR_OVER_SASH)) for x, z, r in STARS)
    for _, z, r in STARS:
        o, X, Y, N = chest_frame(x_all, z, NO_SASH)
        o2 = chest_frame(x_all, z)[0]  # over the sash's edge if it reaches under the star
        lift = max(LIFT, (o2 - o).dot(N) + 0.002)
        star_piece(part, (o + N * lift, X, Y, N), r, TORSO_W.at(o))
        print('star at x %.3f z %.3f' % (x_all, z))
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
    fwd = Vector((0, -1, 0)); fwd = (fwd - axis * fwd.dot(axis)).normalized()
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
    # suspension rings on the bands, at the back edge
    for m0, m1 in MOUNTS[1:3]:
        i = min(range(len(acc)), key=lambda j: abs(acc[j] - (m0 + m1) / 2))
        t, u, v = fr[i]
        c = path[i] - u * (SCABBARD_W / 2 * MOUNT_PROUD + 0.006)
        loop = [c + (u * math.cos(2 * math.pi * j / 16) + t * math.sin(2 * math.pi * j / 16)) * 0.008
                for j in range(17)]
        tube(part, loop, 0.0017, lambda ii, kk: pal_uv('gold'), w, sides=6)
    # hilt: the grip, oval, bound with gold wire in a spiral (dark between the turns), swelling a little
    grip_n, gs = 14, 12
    grip = [POMMEL.lerp(GUARD, i / grip_n) for i in range(grip_n + 1)]
    g_rings = []
    for i, p in enumerate(grip):
        swell = 1 + 0.12 * math.sin(math.pi * i / grip_n)
        g_rings.append([part.vert(p + (fwd * math.cos(2 * math.pi * k / gs) * 0.0105
                                       + side * math.sin(2 * math.pi * k / gs) * 0.0088) * swell, w)
                        for k in range(gs)])
    loft(part, g_rings, lambda i, k: [pal_uv('gold' if (k - i) % 3 else 'dark_gold')] * 4)
    lathe(part, POMMEL, -axis, [(-0.004, 0.0105), (0.004, 0.012), (0.011, 0.0115), (0.016, 0.008), (0.019, 0.0)],
          lambda i, k: uv_in('ornate', i / 4, abs(k / 12 * 2 - 1)), w, 12)
    # guard: an oval plate, a bar across it front to back ending in a roundel either end
    lathe(part, GUARD, axis, [(-0.004, 0.0), (-0.004, 0.016), (0.003, 0.017), (0.005, 0.013), (0.005, 0.0)],
          lambda i, k: pal_uv('gold'), w, 16, ref=fwd)
    bar = [GUARD - fwd * 0.03 + fwd * (0.066 * j / 6) - axis * 0.001 for j in range(7)]
    tube(part, bar, 0.0042, lambda i, k: pal_uv('gold'), w, sides=10)
    for end in (bar[0], bar[-1]):
        lathe(part, end - side * 0.0035, side, [(0.0, 0.0), (0.0, 0.0085), (0.007, 0.0085), (0.007, 0.0)],
              lambda i, k: uv_in('ornate', 0.5 + 0.5 * math.cos(2 * math.pi * k / 14), 0.5), w, 14, ref=fwd)
    # langets: shield-shaped plates down over the scabbard's mouth either side
    shield = [(-0.6, 1.0), (0.6, 1.0), (0.6, -0.15), (0.0, -1.0), (-0.6, -0.15)]
    for sg in (1, -1):
        o = GUARD + axis * 0.022 + side * sg * (SCABBARD_D / 2 * MOUNT_PROUD + 0.0005)
        plaque(part, shield, (o, fwd, -axis, side * sg), 0.019, 0.0018, 'ornate', w=w)
    # knuckle bow: from the bar's front end up to the pommel, bowed forward
    a0, a1 = bar[-1], POMMEL + fwd * 0.012 + axis * 0.004
    bow = [a0.lerp(a1, j / 16) + fwd * 0.012 * math.sin(math.pi * j / 16) for j in range(17)]
    tube(part, bow, 0.0026, lambda i, k: pal_uv('gold'), w, sides=8)
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
    # the hanger's cord: from under the belt in front of the left hip down to its own tassel
    part = Part(bpy.data.materials.get('Regalia'))
    belt = obj('Belt')
    bz = min(v.co.z for v in belt.data.vertices if abs(v.co.x - BELT_KNOT_X) < 0.02 and v.co.y < 0) + 0.006
    top = LOWER.ray_cast(Vector((BELT_KNOT_X, -1.0, bz)), Vector((0, 1, 0)), 2.0)[0] + Vector((0, -BELT_KNOT_R, 0))
    ball = clear_tassel(Vector((BELT_KNOT_X + 0.008, top.y - 0.012, BELT_KNOT_BALL_Z)), Vector((0.35, -1.0, 0.0)))
    bp = clear_path([top.lerp(ball, j / 24) for j in range(25)], BELT_KNOT_R + 0.003)
    wb = TORSO_W.at(top)
    rope(part, bp, BELT_KNOT_R, wb)
    tassel(part, bp[-1], wb)
    belt_knot = part.build('BeltKnot')
    print('sword knot ball at z %.2f, belt knot from %s' % (KNOT_BALL_Z, tuple(round(c, 3) for c in top)))
    return sabre, knot, belt_knot


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


orders = build_orders()
sabre, knot, belt_knot = build_sabre()
bpy.ops.outliner.orphans_purge(do_recursive=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
print('saved', OUT, os.path.getsize(OUT))

# Orders, medals and the sabre, as in art/source/alexander_ii_short.png and alexander_ii_full.png, on the posed uniform.
# blender -b art/3d/alexander_leader.blend --python art/3d/build_orders.py   (after build_regalia.py; rewrites in place)
# - a blue enamel cross with a crown hanging under the collar's opening;
# - a bar of six order ribbons on the left breast with the medals under it (the white St George cross first), a small
#   enamel badge, two silver eight-pointed order stars under them;
# - the sabre on the left hip under his hand: gilt hilt with a knuckle bow, black scabbard with gilt mounts, a gold
#   sword knot with a tassel. The scabbard is pushed off the skirt, trousers and boot so nothing runs through them.
# Own material 'Orders' and atlas textures/orders_{albedo,mr,normal}.png: a palette row of flat colours, the ribbons,
# drawn faces of the star, the cross and the medals (planar UVs). Every piece rides rigidly on the bone weights of the
# cloth under it (the sabre on the pelvis).
import bpy, bmesh, math, os
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
from mathutils.geometry import tessellate_polygon

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'alexander_leader.blend')
TEXDIR = os.path.join(HERE, 'textures')
TEX = 1024
# palette: name -> (sRGB, metal, roughness)
PALETTE = {
    'gold': ((214, 162, 70), 1.0, 0.3), 'silver': ((205, 205, 212), 1.0, 0.25), 'red': ((165, 18, 24), 0.0, 0.15),
    'blue': ((38, 82, 172), 0.0, 0.15), 'white': ((236, 234, 228), 0.0, 0.2), 'leather': ((14, 14, 16), 0.0, 0.35),
    'steel': ((120, 122, 128), 1.0, 0.3), 'dark_gold': ((150, 105, 40), 1.0, 0.45),
}
# the palette's cells are big (128 px): small ones bleed into the ribbons in the mipmaps
ATLAS = {'pal': (0.0, 0.0, 1.0, 0.125), 'ribbons': (0.0, 0.125, 1.0, 0.25), 'star': (0.0, 0.25, 0.5, 0.75),
         'cross': (0.5, 0.25, 1.0, 0.75), 'medal': (0.0, 0.75, 0.25, 1.0), 'wcross': (0.25, 0.75, 0.5, 1.0),
         'smedal': (0.5, 0.75, 0.75, 1.0)}
# Ribbons left to right (stripes as (colour, share)): St George, St Alexander Nevsky, St Andrew, St Vladimir, St Anna,
# the Crimean war medal.
RIBBON_SRGB = {'O': (232, 118, 18), 'K': (18, 18, 20), 'R': (176, 22, 30), 'B': (60, 110, 200), 'Y': (230, 190, 40)}
RIBBONS = [[('O', 1), ('K', 1), ('O', 1), ('K', 1), ('O', 1)], [('R', 1)], [('B', 1)], [('K', 1), ('R', 1), ('K', 1)],
           [('Y', 0.15), ('R', 0.7), ('Y', 0.15)], [('K', 1), ('O', 1), ('K', 1)]]
MEDALS = ['wcross', 'medal', 'medal', 'smedal', 'smedal', 'medal']
BAR_X, BAR_Z, RIB_W, RIB_H = 0.075, 1.655, 0.019, 0.032  # left end of the bar (his left breast), its top; one ribbon
MEDAL_R = 0.0115
NECK_CROSS = (0.030, 1.695, 0.024)   # x, z of its centre, half-size
BADGE = (0.172, 1.575, 0.012)
STARS = [(0.155, 1.515, 0.036), (0.16, 1.425, 0.036)]  # x, z, radius
LIFT = 0.003
# Sabre: pommel under the left palm, the blade hanging down and a little back along the left hip and leg.
POMMEL = Vector((0.222, -0.15, 1.095))
GUARD = Vector((0.222, -0.118, 0.99))
SCABBARD_L, SCABBARD_W, SCABBARD_D = 0.86, 0.04, 0.024
SWORD_CLEAR = 0.012                 # off the skirt, trousers and boot
SWORD_DROP = Vector((0.035, 0.03, -1.0))  # the scabbard hangs nearly straight down, a little out and back
KNOT_TASSEL = Vector((0.205, -0.15, 0.86))
TASSEL_K = 1.8                      # the tassel's size (the portrait's is as long as a hand)

sc = bpy.context.scene
rig = bpy.data.objects['HumanRig']
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


# ---------------------------------------------------------------- atlas
def grid(w, hh):
    return np.meshgrid(np.linspace(0, 1, w), np.linspace(0, 1, hh))


def srgb(c):
    return np.array(c, np.float32) / 255


def blur1(a):
    return (a + np.roll(a, 1, 0) + np.roll(a, -1, 0) + np.roll(a, 1, 1) + np.roll(a, -1, 1)) / 5


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
    groove = 0.5 + 0.5 * np.cos(th * 90)
    c = c * (0.8 + 0.2 * groove)[..., None]
    m = np.ones_like(r); ro = 0.2 + 0.15 * (1 - groove); hg = groove * 0.3
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

    enamel_cross('cross', 'blue')
    enamel_cross('wcross', 'white')

    def medal(region, metal_name):
        r, th, x, y = polar(region)
        base = srgb(PALETTE[metal_name][0])
        rim = (r > 0.85)
        relief = np.where(rim, 1.0, 0.4 + 0.3 * np.exp(-((r - 0.45) / 0.18) ** 2) + 0.15 * (r < 0.25))
        c = base * (0.7 + 0.3 * relief)[..., None]
        put(region, c, 1.0, 0.3 - 0.1 * relief, relief)

    medal('medal', 'gold')
    medal('smedal', 'silver')
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
        img.filepath_raw = path; img.file_format = 'PNG'; img.save()
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

    def __init__(self):
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
        me.materials.append(MAT)
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
    """Eight-pointed order star: each ray a ridge, faceted (flat shaded) so the silver catches the light by facets."""
    o, X, Y, N = frame
    P = lambda x, y, h: o + X * (x * radius) + Y * (y * radius) + N * h  # noqa: E731
    centre = part.vert(P(0, 0, radius * 0.22), w)
    ring = []
    for k in range(16):
        a = math.pi / 2 + 2 * math.pi * k / 16
        rr = 1.0 if k % 2 == 0 else 0.45
        ring.append((math.cos(a) * rr, math.sin(a) * rr, 0.004 if k % 2 == 0 else 0.008))
    rv = [part.vert(P(x, y, h), w) for x, y, h in ring]
    uvc = uv_in('star', 0.5, 0.5)
    for k in range(16):
        a, b = k, (k + 1) % 16
        part.face([centre, rv[a], rv[b]], [uvc, uv_in('star', ring[a][0] * 0.5 + 0.5, ring[a][1] * 0.5 + 0.5),
                                           uv_in('star', ring[b][0] * 0.5 + 0.5, ring[b][1] * 0.5 + 0.5)], smooth=False)
    # the enamel centre: a low dome over the ridges
    medal = []
    cen = part.vert(P(0, 0, radius * 0.27), w)
    for k in range(20):
        a = 2 * math.pi * k / 20
        medal.append(part.vert(P(math.cos(a) * 0.38, math.sin(a) * 0.38, radius * 0.2), w))
    for k in range(20):
        a1, a2 = 2 * math.pi * k / 20, 2 * math.pi * (k + 1) / 20
        part.face([cen, medal[k], medal[(k + 1) % 20]],
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


def build_orders():
    part = Part()
    # neck cross: on a short ribbon from the collar, a gold crown over it
    x, z, s = NECK_CROSS
    o, X, Y, N = chest_frame(x, z)
    w = TORSO_W.at(o)
    plaque(part, CROSS_OUTLINE, (o + N * LIFT, X, Y, N), s, 0.003, 'cross', dome=0.002, w=w)
    crown = o + N * (LIFT + 0.004) + Y * (s * 1.25)
    lathe(part, crown, N, [(0.0, 0.0), (0.0, 0.007), (0.004, 0.008), (0.008, 0.005), (0.010, 0.0)],
          lambda i, k: pal_uv('gold'), w, 10)
    rib_top = chest_frame(x, z + s * 2.6)
    plaque(part, [(-0.4, -1), (0.4, -1), (0.4, 1), (-0.4, 1)], (rib_top[0] + rib_top[3] * LIFT * 0.5, *rib_top[1:]),
           s * 0.5, 0.0015, 'ribbons', w=w)
    # ribbon bar, the medals hanging from it
    n = len(RIBBONS)
    for k in range(n):
        cx = BAR_X + RIB_W * (k + 0.5)
        o, X, Y, N = chest_frame(cx, BAR_Z - RIB_H / 2)
        w = TORSO_W.at(o)
        u0 = k / n
        pts = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
        top = plaque(part, pts, (o + N * LIFT, X * (RIB_W / 2) / (RIB_H / 2), Y, N), RIB_H / 2, 0.003, 'ribbons', w=w)
        for v, (px_, py_) in zip(top, pts):  # the ribbon's own stripes: its share of the region
            for l in v.link_loops:
                l[part.uv].uv = uv_in('ribbons', u0 + (px_ * 0.5 + 0.5) / n, py_ * 0.5 + 0.5)
        mo, mX, mY, mN = chest_frame(cx, BAR_Z - RIB_H - MEDAL_R * 1.15)
        kind = MEDALS[k]
        outline = CROSS_OUTLINE if kind == 'wcross' else DISC
        plaque(part, outline, (mo + mN * (LIFT + 0.002), mX, mY, mN), MEDAL_R * (1.05 if kind == 'wcross' else 1.0),
               0.0025, kind, dome=0.0015, w=w)
    # small badge
    x, z, s = BADGE
    o, X, Y, N = chest_frame(x, z)
    plaque(part, CROSS_OUTLINE, (o + N * LIFT, X, Y, N), s, 0.003, 'cross', dome=0.002, w=TORSO_W.at(o))
    # stars
    for x, z, r in STARS:
        o, X, Y, N = chest_frame(x, z)
        star_piece(part, (o + N * LIFT, X, Y, N), r, TORSO_W.at(o))
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


def build_sabre():
    part = Part()
    w = TORSO_W.at(Vector((0.2, 0.0, 1.2)))  # the pelvis and the left hip, like the belt it hangs from
    axis = (GUARD - POMMEL).normalized()
    tip = GUARD + SWORD_DROP.normalized() * SCABBARD_L
    n = 40
    path = [GUARD.lerp(tip, i / n) for i in range(n + 1)]
    path = clear_path(path, SCABBARD_W / 2)
    # scabbard: elliptical, the wide side front-back; gilt throat, two bands with rings, a long gilt chape
    length = sum((path[i + 1] - path[i]).length for i in range(n))
    acc = [0.0]
    for i in range(n):
        acc.append(acc[-1] + (path[i + 1] - path[i]).length)

    def mount(i):
        s = acc[i]
        return s < 0.09 or 0.27 < s < 0.30 or 0.50 < s < 0.53 or s > length - 0.14

    taper = lambda t: 1.0 - 0.35 * t  # noqa: E731
    rings = tube(part, path, lambda t: SCABBARD_D / 2 * taper(t),
                 lambda i, k: pal_uv('gold' if mount(i) else 'leather'), w, sides=12,
                 rx=None, ref=Vector((0, -1, 0)))
    for i, ring in enumerate(rings):  # the wide side front-back: stretch along the frame's first axis
        c = path[i]
        for k, v in enumerate(ring):
            a = 2 * math.pi * k / 12
            d = v.co - c
            v.co = c + d * 1.0 + (d.normalized() * abs(math.cos(a))) * (SCABBARD_W / 2 - SCABBARD_D / 2) * taper(i / n)
    cap(part, rings[-1], path[-1] + (path[-1] - path[-2]).normalized() * 0.012, pal_uv('gold'))
    cap(part, list(reversed(rings[0])), path[0], pal_uv('gold'))
    # hilt: grip with wire, pommel cap, guard plate, knuckle bow to the front
    grip = [POMMEL.lerp(GUARD, i / 8) for i in range(9)]
    tube(part, grip, lambda t: 0.0115 + 0.002 * math.sin(math.pi * t), lambda i, k: pal_uv('gold'), w, sides=10)
    lathe(part, POMMEL, -axis, [(-0.016, 0.0), (-0.016, 0.006), (-0.010, 0.0135), (0.0, 0.013), (0.004, 0.011)],
          lambda i, k: pal_uv('gold'), w, 12)
    fwd = Vector((0, -1, 0))
    lathe(part, GUARD, axis, [(-0.004, 0.0), (-0.004, 0.022), (0.004, 0.022), (0.006, 0.016), (0.006, 0.0)],
          lambda i, k: pal_uv('gold'), w, 16, ref=fwd)
    bow = [GUARD + fwd * 0.012, GUARD + fwd * 0.042 - axis * 0.02, (GUARD + POMMEL) / 2 + fwd * 0.05,
           POMMEL + fwd * 0.034 + axis * 0.01, POMMEL + fwd * 0.008]
    from_bow = []
    for a, b in zip(bow, bow[1:]):
        for j in range(4):
            from_bow.append(a.lerp(b, j / 4))
    from_bow.append(bow[-1])
    tube(part, from_bow, 0.0035, lambda i, k: pal_uv('gold'), w, sides=6)
    # sword knot: a gold cord from the guard down to a tassel
    knot = [GUARD + fwd * 0.02, GUARD + fwd * 0.03 + Vector((0, 0, -0.06)), KNOT_TASSEL + Vector((0.0, 0.01, 0.10)),
            KNOT_TASSEL + Vector((0, 0, 0.035))]
    kp = []
    for a, b in zip(knot, knot[1:]):
        for j in range(6):
            kp.append(a.lerp(b, j / 6))
    kp.append(knot[-1])
    kp = clear_path(kp, 0.004)
    tube(part, kp, 0.0035, lambda i, k: pal_uv('gold'), w, sides=6)
    lathe(part, KNOT_TASSEL, Vector((0, 0, -1)),
          [(t * TASSEL_K, r * TASSEL_K) for t, r in ((-0.035, 0.0), (-0.035, 0.006), (-0.025, 0.012), (-0.012, 0.010),
                                                     (-0.006, 0.013), (0.0, 0.016), (0.045, 0.02), (0.05, 0.012),
                                                     (0.052, 0.0))], lambda i, k: pal_uv('gold'), w, 14)
    return part.build('Sabre')


orders = build_orders()
sabre = build_sabre()
bpy.ops.outliner.orphans_purge(do_recursive=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
print('saved', OUT, os.path.getsize(OUT))

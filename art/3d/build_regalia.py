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
EP_X, EP_A, EP_B = 0.25, 0.09, 0.07  # centre |x|; semi-axes along the shoulder and across it
EP_LIFT, EP_DOME, EP_THICK = 0.014, 0.018, 0.007
EP_TILT = 18.0 
EP_FORWARD = 15.0               # ... and towards the front (in the portrait the fields face the viewer a little)                  # degrees: the field turns down outwards more than the shoulder top under it
STRAP_X, STRAP_W = 0.115, 0.030  # strap from the field to this |x| near the collar
FRINGE_N, FRINGE_ARC = 30, 240.0  # strands per row over this arc of the rim, centred on the outer end
FRINGE_LEN, FRINGE_R, FRINGE_OUT = 0.11, 0.0115, 0.028
FRINGE_TOP = (0.68, 0.0125, 0.6, 0.007)  # the upper row over it: length, radius, outward reach (x FRINGE_*), lift
# Bullion (canitel): a coiled gold wire - each strand a tight helix of BULLION_STARTS wires at BULLION_PITCH a turn.
BULLION_PITCH, BULLION_STARTS, BULLION_UV_LEN = 0.007, 1, 0.147  # 21 turns over the region
# Sash: a band 'SASH_W' wide round the torso in the plane through the top of the right shoulder and the left hip.
SASH_SHOULDER = Vector((-0.175, 0.0, 1.76))
SASH_HIP = Vector((0.17, 0.0, 1.31))   # the lower edge on the belt's top at the side
SASH_W, SASH_GAP, SASH_THICK, SASH_N = 0.095, 0.005, 0.002, 240
SASH_RELAX = 40                  # rounds of smoothing the band and pushing it out of the cloth
GOLD_FLOOR = 0.55                # gold albedo: the pictures' shading only darkens it down to this (the relief does the rest)
NORMAL_STRENGTH = {'cord': 3.0, 'pole': 2.0, 'sash': 0.05, 'bullion': 1.0}
# Aiguillettes: cords from under the right epaulette's front to the closure, hanging in loops; two loose cords with
# gold tips ('pencils') hang from the closure end over the sash.
AIG_FROM = (-0.215, 1.67)          # (x, z) on the front of the chest
AIG_TO = (-0.07, 1.60)     # under the sash
AIG_LOOPS = [(-0.175, 1.55), (-0.165, 1.49), (-0.155, 1.43)]  # lowest point of each loop
# the loose cords run on under the sash and come out at its lower edge (emerge), a short way over it to the knot the
# pencil hangs from (end): in the portrait the pencils hang over the sash's lower part
AIG_TAILS = [((0.068, 1.588), (0.078, 1.565)), ((0.06, 1.572), (0.092, 1.55))]  # (emerge, end), x z
AIG_R, AIG_GAP = 0.007, 0.002
PENCIL_L, PENCIL_R = 0.14, 0.0085
CORD_UV_LEN = 0.6                # metres of cord over the width of its atlas region (the twist repeats along it)

ATLAS = {
    'sash': (0.0, 0.0, 1.0, 0.125),
    'cord': (0.0, 0.125, 1.0, 0.1875),
    'bullion': (0.0, 0.1875, 1.0, 0.25),
    'pole': (0.0, 0.25, 0.5, 0.75),
    'gold': (0.5, 0.25, 0.5625, 0.3125),
}
# The generated material pictures (textures/gen, see art/prompts.md) and how often they repeat in their regions.
SASH_CONTRAST = 2.5               # the damask's light and dark, stronger than generated (it is faint on the model)
SASH_REPEATS = 12                # mirrored, even: the band's ends meet on the same column
CORD_REPEATS, BULLION_REPEATS = 8, 1  # the cord picture is seamless along its length (8 plies)

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
def bvh_of(obs, torso=False):
    """BVH of the objects; torso: the uniform without its sleeves (the sash and the cords lie on the torso - the hanging
    left arm is right by the sash's end at the hip, which would wrap onto it)."""
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
            arm = {i for i, n in enumerate(names) if n.startswith(('upperarm', 'lowerarm', 'hand'))}
            bmesh.ops.delete(b2, geom=[v for v in b2.verts if sum(w for g, w in v[dl].items() if g in arm) > 0.5],
                             context='VERTS')
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
    rgb = srgb(GOLD_SRGB) * (0.55 + 0.45 * h)[..., None]
    return rgb, 0.28 + 0.25 * (1 - h), h * BULLION_PITCH * 0.25


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

    def gold(region, c, recolour=True):
        """Gold from a generated picture: its shading only darkens bright gold down to GOLD_FLOOR (dark pictures made
        dull brown metal); bright thread shines, the gaps between are rougher."""
        x0, y0, x1, y1 = px(region)
        lum = c @ np.array([0.2126, 0.7152, 0.0722], np.float32)
        shade = np.clip(lum / max(float(np.percentile(lum, 95)), 1e-3), 0, 1)
        rgb[y0:y1, x0:x1] = (srgb(GOLD_SRGB) * (GOLD_FLOOR + (1 - GOLD_FLOOR) * shade)[..., None] if recolour
                             else mat_util.gold_grade(np.clip(c * 1.25, 0, 1), np.clip(shade * 3, 0, 1)))
        metal[y0:y1, x0:x1] = np.clip(shade * 2.0, 0.4, 1.0)
        rough[y0:y1, x0:x1] = np.clip(0.55 - shade * 0.3, 0.25, 0.55)
        relief(region, c, NORMAL_STRENGTH[region])

    x0, y0, x1, y1 = px('cord')
    gold('cord', cord_tex(x1 - x0, y1 - y0, CORD_REPEATS))
    x0, y0, x1, y1 = px('bullion')
    c, r, hgt = bullion_tex(x1 - x0, y1 - y0)
    rgb[y0:y1, x0:x1] = c; metal[y0:y1, x0:x1] = 1.0; rough[y0:y1, x0:x1] = r
    nrm[y0:y1, x0:x1] = normals(hgt, BULLION_UV_LEN / (x1 - x0), 2 * math.pi * FRINGE_R / (y1 - y0))
    x0, y0, x1, y1 = px('pole')
    gold('pole', pole_tex(x1 - x0, y1 - y0), recolour=False)
    x0, y0, x1, y1 = px('gold')
    rgb[y0:y1, x0:x1] = srgb(GOLD_SRGB); metal[y0:y1, x0:x1] = 1.0; rough[y0:y1, x0:x1] = 0.3
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
    if cap:  # rounded end: the last ring drawn to a point a radius further on
        t = (path[-1] - path[-2]).normalized()
        tip = bm.verts.new(path[-1] + t * r * 0.8)
        uvs[tip] = uv_in('gold', 0.5, 0.5)
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
    for _ in range(SASH_RELAX):  # a smooth band (the projection snaps to the belt's and buttons' edges), and nothing
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
def build_aiguillettes(under, over, part):
    """Cords lying on the chest (the front of 'surface' under them), loops from AIG_FROM to AIG_TO ('loops': built
    before the sash, which lies over them); loose cords from AIG_TO ending in pencils ('tails': over the sash)."""
    def on_chest(x, z, lift, surface=over):
        loc, nrm = front_at(surface, x, z)
        return loc + nrm * lift if loc is not None else Vector((x, -0.2, z))

    bm = bmesh.new()
    uvs = {}
    paths = []
    for lx, lz in (AIG_LOOPS if part == 'loops' else []):
        ctrl = [AIG_FROM, ((AIG_FROM[0] + lx) / 2 - 0.01, (AIG_FROM[1] + lz) / 2 - 0.02), (lx, lz),
                ((lx + AIG_TO[0]) / 2 + 0.01, (lz + AIG_TO[1]) / 2 - 0.02), AIG_TO]
        paths.append(ctrl)
    for emerge, end in AIG_TAILS:
        if part == 'loops':  # under the sash: built with the loops
            paths.append([AIG_TO, ((AIG_TO[0] + emerge[0]) / 2, (AIG_TO[1] + emerge[1]) / 2 + 0.01),
                          (emerge[0] - 0.012, emerge[1] + 0.004)])
        else:
            paths.append([(emerge[0] - 0.012, emerge[1] + 0.004), emerge, end])
    for k, ctrl in enumerate(paths):
        pts2 = catmull([Vector((x, 0, z)) for x, z in ctrl], 0.008)
        surf = under if part == 'loops' else over
        path = [on_chest(p.x, p.z, AIG_R + AIG_GAP + 0.0015 * k, surf) for p in pts2]  # each over the last
        _, u = tube(bm, path, AIG_R, 6, 'cord', cap=False)
        uvs.update(u)
    if part == 'loops':
        return new_part('Aiguillettes', bm, lambda v: uvs[v], lambda v: TORSO_W.at(v.co))
    cords = new_part('AiguilletteTails', bm, lambda v: uvs[v], lambda v: TORSO_W.at(v.co))
    # pencils: a gold tip at the end of each loose cord, along the cord's last direction
    bm = bmesh.new(); uvs = {}
    for via, end in AIG_TAILS:
        a = on_chest(*end, AIG_R + AIG_GAP)
        b = on_chest(end[0] + (end[0] - via[0]) * 0.5, end[1] - PENCIL_L, PENCIL_R + AIG_GAP)
        prof = lambda t: 0.75 + 0.25 * math.sin(min(t * 1.25, 1.0) * math.pi) if t < 0.85 else 0.9 * (1 - t) / 0.15 + 0.1
        # every point lifted off the sash and cloth under it by its radius (a straight line would cut into the chest)
        # straight, lifted as a whole off the sash and cloth under it by its radius where it comes closest
        path = [a.lerp(b, t / 10) for t in range(11)]
        lift = 0.0
        for p in path[1:]:
            q = on_chest(p.x, p.z, PENCIL_R * 1.1 + AIG_GAP + 0.002)
            n_ = (q - on_chest(p.x, p.z, 0.0)).normalized()
            lift = max(lift, (q - p).dot(n_))
        n_ = (on_chest(b.x, b.z, 0.01) - on_chest(b.x, b.z, 0.0)).normalized()
        path = [path[0]] + [p + n_ * lift * (t / 10) ** 0.5 for t, p in enumerate(path) if t]
        _, u = tube(bm, path, PENCIL_R, 8, 'gold', cap=True, taper=prof)
        uvs.update(u)
    pencils = new_part('AiguilletteTips', bm, lambda v: uvs[v], lambda v: TORSO_W.at(v.co))
    return cords, pencils


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
    sign = 1 if side == 'l' else -1
    top, nrm = CLOTH.ray_cast(Vector((sign * EP_X, 0.0, 2.2)), Vector((0, 0, -1)), 1.0)[:2]
    out = Vector((sign, 0, 0))
    Z = Matrix.Rotation(math.radians(-EP_TILT * sign), 3, 'Y') @ nrm  # tilted further down outwards
    Z = Matrix.Rotation(math.radians(EP_FORWARD), 3, 'X') @ Z           # and to the front (-Y)
    X = (out - Z * out.dot(Z)).normalized()
    Y = Z.cross(X)
    C = top + Z * EP_LIFT
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
    x_end = sign * STRAP_X - C.x
    strap_len = abs(x_end / X.x) if abs(X.x) > 1e-3 else 0.1
    srows = []
    for i in range(7):
        f = i / 6
        x = -EP_A * 0.7 - (strap_len - EP_A * 0.7) * f
        p0 = L(x, 0, 0)
        hit = CLOTH.ray_cast(p0 + Vector((0, 0, 0.1)), Vector((0, 0, -1)), 0.3)[0]
        z_on = (hit.z + 0.004 - p0.z) if hit is not None else 0.0
        row = []
        for y in (-STRAP_W / 2, STRAP_W / 2):
            v = bm.verts.new(L(x, y * (1 - 0.15 * f), 0) + Vector((0, 0, z_on * f)))
            uvs[v] = uv_in('cord', f * 0.2, 0.5 + y / STRAP_W * 0.9)
            row.append(v)
        srows.append(row)
    for r0, r1 in zip(srows, srows[1:]):
        bm.faces.new((r0[0], r0[1], r1[1], r1[0]))
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
    # the gaps of the lower); each rides on the cloth under its top
    bm = bmesh.new(); uvs = {}; wmap = {}
    half = math.radians(FRINGE_ARC) / 2
    for row, (k_len, rad, k_out, lift, shift) in enumerate(((1.0, FRINGE_R, 1.0, 0.0, 0.0), (*FRINGE_TOP, 0.5))):
        for i in range(FRINGE_N):
            a = -half + 2 * half * (i + 0.5 + shift) / (FRINGE_N + shift)
            rim_p = L(EP_A * 0.97 * math.cos(a), EP_B * 0.97 * math.sin(a), -EP_THICK + lift)
            radial = (X * math.cos(a) * EP_B + Y * math.sin(a) * EP_A).normalized()
            radial = Vector((radial.x, radial.y, 0)).normalized()
            jit = 0.004 * math.sin(i * 2.399 + row)
            length = (FRINGE_LEN * (0.92 + 0.08 * math.cos(a)) + jit) * k_len  # longest over the shoulder's end
            reach = FRINGE_OUT * k_out
            down = Vector((0, 0, -1))
            ctrl = [rim_p, rim_p + radial * reach * 0.6 + down * 0.008,
                    rim_p + radial * (reach + jit) + down * length * 0.5,
                    rim_p + radial * (reach * 1.3 + jit) + down * length]
            path = catmull(ctrl, 0.012)
            vs, u = tube(bm, path, rad, 6, 'bullion', uv_len=BULLION_UV_LEN)
            uvs.update(u)
            wt = on_shoulder(UNI_W.at(rim_p), side)
            for v in u:
                wmap[v] = wt
    fringe = new_part('EpauletteFringe_' + side, bm, lambda v: uvs[v], lambda v: wmap[v])
    return field, fringe


# the loops first: the sash lies over them (in the portrait they go under it), the loose cords over the sash
loops = build_aiguillettes(bvh_of([uni] + [bpy.data.objects[n] for n in ('Buttons',)]), None, 'loops')
CLOTH = bvh_of([uni, loops] + [bpy.data.objects[n] for n in ('Belt', 'Buckle', 'Buttons')], torso=True)
sash = build_sash()
aig = build_aiguillettes(None, bvh_of([uni, sash] + [bpy.data.objects[n] for n in ('Belt', 'Buckle', 'Buttons')]),
                         'tails')
CLOTH = bvh_of([uni, sash] + [bpy.data.objects[n] for n in ('Belt', 'Buckle', 'Buttons', 'Collar')])
eps = [build_epaulette(s) for s in 'lr']

rig.data.pose_position = 'POSE'
bpy.ops.outliner.orphans_purge(do_recursive=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
print('saved', OUT, os.path.getsize(OUT))

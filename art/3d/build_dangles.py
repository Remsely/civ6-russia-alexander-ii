# Bones for what hangs loose - the sword knot's tassel, the aiguillettes' loops and their pencils, the epaulettes'
# fringe, the skirt of the tunic - so they can swing after the body when it moves (the game has no cloth physics: the
# idle animation carries their motion, simulated by tools/blender/motion_test.py's springs and baked into it).
# blender -b art/3d/alexander_leader.blend --python art/3d/build_dangles.py   (after build_orders.py; in place)
#
# Each chain is parented to the bone that carries the piece; the piece's vertices are moved onto the chain by how far
# they hang from where the piece is held (0 there, 1 at the free end), the rest of their weight kept as it was.
# Bones get 'dangle' = (stiffness, damping) for the spring simulation.
import bpy, math, os, sys
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'alexander_leader.blend')
# (stiffness, damping) of the springs, per second squared and per second: a hanging piece swings like a pendulum of its
# length (stiffness ~ g / L), lightly damped; the thick twisted cords of the aiguillettes are heavier and stiffer than
# a pendulum (they sway, never flap), the bullion fringe is stiff wire and the wool skirt stops soonest
SPRING = {'knot': (45.0, 2.0), 'loop': (95.0, 5.0), 'pencil': (85.0, 4.5), 'fringe': (260.0, 12.0),
          'skirt': (150.0, 8.0)}
SKIRT_BONES = 4                    # round the skirt: front left / right, back left / right
SKIRT_SHARE = 0.6                  # at the hem the skirt bones carry this much (the thighs and pelvis the rest)

sc = bpy.context.scene
rig = bpy.data.objects['HumanRig']
P = sc['uniform'].to_dict()
added = []  # (bone, parent, head, tail, kind)
if any(b.name.startswith('dangle_') for b in rig.data.bones):  # their weights were taken from the others: not twice
    sys.exit('build_dangles.py: the rig has dangle bones already - rebuild from the pose step (build_all.py --from pose)')


def smoothstep(x, a, b):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def islands(me):
    parent = list(range(len(me.vertices)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    for e in me.edges:
        parent[find(e.vertices[0])] = find(e.vertices[1])
    groups = {}
    for i in range(len(parent)):
        groups.setdefault(find(i), []).append(i)
    return [np.array(g) for g in groups.values()]


def coords(ob):
    co = np.zeros(len(ob.data.vertices) * 3); ob.data.vertices.foreach_get('co', co)
    return co.reshape(-1, 3)


def dominant_bone(ob, idx):
    acc = {}
    names = [g.name for g in ob.vertex_groups]
    for i in idx:
        for g in ob.data.vertices[int(i)].groups:
            acc[names[g.group]] = acc.get(names[g.group], 0.0) + g.weight
    return max(acc, key=acc.get)


def put_on(ob, idx, bone, amount):
    """Vertices idx of ob: amount (per vertex, 0..1) of their weight moved onto bone, the rest scaled down."""
    g = ob.vertex_groups.get(bone) or ob.vertex_groups.new(name=bone)
    for i, a in zip(idx, amount):
        v = ob.data.vertices[int(i)]
        if a <= 1e-4:
            continue
        for e in v.groups:
            e.weight *= (1 - a)
        g.add([int(i)], float(a), 'ADD')


def chain(ob, idx, name, parent, head, tail, kind, start=0.0):
    """One bone from head to tail; the vertices weighted by how far along it they hang (from start)."""
    head, tail = Vector(head), Vector(tail)
    added.append((name, parent, head, tail, kind))
    co = coords(ob)[idx]
    d = np.array(tail - head); L2 = float(d @ d)
    t = np.clip((co - np.array(head)) @ d / L2, 0, 1)
    put_on(ob, idx, name, [smoothstep(x, start, start + 0.6) for x in t])


# ---------------------------------------------------------------- sword knot and the belt's cord: down to the tassels
for name, bone in (('SwordKnot', 'dangle_knot'), ('BeltKnot', 'dangle_beltknot')):
    knot = bpy.data.objects.get(name)
    if knot:
        co = coords(knot)
        top = co[np.argmax(co[:, 2])]; bottom = co[np.argmin(co[:, 2])]
        idx = np.arange(len(co))
        chain(knot, idx, bone, dominant_bone(knot, idx), top, bottom, 'knot', 0.05)

# ---------------------------------------------------------------- aiguillettes: each loop swings about its two ends
aig = bpy.data.objects.get('Aiguillettes')
if aig:
    co = coords(aig)
    loops = [ix for ix in islands(aig.data) if co[ix, 2].max() - co[ix, 2].min() > 0.05]  # not the cords under the sash
    for k, idx in enumerate(sorted(loops, key=lambda ix: -co[ix, 2].min())):
        pts = co[idx]
        low = pts[np.argmin(pts[:, 2])]
        top = pts[np.argmax(pts[:, 2])]
        head = Vector(((pts[:, 0].max() + pts[:, 0].min()) / 2, top[1], top[2] - 0.01))
        chain(aig, idx, 'dangle_loop_%d' % k, 'spine_03', head, low, 'loop', 0.0)
# pencils: each hangs from its knot at the end of a loose cord
tips = bpy.data.objects.get('AiguilletteTips')
if tips:
    tc = coords(tips)
    for k, idx in enumerate(sorted(islands(tips.data), key=lambda ix: tc[ix, 0].mean())):
        pts = tc[idx]
        top = Vector(pts[np.argmax(pts[:, 2])]); low = Vector(pts[np.argmin(pts[:, 2])])
        head = top + Vector((0, 0, 0.015))
        chain(tips, idx, 'dangle_pencil_%d' % k, 'spine_03', head, low, 'pencil', 0.0)

# ---------------------------------------------------------------- epaulette fringe: swings from the rim
for s in 'lr':
    fr = bpy.data.objects.get('EpauletteFringe_' + s)
    if not fr:
        continue
    co = coords(fr)
    idx = np.arange(len(co))
    top = co[:, 2].max(); bot = co[:, 2].min()
    c = co.mean(0)
    head = Vector((c[0], c[1], top)); tail = Vector((c[0] + (0.03 if s == 'l' else -0.03), c[1], bot))
    name = 'dangle_fringe_' + s
    added.append((name, dominant_bone(fr, idx), head, tail, 'fringe'))
    put_on(fr, idx, name, [smoothstep((top - z) / (top - bot), 0.15, 0.9) for z in co[:, 2]])

# ---------------------------------------------------------------- skirt: four flaps from the waist to the hem
uni = bpy.data.objects['Uniform']
co = coords(uni)
part = np.zeros(len(uni.data.polygons), np.int32)
uni.data.attributes['part'].data.foreach_get('value', part) if 'part' in uni.data.attributes else None
tunic_v = np.zeros(len(co), bool)
for p, pt in zip(uni.data.polygons, part):
    if pt == 0:
        tunic_v[list(p.vertices)] = True
z0, z1 = P['WAIST_Z'] - 0.05, co[tunic_v, 2].min()
skirt = np.where(tunic_v & (co[:, 2] < z0))[0]
centre = co[skirt].mean(0)
for k in range(SKIRT_BONES):
    a = 2 * math.pi * (k + 0.5) / SKIRT_BONES  # 0 at the front (-Y), towards his left (+X)
    d = Vector((math.sin(a), -math.cos(a), 0))
    ang = np.arctan2(co[skirt, 0] - centre[0], -(co[skirt, 1] - centre[1]))
    share = np.clip(np.cos(ang - a), 0, None) ** 2
    share /= np.maximum(sum(np.clip(np.cos(ang - 2 * math.pi * (j + 0.5) / SKIRT_BONES), 0, None) ** 2
                            for j in range(SKIRT_BONES)), 1e-6)
    t = np.clip((z0 - co[skirt, 2]) / (z0 - z1), 0, 1)
    head = Vector((centre[0], centre[1], z0)) + d * 0.12
    tail = Vector((centre[0], centre[1], z1)) + d * 0.17
    name = 'dangle_skirt_%d' % k
    added.append((name, 'pelvis', head, tail, 'skirt'))
    put_on(uni, skirt, name, share * SKIRT_SHARE * t ** 1.5)
# what is sewn onto the skirt follows it (the piping is in the texture; buttons and pockets would be here)

# ---------------------------------------------------------------- the bones
bpy.context.view_layer.objects.active = rig
for o in sc.objects:
    o.select_set(o == rig)
bpy.ops.object.mode_set(mode='EDIT')
eb = rig.data.edit_bones
for name, parent, head, tail, kind in added:
    if name in eb:
        eb.remove(eb[name])
    b = eb.new(name)
    b.head, b.tail = head, tail
    b.parent = eb[parent]
    b.use_deform = True
bpy.ops.object.mode_set(mode='OBJECT')
for name, parent, head, tail, kind in added:
    rig.pose.bones[name]['dangle'] = SPRING[kind]
for ob in sc.objects:  # weights renormalised (ADD may leave sums over 1 where groups overlapped)
    if ob.type != 'MESH' or not any(m.type == 'ARMATURE' for m in ob.modifiers):
        continue
    for v in ob.data.vertices:
        s_ = sum(g.weight for g in v.groups)
        if s_ > 1.0001:
            for g in v.groups:
                g.weight /= s_
print('dangles:', ', '.join('%s (%s, %.0f cm)' % (n, p, (t - h).length * 100) for n, p, h, t, _ in added))
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
print('saved', OUT, os.path.getsize(OUT))

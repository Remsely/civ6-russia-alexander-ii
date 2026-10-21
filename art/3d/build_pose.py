# The leader in the portrait's stance (pose.py), the cloth settled on the posed body; the stance becomes the rig's rest.
# blender -b art/3d/alexander_rest.blend --python art/3d/build_pose.py   (after build_head.py; writes alexander_leader.blend)
#
# 1. Everything sewn onto the uniform (collar, buttons, belt, cuffs) is bound to the uniform's surface (Surface Deform)
#    and follows it - the folds as well; buttons and the buckle move as rigid pieces; boots, head and hands follow the
#    bones. The regalia are built afterwards on the posed uniform (build_regalia.py): they hang as in the stance.
# 2. The bones go from rest into the stance over POSE_FRAMES; the uniform's single sheet is simulated as wool over the
#    posed body (collision) and itself (sleeves against the torso) and settles for SETTLE_FRAMES more. Where the
#    uniform is held - collar and shoulders, under the belt, the cuffs, inside the boots - it is pinned to the bones;
#    sleeves, chest, skirt and trouser legs hang free, so they fold where the pose bunches them.
# 3. Every mesh is baked as it is at the last frame, the pose applied as the rig's rest, the armature put back.
import bpy, math, os, sys
import numpy as np
from mathutils import Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pose  # noqa: E402
from mat_util import belt_z  # noqa: E402

OUT = os.path.join(HERE, 'alexander_leader.blend')
POSE_FRAMES, SETTLE_FRAMES = 24, 24
BONES_ONLY = ('Boot', 'Sole', 'Spur')   # details that follow the bones, not the cloth
RIGID = ('Buttons', 'Buckle', 'CuffButtons')  # each piece of these moves as a whole with the cloth under it
SUBDIVIDE = 1                           # cuts per edge of the uniform's sheet before the simulation
SLEEVE_PIN = 0.5                        # sleeves held this much to the arm (less: they slide down and balloon)
CLOSURE_PIN = 0.7                       # the strip along the front closure held this much (its step and piping straight)
TROUSER_PIN = 0.6                       # trouser legs held this much to the legs: they turn with them (at 0.05 the
                                        # legs turned out inside them and the stripes stayed where a straight leg has them)
SKIRT_PIN = (0.14, 0.32)                # the skirt held this much at the hem, at the belt
# cloth: heavy broadcloth
CLOTH = dict(quality=8, mass=0.35, air_damping=1.0, tension_stiffness=40, compression_stiffness=40,
             shear_stiffness=20, bending_stiffness=6.0, tension_damping=8, compression_damping=8, shear_damping=8,
             pin_stiffness=4.0)
ELBOW_R = (0.05, 0.13)                  # sleeve smoothed fully within this of the elbow joint, fading out by the second
SHOULDER_R = (0.06, 0.16)               # ... and the cloth round the shoulder joint
JOINT_ROUNDS, JOINT_CLEAR = 12, 0.006   # Taubin rounds; the cloth at least this off the skin there
SLEEVE_MIN_R, ELBOW_PASSES = 0.05, 4    # the sleeve this far at least from the arm bones round the elbow; rounds
UNTANGLE_TRIES, UNTANGLE_RINGS = 6, 4      # rounds of smoothing round the sheet's self-crossings; rings of neighbours
SKIRT_BACK_ROUNDS = 30                  # smooth_skirt_back: Taubin rounds over the skirt's back
SKIRT_FRONT = (0.05, 0.10, 60)          # smooth_skirt_front: within the first of the closure fully, fading out by the
                                        # second; rounds of smoothing the cloth's move off the skinned sheet
TORSO_ROUNDS = 40                       # smooth_torso: Taubin rounds over the tunic's body above the belt
SHOULDER_FIT_OFF = 0.008               # fit_shoulders: the tunic this far off the body over the shoulders' top ...
SHOULDER_FIT_FROM = 0.015               # ... fading in over this much beyond the collar's foot (over 3 cm, the
                                        # trapezius' fall by the collar was bridged in a level shelf)
SHOULDER_FIT_Z = (1.57, 1.63)           # ... above the armpits
SHOULDER_FIT_NZ = (0.0, 0.3)            # ... where the body faces up (fading out down the arm's outside)
SHOULDER_FIT_ROUNDS = 8                 # ... the move smoothed out into the cloth round
TORSO_KEEP = (0.012, 0.03)              # ... none within the first of a button or the closure's edge, fully past the second
UNI_IN, UNI_IN_BELOW, UNI_IN_SHIRT = 0.003, 0.010, -0.001  # uniform_in_collar: inside the collar by; from under
                                        # its foot (at 4 mm the creases over the shoulders rose to the foot in knobs);
                                        # up to just under the shirt collar's lower edge (the shirt lies as far out as
                                        # the tunic's inside: up over its edge, the tunic went through it)
COLLIDE = dict(distance_min=0.004, self_distance_min=0.003, collision_quality=4)
NECK_IN, NECK_EASE, NECK_ROUNDS = 0.006, 0.03, 12  # the head inside the collar's inner side by this (the shirt
                                        # collar lies between; at 8 mm it pulled the neck in off the shirt); eased out
                                        # over this much above its top edge; smoothing rounds
UNI_FOOT_ONLY = 0.012                   # uniform_in_collar(foot_only): up to this over the foot (higher, the settled
                                        # stand pulled in onto the neck at the nape)
UNI_FOOT_TRIES = 8                      # uniform_in_collar: rays 2 mm apart up from under the foot
UNI_OPENING_DROP = (0.008, 0.25, 0.40)  # uniform_under_shirt: in the collar's opening (to the first angle from the
                                        # front, faded out by the second, rad) its top this much lower still - the
                                        # shirt there stands out at the collar's radius, ~7 mm off the neck, and from
                                        # above its ragged top and red piping showed in the gap behind the white
NECK_CLEAR = 0.002                      # uniform_off_neck: the tunic's inside at least this off the neck
NECK_OVER = 0.004                       # ... or this far up over its top edge
NECK_OUT = 0.003                        # ... or (the beard and whiskers, nearer its outside) this far out of it
NECK_UP_DEPTH = (0.012, 0.025)          # from under the edge: up only down to the first, in only from the second

sc = bpy.context.scene
rig, h, uni = bpy.data.objects['HumanRig'], bpy.data.objects['Human'], bpy.data.objects['Uniform']
P = dict(sc['uniform'])
for o in list(bpy.data.objects):  # regalia are built on the posed uniform afterwards (build_regalia.py)
    if o.get('regalia'):
        bpy.data.objects.remove(o)
names = [g.name for g in uni.vertex_groups]


def smoothstep(x, a, b):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def activate(ob):
    for o in sc.objects:
        o.select_set(o == ob)
    bpy.context.view_layer.objects.active = ob


# ---------------------------------------------------------------- 1. followers bound to the uniform sheet (rest pose)


def neck_to_chest(ob):
    """The collar sits on the shoulders: what the neck and head bones carried of ob goes to spine_03 (the neck and
    head turn inside it - the stand collar reaches up to the jaw, and with the head's weight its top turned with the
    head, the opening at the front running slantwise)."""
    cg = ob.vertex_groups.get('spine_03') or ob.vertex_groups.new(name='spine_03')
    for n in ('neck_01', 'head'):
        ng = ob.vertex_groups.get(n)
        if ng is None:
            continue
        for v in ob.data.vertices:
            w = next((g.weight for g in v.groups if g.group == ng.index), 0.0)
            if w > 0:
                cg.add([v.index], w, 'ADD')
        ob.vertex_groups.remove(ng)


for o in sc.objects:
    if o.type == 'MESH' and (o == uni or o.get('detail')):
        neck_to_chest(o)

thick = uni.modifiers['Thick']
thick.show_viewport = thick.show_render = False
activate(uni)  # Surface Deform binds only to convex faces
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.remove_doubles(threshold=0.0005)  # zero-length edges make the cloth solver explode
bpy.ops.mesh.dissolve_degenerate(threshold=0.0005)
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.subdivide(number_cuts=SUBDIVIDE)  # a finer sheet folds finer
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.quads_convert_to_tris(quad_method='BEAUTY', ngon_method='BEAUTY')
bpy.ops.object.mode_set(mode='OBJECT')
followers = [o for o in sc.objects if o.type == 'MESH' and (o.get('detail') or o.get('regalia'))
             and not o.name.startswith(BONES_ONLY)]
for o in followers:
    for m in o.modifiers:
        if m.type == 'ARMATURE':
            m.show_viewport = m.show_render = False
    sd = o.modifiers.new('Follow', 'SURFACE_DEFORM')
    sd.target = uni
    sd.falloff = 4.0
    activate(o)
    with bpy.context.temp_override(object=o, active_object=o):
        bpy.ops.object.surfacedeform_bind(modifier='Follow')
    if not sd.is_bound:  # unbound, it would stay in the rest pose (the cuffs hanging where the A-pose had the wrists)
        raise RuntimeError('%s could not be bound to the uniform' % o.name)
print('bound to the uniform:', ', '.join(o.name for o in followers))
REST_CO = {o.name: np.array([v.co[:] for v in o.data.vertices]) for o in followers if o.name.startswith(RIGID)}


def islands(me):
    """Vertex index arrays of the mesh's connected pieces."""
    parent = list(range(len(me.vertices)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    for e in me.edges:
        a, b = find(e.vertices[0]), find(e.vertices[1])
        parent[a] = b
    groups = {}
    for i in range(len(parent)):
        groups.setdefault(find(i), []).append(i)
    return [np.array(g) for g in groups.values()]


def make_rigid(ob):
    """Each piece of ob put back in its rest shape, moved by the rigid fit to where the cloth took it."""
    rest = REST_CO[ob.name]
    co = np.array([v.co[:] for v in ob.data.vertices])
    for idx in islands(ob.data):
        A, B = rest[idx], co[idx]
        ma, mb = A.mean(0), B.mean(0)
        U, _, Vt = np.linalg.svd((B - mb).T @ (A - ma))
        D = np.eye(3); D[2, 2] = np.sign(np.linalg.det(U @ Vt))
        R = U @ D @ Vt
        co[idx] = (A - ma) @ R.T + mb
    ob.data.vertices.foreach_set('co', co.astype(np.float32).ravel())
    ob.data.update()


# ---------------------------------------------------------------- 2. pin weights, cloth, the pose animated
def pin_weights():
    """Per vertex of the sheet (rest pose): 1 pinned to the bones .. 0 free."""
    me = uni.data
    part_v = np.zeros(len(me.vertices), np.int32)
    part = np.zeros(len(me.polygons), np.int32)
    me.attributes['part'].data.foreach_get('value', part)
    for p, pt in zip(me.polygons, part):
        for i in p.vertices:
            part_v[i] = max(part_v[i], pt)
    bones = {b.name: (b.head_local.copy(), b.tail_local.copy()) for b in rig.data.bones}
    w = np.zeros(len(me.vertices))
    for v in me.vertices:
        c = v.co
        zc = belt_z(P, c.x, c.y)
        g = {names[x.group]: x.weight for x in v.groups}
        arm = sum(x for n, x in g.items() if n.startswith(('upperarm', 'lowerarm', 'hand')))
        if part_v[v.index] == 2:  # trousers: the waistband and inside the boot shafts
            w[v.index] = max(TROUSER_PIN, smoothstep(c.z, P['WAIST_Z'] - 0.16, P['WAIST_Z'] - 0.08),
                             1 - smoothstep(c.z, P['BOOT_TOP'], P['BOOT_TOP'] + 0.10))
            continue
        if arm > 0.5:  # sleeve: held at the shoulder seam and the cuff
            s = 'l' if c.x > 0 else 'r'
            a, b = bones['lowerarm_' + s]
            t = (c - a).dot(b - a) / (b - a).length_squared
            sh = (c - bones['upperarm_' + s][0]).length
            w[v.index] = max(SLEEVE_PIN, smoothstep(t, P['SLEEVE_T'] - P['CUFF_T'], P['SLEEVE_T'] - P['CUFF_T'] + 0.1),
                             1 - smoothstep(sh, 0.05, 0.11))
            continue
        belt = 1 - smoothstep(abs(c.z - zc), P['BELT_H'] / 2 + 0.01, P['BELT_H'] / 2 + 0.06)
        upper = smoothstep(c.z, 1.50, 1.64)  # collar, shoulders, upper back
        # torso / skirt: the skirt held a little, more towards the belt (at 0.04 the stepping legs folded its back
        # over itself in a crumpled flap)
        chest = 0.35 if c.z > zc else SKIRT_PIN[0] + (SKIRT_PIN[1] - SKIRT_PIN[0]) * smoothstep(c.z, P['HEM_Z'], zc)
        # the closure: the flap's step and its piping stay straight (free, the step crumples into a zigzag)
        closure = CLOSURE_PIN * (1 - smoothstep(abs(c.x - P['FLAP_X']), 0.015, 0.04)) if c.y < -0.03 else 0.0
        w[v.index] = max(chest, belt, upper, closure)
    g = uni.vertex_groups.get('pin') or uni.vertex_groups.new(name='pin')
    for i, x in enumerate(w):
        g.add([i], float(x), 'REPLACE')
    print('pin: %d free, %d pinned of %d' % (int((w < 0.2).sum()), int((w > 0.99).sum()), len(w)))


pin_weights()
cloth = uni.modifiers.new('Cloth', 'CLOTH')
cs = cloth.settings
for k, v in CLOTH.items():
    setattr(cs, k, v)
cs.mass = CLOTH['mass'] / (SUBDIVIDE + 1) ** 2  # Blender's mass is per vertex: the sheet weighs the same
cs.vertex_group_mass = 'pin'
cc = cloth.collision_settings
cc.use_collision = True
cc.use_self_collision = True
for k, v in COLLIDE.items():
    setattr(cc, k, v)
last = POSE_FRAMES + SETTLE_FRAMES
cloth.point_cache.frame_start, cloth.point_cache.frame_end = 1, last
sc.frame_start, sc.frame_end = 1, last

h.hide_set(False); h.hide_viewport = False  # the collider is the whole MPFB body (BodyUnder lacks the torso)
# forearms and hands are not in it: moving into place behind the back they would drag the skirt up with them
hg = [g.index for g in h.vertex_groups if g.name.startswith(('lowerarm', 'hand', 'index', 'middle', 'ring', 'pinky',
                                                               'thumb'))]
cg = h.vertex_groups.get('collider') or h.vertex_groups.new(name='collider')
for v in h.data.vertices:
    if sum(x.weight for x in v.groups if x.group in hg) < 0.3:
        cg.add([v.index], 1.0, 'REPLACE')
mask = h.modifiers.new('ColliderMask', 'MASK')
mask.vertex_group = 'collider'
col = h.modifiers.new('Collision', 'COLLISION')
h.collision.thickness_outer = 0.004
h.collision.cloth_friction = 10.0

# the pose: rest at frame 1, the stance from POSE_FRAMES on
sc.frame_set(1)
for pb in rig.pose.bones:
    pb.matrix_basis.identity()
    for path in ('location', 'rotation_quaternion', 'rotation_euler'):
        pb.keyframe_insert(path, frame=1)
pose.set_pose(rig)
for pb in rig.pose.bones:
    for path in ('location', 'rotation_quaternion', 'rotation_euler'):
        pb.keyframe_insert(path, frame=POSE_FRAMES)
for f in range(1, last + 1):
    sc.frame_set(f)
print('cloth simulated over %d frames' % last)


# ---------------------------------------------------------------- 3. bake the last frame, the stance as the rest pose
def bake(ob):
    """ob's evaluated mesh (at the current frame) as its data; deforming modifiers dropped."""
    masks = [m for m in ob.modifiers if m.type == 'MASK' and m.show_viewport]  # the body keeps its helpers
    for m in masks:
        m.show_viewport = False
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    for m in masks:
        m.show_viewport = True
    old = ob.data
    if old.shape_keys:
        ob.shape_key_clear()
    me.name = old.name
    ob.data = me
    me.materials.clear()
    for mat in old.materials:
        me.materials.append(mat)
    for m in list(ob.modifiers):
        if m.type in ('ARMATURE', 'SURFACE_DEFORM', 'CLOTH', 'COLLISION'):
            ob.modifiers.remove(m)


def arm_w(ob):
    """Per vertex of ob: its weight on the upper arms and forearms."""
    arm = {g.index for g in ob.vertex_groups if g.name.startswith(('upperarm', 'lowerarm'))}
    return np.array([sum(x.weight for x in v.groups if x.group in arm) for v in ob.data.vertices])


def smooth_joints():
    """The bent elbow pinches the skinned arm, and the half-pinned sleeve over it creases into a knot of folds; the arm
    taken back bunches the cloth up behind the shoulder: round each elbow (the sleeve) and each shoulder joint (sleeve
    and back) the cloth is smoothed (Taubin: no shrinking), then kept JOINT_CLEAR off the skin."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    me = uni.data
    co = np.array([v.co[:] for v in me.vertices])
    nb = [[] for _ in range(len(co))]
    for e in me.edges:
        a, b = e.vertices
        nb[a].append(b); nb[b].append(a)
    sleeve = arm_w(uni) > 0.5  # at the elbow: not the torso the left elbow hangs by
    k = np.zeros(len(co))
    for bone, (r0, r1), only in (('lowerarm_', ELBOW_R, sleeve), ('upperarm_', SHOULDER_R, None)):
        for s in 'lr':
            d = np.linalg.norm(co - np.array(rig.pose.bones[bone + s].head), axis=1)
            w = 1 - np.clip((d - r0) / (r1 - r0), 0, 1)
            k = np.maximum(k, w * w * (3 - 2 * w) * (only if only is not None else 1))
    zone = np.where(k > 0)[0]
    # the bent elbow: the sleeve round it at least SLEEVE_MIN_R off the two arm bones (capsules round the upper arm
    # and forearm) - the skin pinches in the crook and the cloth followed it into a notch; the outside of the joint
    # rounds off over the capsules' spheres instead of standing in a point. Smoothed, pushed out again, a few times.
    segs = {s: [(np.array(rig.pose.bones[b + s].head), np.array(rig.pose.bones[b + s].tail))
                 for b in ('upperarm_', 'lowerarm_')] for s in 'lr'}
    elbow = {}
    for s in 'lr':
        d = np.linalg.norm(co - np.array(rig.pose.bones['lowerarm_' + s].head), axis=1)
        elbow[s] = np.where(sleeve & (d < ELBOW_R[1] * 1.2))[0]

    def capsules():
        n = 0
        for s, idx in elbow.items():
            best = np.full(len(idx), 1e9); foot = np.zeros((len(idx), 3))
            for a, b in segs[s]:
                ab = b - a
                t = np.clip(((co[idx] - a) @ ab) / (ab @ ab), 0, 1)
                q = a + t[:, None] * ab
                dd = np.linalg.norm(co[idx] - q, axis=1)
                closer = dd < best
                best[closer] = dd[closer]; foot[closer] = q[closer]
            low = best < SLEEVE_MIN_R
            out = (co[idx] - foot) / np.maximum(best, 1e-6)[:, None]
            co[idx[low]] = foot[low] + out[low] * SLEEVE_MIN_R
            n += int(low.sum())
        return n
    pushed_e = 0
    for rnd in range(ELBOW_PASSES):
        pushed_e += capsules()
        for _ in range(JOINT_ROUNDS // 2):
            for f in (0.6, -0.63):
                lap = np.array([co[nb[i]].mean(0) - co[i] if nb[i] else np.zeros(3) for i in zone])
                co[zone] += lap * (f * k[zone])[:, None]
    pushed_e += capsules()
    print('elbows: %d sleeve vertices brought out to the arm capsules' % pushed_e)
    tree = BVHTree.FromPolygons([v.co.copy() for v in h.data.vertices], [tuple(p.vertices) for p in h.data.polygons])
    pushed = 0
    for i in zone:
        p = Vector(co[i])
        loc, nrm, _, _ = tree.find_nearest(p, 0.05)
        if loc is not None and (p - loc).dot(nrm) < JOINT_CLEAR:
            co[i] = loc + nrm * JOINT_CLEAR
            pushed += 1
    me.vertices.foreach_set('co', co.astype(np.float32).ravel())
    me.update()
    print('joints: %d cloth vertices smoothed, %d kept off the skin' % (len(zone), pushed))


def untangle():
    """Where the sheet has run through itself (a fold pressed flat where the arm is taken back, behind the shoulder),
    the lining's thickness would come out through it in spikes: around every crossing the sheet is smoothed until no
    two faces that share no vertex cross."""
    from mathutils.bvhtree import BVHTree
    me = uni.data
    co = np.array([v.co[:] for v in me.vertices])
    faces = [tuple(p.vertices) for p in me.polygons]
    nb = [[] for _ in range(len(co))]
    for e in me.edges:
        a, b = e.vertices
        nb[a].append(b); nb[b].append(a)
    for rnd in range(UNTANGLE_TRIES):
        t = BVHTree.FromPolygons([tuple(c) for c in co], faces)
        bad = set()
        for i, j in t.overlap(t):
            if i < j and not set(faces[i]) & set(faces[j]):
                bad.update(faces[i]); bad.update(faces[j])
        print('untangle: %d vertices in crossing faces%s' % (len(bad), (' round (%.3f %.3f %.3f)' % tuple(co[sorted(bad)].mean(0)))
                                                              if 0 < len(bad) < 100 else ''))
        if not bad:
            break
        zone = set(bad)
        for _ in range(UNTANGLE_RINGS):
            zone |= {n for i in zone for n in nb[i]}
        zone = np.array(sorted(zone))
        for _ in range(10):
            for f in (0.6, -0.63):
                lap = np.array([co[nb[i]].mean(0) - co[i] for i in zone])
                co[zone] += lap * f
    me.vertices.foreach_set('co', co.astype(np.float32).ravel())
    me.update()


def skinned_co(ob):
    """ob's vertices as its armature alone puts them (a copy without the cloth: switching the cloth off would drop
    its simulated frames)."""
    tmp = ob.copy()
    for m in list(tmp.modifiers):
        if m.type != 'ARMATURE':
            tmp.modifiers.remove(m)
    sc.collection.objects.link(tmp)
    dg = bpy.context.evaluated_depsgraph_get()
    e = tmp.evaluated_get(dg)
    me = e.to_mesh()
    co = np.array([v.co[:] for v in me.vertices])
    e.to_mesh_clear()
    bpy.data.objects.remove(tmp)
    return co


UNI_SKINNED = skinned_co(uni)
skinned = [o for o in sc.objects if o.type == 'MESH' and any(m.type == 'ARMATURE' for m in o.modifiers)]
for o in skinned:
    bake(o)
    if o.name in REST_CO:
        make_rigid(o)
untangle()
smooth_joints()


def smooth_torso():
    """A tailored tunic's body lies smooth over the chest and back: the simulated sheet crumpled there (the arms
    taken back and down pull at it), and the orders, the stars and the aiguillettes, built on it afterwards, stood in
    the dents askew. Above the belt and under the collar, away from the sleeves, the sheet is smoothed (Taubin), the
    closure's step and the buttons' places left as they are; then kept JOINT_CLEAR off the body."""
    from mathutils.bvhtree import BVHTree
    from mathutils.kdtree import KDTree
    me = uni.data
    co = np.array([v.co[:] for v in me.vertices])
    nb = [[] for _ in range(len(co))]
    for e in me.edges:
        a, b = e.vertices
        nb[a].append(b); nb[b].append(a)
    btn = bpy.data.objects.get('Buttons')
    kd = KDTree(len(btn.data.vertices) if btn else 0)
    if btn:
        for i, v in enumerate(btn.data.vertices):
            kd.insert(btn.matrix_world @ v.co, i)
    kd.balance()
    top = P['STAND_TOP_BACK'] - 0.06
    arm = arm_w(uni)
    k = np.zeros(len(co))
    for i, c in enumerate(co):
        low = belt_z(P, c[0], c[1]) + P['BELT_H'] / 2 + 0.01
        if not low < c[2] < top + 0.03:
            continue
        w = smoothstep(c[2], low, low + 0.03) * (1 - smoothstep(c[2], top, top + 0.03))
        w *= 1 - smoothstep(arm[i], 0.15, 0.5)
        near = kd.find(c)[2] if btn else 1.0
        edge = abs(c[0] - P['FLAP_X']) if c[1] < -0.03 else 1.0
        w *= smoothstep(min(near, edge), *TORSO_KEEP)
        k[i] = w
    zone = np.where(k > 0)[0]
    for _ in range(TORSO_ROUNDS):
        for f in (0.6, -0.63):
            lap = np.array([co[nb[i]].mean(0) - co[i] if nb[i] else np.zeros(3) for i in zone])
            co[zone] += lap * (f * k[zone])[:, None]
    bi = h.vertex_groups['body'].index  # the skin only: MPFB's helpers (tights, skirt) stand off it (kept off them,
    skin = {v.index for v in h.data.vertices if any(g.group == bi and g.weight > 0.5 for g in v.groups)}  # the back
    tree = BVHTree.FromPolygons([v.co.copy() for v in h.data.vertices],  # stood in a 2 cm ridge down the spine)
                                [tuple(p.vertices) for p in h.data.polygons if all(i in skin for i in p.vertices)])
    pushed = 0
    for i in zone:
        q = Vector(co[i])
        loc, nrm, _, _ = tree.find_nearest(q, 0.05)
        if loc is not None and (q - loc).dot(nrm) < JOINT_CLEAR:
            co[i] = loc + nrm * JOINT_CLEAR
            pushed += 1
    me.vertices.foreach_set('co', co.astype(np.float32).ravel())
    me.update()
    print('torso: %d cloth vertices smoothed, %d kept off the body' % (len(zone), pushed))


smooth_torso()


def smooth_skirt_back():
    """The skirt's back, from under the belt to over the hem, smoothed (Taubin, SKIRT_BACK_ROUNDS) as the torso: the
    hands held behind and the stepping legs left it bumpy with a crease down the middle - fussy for a broadcloth
    skirt that hangs plain. The hem's own line and the sleeves stay; then kept JOINT_CLEAR off the body."""
    from mathutils.bvhtree import BVHTree
    me = uni.data
    co = np.array([v.co[:] for v in me.vertices])
    nb = [[] for _ in range(len(co))]
    for e in me.edges:
        a, b = e.vertices
        nb[a].append(b); nb[b].append(a)
    low = P['HEM_Z']
    top = np.array([belt_z(P, c[0], c[1]) for c in co]) - P['BELT_H'] / 2 - 0.01  # its lower edge over each
    cy = P['BELT_C'][1]
    arm = arm_w(uni)
    k = np.array([smoothstep(c[2], low + 0.01, low + 0.05) * (1 - smoothstep(c[2], t - 0.03, t))
                  * smoothstep(c[1] - cy, -0.02, 0.04) * (1 - smoothstep(a, 0.15, 0.5))
                  for c, a, t in zip(co, arm, top)])
    zone = np.where(k > 0)[0]
    for _ in range(SKIRT_BACK_ROUNDS):
        for f in (0.6, -0.63):
            lap = np.array([co[nb[i]].mean(0) - co[i] if nb[i] else np.zeros(3) for i in zone])
            co[zone] += lap * (f * k[zone])[:, None]
    tree = BVHTree.FromPolygons([v.co.copy() for v in h.data.vertices], [tuple(p.vertices) for p in h.data.polygons])
    pushed = 0
    for i in zone:
        q = Vector(co[i])
        loc, nrm, _, _ = tree.find_nearest(q, 0.05)
        if loc is not None and (q - loc).dot(nrm) < JOINT_CLEAR:
            co[i] = loc + nrm * JOINT_CLEAR
            pushed += 1
    me.vertices.foreach_set('co', co.astype(np.float32).ravel())
    me.update()
    print('skirt back: %d cloth vertices smoothed, %d kept off the body' % (len(zone), pushed))


smooth_skirt_back()


def smooth_skirt_front():
    """The skirt's front by the closure, from under the belt to the hem: the closure's strip, held harder than the
    skirt beside it, came out of the simulation with creases running down along it, bunched up at the hem. There the
    cloth's move off the sheet as the armature alone puts it is smoothed (SKIRT_FRONT), and added back to that sheet:
    the creases go, the closure's step and the skirt's fall stay. Then kept JOINT_CLEAR off the body."""
    from mathutils.bvhtree import BVHTree
    me = uni.data
    co = np.array([v.co[:] for v in me.vertices])
    if len(co) != len(UNI_SKINNED):
        print('skirt front: the skinned sheet does not match, left as it is')
        return
    nb = [[] for _ in range(len(co))]
    for e in me.edges:
        a, b = e.vertices
        nb[a].append(b); nb[b].append(a)
    near, far, rounds = SKIRT_FRONT
    low = P['HEM_Z'] - 0.02
    top = np.array([belt_z(P, c[0], c[1]) for c in co]) - P['BELT_H'] / 2 - 0.01  # its lower edge over each
    cy = P['BELT_C'][1]
    arm = arm_w(uni)
    k = np.array([(1 - smoothstep(abs(c[0] - P['FLAP_X']), near, far)) * (1 - smoothstep(c[2], t - 0.03, t))
                  * smoothstep(c[2], low - 0.03, low) * (1 - smoothstep(c[1] - cy, -0.04, 0.0))
                  * (1 - smoothstep(a, 0.15, 0.5)) for c, a, t in zip(co, arm, top)])
    zone = np.where(k > 0)[0]
    d = co - UNI_SKINNED
    for _ in range(rounds):
        lap = np.array([d[nb[i]].mean(0) - d[i] if nb[i] else np.zeros(3) for i in zone])
        d[zone] += lap * (0.5 * k[zone])[:, None]
    co[zone] = UNI_SKINNED[zone] + d[zone]
    tree = BVHTree.FromPolygons([v.co.copy() for v in h.data.vertices], [tuple(p.vertices) for p in h.data.polygons])
    pushed = 0
    for i in zone:
        q = Vector(co[i])
        loc, nrm, _, _ = tree.find_nearest(q, 0.05)
        if loc is not None and (q - loc).dot(nrm) < JOINT_CLEAR:
            co[i] = loc + nrm * JOINT_CLEAR
            pushed += 1
    me.vertices.foreach_set('co', co.astype(np.float32).ravel())
    me.update()
    print('skirt front: %d cloth vertices evened, %d kept off the body' % (len(zone), pushed))


smooth_skirt_front()


def fit_shoulders():
    """Simulated, the tunic stood 1.5-2.2 cm off the shoulders' top beside the collar - a flat plateau that dropped
    onto the body in a step half way out - and swelled 2.5-3 cm over the shoulder joints: the shoulder's line ran
    straight, dipped and bulged again, and the epaulettes and their straps lay on that. The body's own line is a smooth
    convex curve from the neck down over the deltoid: over the shoulders' top (from the collar's foot out over the
    joints, down to the armpits) the tunic is laid SHOULDER_FIT_OFF off it, the move smoothed out into the cloth."""
    from mathutils.bvhtree import BVHTree
    outer = [bpy.data.objects[n] for n in ('Collar', 'CollarStand') if n in bpy.data.objects]
    O = np.array([(o.matrix_world @ v.co)[:] for o in outer for v in o.data.vertices])
    ax = O[:, :2].mean(0)
    nb_ = 72

    def bins(A):
        d = A[:, :2] - ax
        return np.floor((np.arctan2(d[:, 0], -d[:, 1]) + np.pi) / (2 * np.pi) * nb_).astype(int) % nb_
    ob = bins(O)
    rad = np.linalg.norm(O[:, :2] - ax, axis=1)
    foot = np.zeros(nb_)
    for k in range(nb_):
        sel = ob == k
        if sel.any():
            low = O[sel, 2].min()
            foot[k] = rad[sel & (O[:, 2] < low + 0.012)].max()
    foot = np.where(foot > 0, foot, foot.max())
    me = uni.data
    co = np.array([v.co[:] for v in me.vertices])
    nb = [[] for _ in range(len(co))]
    for e in me.edges:
        a, b = e.vertices
        nb[a].append(b); nb[b].append(a)
    bi = h.vertex_groups['body'].index  # the skin only: MPFB's helpers (tights, skirt) stand off it
    skin = {v.index for v in h.data.vertices if any(g.group == bi and g.weight > 0.5 for g in v.groups)}
    tree = BVHTree.FromPolygons([v.co.copy() for v in h.data.vertices],
                                [tuple(p.vertices) for p in h.data.polygons if all(i in skin for i in p.vertices)])
    ub = bins(co)
    r = np.linalg.norm(co[:, :2] - ax, axis=1)
    disp = np.zeros_like(co)
    k = np.zeros(len(co))
    for i, c in enumerate(co):
        if c[2] < SHOULDER_FIT_Z[0] or r[i] < foot[ub[i]]:
            continue
        loc, nrm, _, _ = tree.find_nearest(Vector(c), 0.08)
        if loc is None:
            continue
        w = smoothstep(c[2], *SHOULDER_FIT_Z) * smoothstep(nrm.z, *SHOULDER_FIT_NZ)
        w *= smoothstep(r[i] - foot[ub[i]], 0.0, SHOULDER_FIT_FROM)
        if w <= 0:
            continue
        k[i] = w
        disp[i] = (np.array((loc + nrm * SHOULDER_FIT_OFF)[:]) - c) * w
    zone = np.where(k > 0)[0]
    ring = set(zone)  # the move spread a few rings of neighbours further, fading
    for _ in range(4):
        ring |= {j for i in list(ring) for j in nb[i]}
    ring = np.array(sorted(ring))
    fixed = k > 0.5
    need = disp.copy()
    for _ in range(SHOULDER_FIT_ROUNDS):
        avg = np.array([disp[nb[i]].mean(0) if nb[i] else disp[i] for i in ring])
        disp[ring] = avg
        disp[fixed] = need[fixed]
    co = co + disp
    pushed = 0
    for i in ring:
        q = Vector(co[i])
        loc, nrm, _, _ = tree.find_nearest(q, 0.05)
        if loc is not None and (q - loc).dot(nrm) < JOINT_CLEAR:
            co[i] = loc + nrm * JOINT_CLEAR
            pushed += 1
    me.vertices.foreach_set('co', co.astype(np.float32).ravel())
    me.update()
    print('shoulders: %d cloth vertices laid on them (moved %.4f m at most), %d eased round, %d kept off the body' % (
        int(fixed.sum()), float(np.linalg.norm(need, axis=1).max()), len(ring), pushed))
    tu = BVHTree.FromPolygons([tuple(c) for c in co], [tuple(p.vertices) for p in me.polygons])
    for sg in (-1, 1):
        row = []
        for x in (0.10, 0.11, 0.12, 0.13, 0.14, 0.16, 0.18, 0.20, 0.22):
            a_ = tree.ray_cast(Vector((sg * x, 0.0, 2.2)), Vector((0, 0, -1)), 2)[0]
            b_ = tu.ray_cast(Vector((sg * x, 0.0, 2.2)), Vector((0, 0, -1)), 2)[0]
            row.append('%.2f:%s/%s' % (x, '%.1f' % ((a_.z - 1.6) * 100) if a_ else '-', '%.1f' % ((b_.z - 1.6) * 100) if b_ else '-'))
        print('  shoulder line skin/tunic', ' '.join(row))


fit_shoulders()


def uniform_in_collar(foot_only=False):
    """The tunic's own stand collar stays inside what is sewn over it: UNI_IN inside the gold collar's (and, in its
    front opening, the dark stand's) inner side, measured at each height (the collar flares out lower down), from a
    little under the collar's foot up; and no higher than just over the shirt collar's lower edge (the two lay on one
    radius). Simulated, its front edge and piping came out through the dark stand in the opening, its ragged top edge
    over the white shirt collar, and a fold through the collar's foot at the back."""
    import bmesh
    from mathutils.bvhtree import BVHTree
    outer = [bpy.data.objects[n] for n in ('Collar', 'CollarStand') if n in bpy.data.objects]
    shirt = bpy.data.objects.get('ShirtCollar')
    if not outer or shirt is None:
        return
    cb = bmesh.new()
    for o in outer:
        me = o.data.copy(); me.transform(o.matrix_world); cb.from_mesh(me); bpy.data.meshes.remove(me)
    tree = BVHTree.FromBMesh(cb)
    O = np.array([v.co[:] for v in cb.verts])
    cb.free()
    S_ = np.array([(shirt.matrix_world @ v.co)[:] for v in shirt.data.vertices])
    ax = O[:, :2].mean(0)
    nb = 72

    def bins(A):
        d = A[:, :2] - ax
        return np.floor((np.arctan2(d[:, 0], -d[:, 1]) + np.pi) / (2 * np.pi) * nb).astype(int) % nb
    ob, sb = bins(O), bins(S_)
    bot = np.array([O[ob == k, 2].min() if (ob == k).any() else np.nan for k in range(nb)])
    s_bot = np.array([S_[sb == k, 2].min() if (sb == k).any() else np.nan for k in range(nb)])
    while np.isnan(s_bot).any() and not np.isnan(s_bot).all():  # bins between its vertices (fewer than the bins: the
        # tunic there was left up through the shirt) from their neighbours
        s_bot = np.where(np.isnan(s_bot), np.fmin(np.roll(s_bot, 1), np.roll(s_bot, -1)), s_bot)
    me = uni.data
    co = np.array([v.co[:] for v in me.vertices])
    ub = bins(co)
    moved = 0
    for i in range(len(co)):
        k = ub[i]
        if np.isnan(bot[k]) or co[i, 2] < bot[k] - UNI_IN_BELOW or foot_only and co[i, 2] > bot[k] + UNI_FOOT_ONLY:
            continue
        d = Vector((co[i, 0] - ax[0], co[i, 1] - ax[1], 0.0))
        r = d.length
        if r < 1e-4 or r > 0.15:
            continue
        z = min(co[i, 2], s_bot[k] + UNI_IN_SHIRT) if not np.isnan(s_bot[k]) else co[i, 2]
        hit = None
        for up in range(UNI_FOOT_TRIES):  # under the foot here (it rises between the bin's lowest vertices): the
            # radius a little up it (narrower - the cone flares down); missed, a crease there stood out through it
            hit = tree.ray_cast(Vector((ax[0], ax[1], z + 0.002 * up)), d.normalized(), 0.2)[0]
            if hit is not None:
                break
        if hit is None:
            continue
        lim = (hit.xy - Vector(ax)).length - UNI_IN
        w = smoothstep(co[i, 2], bot[k] - UNI_IN_BELOW, bot[k])  # all in from the foot up (to 4 mm over it, a crease
        # risen to the foot stayed half out of it in a black knob)
        r_new = r + (min(r, lim) - r) * w
        if abs(r_new - r) > 1e-6 or z != co[i, 2]:
            co[i, :2] = ax + np.array(d.normalized().xy[:]) * r_new
            co[i, 2] = z
            moved += 1
    me.vertices.foreach_set('co', co.astype(np.float32).ravel())
    me.update()
    print('tunic stand collar: %d vertices taken in under the collar' % moved)
    return ax, s_bot + UNI_IN_SHIRT


UNI_CAP = uniform_in_collar()
activate(rig)
bpy.ops.object.mode_set(mode='POSE')
bpy.ops.pose.select_all(action='SELECT')
bpy.ops.pose.armature_apply(selected=False)
bpy.ops.object.mode_set(mode='OBJECT')
rig.animation_data_clear()
for pb in rig.pose.bones:
    pb.matrix_basis.identity()


def aim_eyes():
    """The eyeballs (build_head.py) turned in the stance: each from the face's own forward (its eye bone's) by
    pose.EYE_GAZE - set so that, seen square to the face, both irises sit alike in their openings (turned to the
    camera, through the openings' middles or the portrait's painted irises, the generated openings and balls being
    unalike, one iris sat by the nose or under the upper lid: a squint). The eye bones keep their rest; the eyeballs'
    mesh turns about them."""
    eyes = bpy.data.objects.get('Eyes')
    if eyes is None:
        return
    names = [g.name for g in eyes.vertex_groups]
    bones = {s: rig.data.bones['eye_' + s] for s in 'lr'}
    lat = (bones['l'].head_local - bones['r'].head_local).normalized()  # towards his left
    for s, b in bones.items():
        c = b.head_local
        f = (b.tail_local - c).normalized()
        yaw, pitch = (math.radians(a) for a in pose.EYE_GAZE[s])
        g = Quaternion(f.cross(lat).normalized(), yaw) @ f   # + towards his left
        g = Quaternion(lat, -pitch) @ g                      # + up
        q = f.rotation_difference(g)
        gi = names.index('eye_' + s)
        for v in eyes.data.vertices:
            if any(gr.group == gi and gr.weight > 0.5 for gr in v.groups):
                v.co = c + q @ (v.co - c)
        print('eye %s: turned %.1f deg to his left, %.1f up' % (s, *pose.EYE_GAZE[s]))
    eyes.data.update()

aim_eyes()


def neck_in_collar():
    """Nothing of the head in the collar's wall under its top edge: in the stance the head turns in the collar and the
    neck and the right whisker came out through it. Each head vertex under the collar's top (per direction round it)
    in its wall: nearer its outside, out to NECK_OUT over it (the beard and the whiskers' ends hang over the collar, as
    in the portrait - lifted over its edge, the beard's underside was a flat shelf with shards round it); nearer its
    inside, in to its inner side less NECK_IN, or up to NECK_OVER over the edge if just under it; the move spread
    smoothly over NECK_EASE round it (no crease)."""
    import bmesh
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    head = bpy.data.objects.get('Head')
    if head is None:
        return
    cb = bmesh.new()
    for n in ('Collar', 'CollarStand'):
        o = bpy.data.objects.get(n)
        if o:
            me = o.data.copy(); me.transform(o.matrix_world); cb.from_mesh(me); bpy.data.meshes.remove(me)
        if n == 'Collar':
            red = len(cb.verts)  # the red halves' vertices first: their tops are the edge (the dark stand between them
            # ends lower, under the shirt's white edge: taken as the edge, the throat was pulled out over it in a shelf)
    tree = BVHTree.FromBMesh(cb)
    cb.verts.ensure_lookup_table()
    ax = sum((v.co for v in cb.verts), Vector()) / len(cb.verts)
    zbot = min(v.co.z for v in cb.verts)
    tops, outer = {}, {}
    for v in cb.verts[:red]:
        k = int(math.degrees(math.atan2(v.co.x - ax.x, -(v.co.y - ax.y))) // 5)
        tops[k] = max(tops.get(k, 0.0), v.co.z)
    for v in cb.verts[:red]:  # its outside up by the top (it flares out lower down)
        k = int(math.degrees(math.atan2(v.co.x - ax.x, -(v.co.y - ax.y))) // 5)
        if v.co.z > tops[k] - 0.015:
            outer[k] = max(outer.get(k, 0.0), (v.co - ax).xy.length)
    cb.free()
    me = head.data
    co = np.array([v.co[:] for v in me.vertices])
    ed = np.array([e.vertices[:] for e in me.edges])
    disp = np.zeros_like(co)
    fixed = np.zeros(len(co), bool)
    zone = np.zeros(len(co), bool)
    for i, c in enumerate(co):
        if c[2] < zbot:
            continue
        d = Vector((c[0] - ax.x, c[1] - ax.y, 0.0))
        if d.length < 1e-4:
            continue
        kb = int(math.degrees(math.atan2(d.x, -d.y)) // 5)
        top = tops.get(kb, 0.0)
        if c[2] > top + NECK_EASE:
            continue
        zone[i] = True
        o = Vector((ax.x, ax.y, min(c[2], top - 0.003)))
        hit = tree.ray_cast(o, d.normalized(), 0.3)
        if hit[0] is None:
            continue
        allowed = (hit[0] - o).length - NECK_IN
        out_r = outer.get(kb, 0.0) + NECK_OUT
        if c[2] <= top and d.length > (allowed + NECK_IN + out_r) / 2:  # nearer the outside: out over it
            disp[i] = np.array(d.normalized()[:]) * max(out_r - d.length, 0.0)
            fixed[i] = True
        elif c[2] <= top + NECK_OVER and d.length > allowed:
            inward, upward = d.length - allowed, top + NECK_OVER - c[2]
            # just under the edge (the chin, the whiskers' ends) up over it - pulled in, the chin came out a cone;
            # deeper (the neck) in; between them blended by the depth (picked either way, they left a ragged edge)
            k = smoothstep(upward, *NECK_UP_DEPTH)
            disp[i] = (np.array([0.0, 0.0, upward]) * (1 - k) - np.array(d.normalized()[:]) * inward * k)
            fixed[i] = True
    need = disp.copy()
    deg = np.bincount(ed.ravel(), minlength=len(co)).astype(float)
    for _ in range(NECK_ROUNDS):  # spread the move over the eased band, the vertices that must go in held to it
        acc = np.zeros_like(disp)
        np.add.at(acc, ed[:, 0], disp[ed[:, 1]]); np.add.at(acc, ed[:, 1], disp[ed[:, 0]])
        avg = acc / np.maximum(deg, 1)[:, None]
        disp = np.where(zone[:, None], avg, 0.0)
        disp[fixed] = need[fixed]
    co = co + disp
    me.vertices.foreach_set('co', co.astype(np.float32).ravel()); me.update()
    print('neck in the collar: %d vertices went in (most %.4f m), %d eased' % (
        int(fixed.sum()), float(np.linalg.norm(need, axis=1).max()), int((np.linalg.norm(disp, axis=1) > 1e-4).sum())))


neck_in_collar()


def uniform_off_neck():
    """The tunic's stand at least NECK_CLEAR off the neck (its thickness goes inwards): after the simulation a corner
    of its closure's edge reached in through the throat, under the collar."""
    from mathutils.bvhtree import BVHTree
    head = bpy.data.objects.get('Head')
    if head is None:
        return
    hm = head.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
    tree = BVHTree.FromPolygons([head.matrix_world @ v.co for v in hm.vertices], [tuple(p.vertices) for p in hm.polygons])
    inv = uni.matrix_world.inverted()
    need = NECK_CLEAR + thick.thickness
    n = 0
    for v in uni.data.vertices:
        p = uni.matrix_world @ v.co
        if not 1.70 < p.z < 1.795:  # (not up by its top edge, where the whiskers' ends hang over the collar)
            continue
        loc, nrm, _, d = tree.find_nearest(p, need)
        if loc is None:
            continue
        s = (p - loc).dot(nrm)
        if s < need:
            v.co = inv @ (loc + nrm * need)
            n += 1
    uni.data.update()
    print('tunic off the neck: %d vertices moved out' % n)


uniform_off_neck()
for o in skinned:
    o.modifiers.new('Armature', 'ARMATURE').object = rig
uni.vertex_groups.remove(uni.vertex_groups['pin'])
thick.show_viewport = thick.show_render = True
uni.data.materials.append(uni.data.materials[0])  # the lining and edges get slot 1 (build_bake.py bakes the outside)
thick.material_offset = thick.material_offset_rim = 1
activate(uni)
bpy.ops.object.modifier_move_to_index(modifier='Thick', index=0)
bpy.ops.object.modifier_apply(modifier='Thick')


def uniform_under_shirt():
    """The tunic stand's thickness kept under the shirt collar too: its top, flattened under it (uniform_in_collar),
    faces down there, and the thickness laid inwards along that went up through the shirt in black jags."""
    if UNI_CAP is None:
        return
    ax, cap = UNI_CAP
    nb = len(cap)
    me = uni.data
    co = np.array([v.co[:] for v in me.vertices])
    d = co[:, :2] - ax
    k = np.floor((np.arctan2(d[:, 0], -d[:, 1]) + np.pi) / (2 * np.pi) * nb).astype(int) % nb
    a, a0, a1 = UNI_OPENING_DROP
    front = np.abs(np.arctan2(d[:, 0], -d[:, 1]))
    lim = cap[k] - a * (1 - np.clip((front - a0) / (a1 - a0), 0, 1))
    over = ~np.isnan(lim) & (np.hypot(d[:, 0], d[:, 1]) < 0.12) & (co[:, 2] > lim)
    co[over, 2] = lim[over]
    me.vertices.foreach_set('co', co.astype(np.float32).ravel()); me.update()
    print('tunic under the shirt collar: %d vertices lowered' % int(over.sum()))


UNI_CAP = uniform_in_collar(foot_only=True) or UNI_CAP  # again by the collar's foot on the settled cloth: settled,
# a crease over the shoulder stood up through the foot at his right in a black knob
uniform_under_shirt()  # (to the shirt as it stands now: by the one before the stance, the tunic's top stood over the
# shirt in the opening in red and black jags)
h.hide_set(True); h.hide_render = True
h.modifiers.remove(h.modifiers['ColliderMask'])
h.vertex_groups.remove(h.vertex_groups['collider'])
sc.frame_set(1)
sc['pose'] = dict(YAW_DEG=pose.YAW_DEG)
if 'BLINK_DEG' in sc['head'] and not sc['head'].get('LIDS_LOWERED'):  # the stance's lids are part closed
    hd = dict(sc['head']); hd['BLINK_DEG'] = hd['BLINK_DEG'] - min(pose.LID_DROP.values()); hd['LIDS_LOWERED'] = True; sc['head'] = hd
bpy.ops.outliner.orphans_purge(do_recursive=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
print('saved', OUT, os.path.getsize(OUT))

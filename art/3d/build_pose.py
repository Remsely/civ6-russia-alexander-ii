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

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pose  # noqa: E402

OUT = os.path.join(HERE, 'alexander_leader.blend')
POSE_FRAMES, SETTLE_FRAMES = 24, 24
BONES_ONLY = ('Boot', 'Sole', 'Spur')   # details that follow the bones, not the cloth
RIGID = ('Buttons', 'Buckle', 'CuffButtons')  # each piece of these moves as a whole with the cloth under it
SLEEVE_PIN = 0.5                        # sleeves held this much to the arm (less: they slide down and balloon)
# cloth: heavy broadcloth
CLOTH = dict(quality=8, mass=0.35, air_damping=1.0, tension_stiffness=40, compression_stiffness=40,
             shear_stiffness=20, bending_stiffness=6.0, tension_damping=8, compression_damping=8, shear_damping=8,
             pin_stiffness=4.0)
COLLIDE = dict(distance_min=0.004, self_distance_min=0.003, collision_quality=4)

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
thick = uni.modifiers['Thick']
thick.show_viewport = thick.show_render = False
activate(uni)  # Surface Deform binds only to convex faces
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.remove_doubles(threshold=0.0005)  # zero-length edges make the cloth solver explode
bpy.ops.mesh.dissolve_degenerate(threshold=0.0005)
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
    zc, top = P['BELT_ZC'], P['STAND_TOP_FRONT']
    for v in me.vertices:
        c = v.co
        g = {names[x.group]: x.weight for x in v.groups}
        arm = sum(x for n, x in g.items() if n.startswith(('upperarm', 'lowerarm', 'hand')))
        if part_v[v.index] == 2:  # trousers: the waistband and inside the boot shafts
            w[v.index] = max(0.05, smoothstep(c.z, P['WAIST_Z'] - 0.16, P['WAIST_Z'] - 0.08),
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
        chest = 0.35 if c.z > zc else 0.04   # torso / skirt
        w[v.index] = max(chest, belt, upper)
    g = uni.vertex_groups.get('pin') or uni.vertex_groups.new(name='pin')
    for i, x in enumerate(w):
        g.add([i], float(x), 'REPLACE')
    print('pin: %d free, %d pinned of %d' % (int((w < 0.2).sum()), int((w > 0.99).sum()), len(w)))


pin_weights()
cloth = uni.modifiers.new('Cloth', 'CLOTH')
cs = cloth.settings
for k, v in CLOTH.items():
    setattr(cs, k, v)
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


skinned = [o for o in sc.objects if o.type == 'MESH' and any(m.type == 'ARMATURE' for m in o.modifiers)]
for o in skinned:
    bake(o)
    if o.name in REST_CO:
        make_rigid(o)
activate(rig)
bpy.ops.object.mode_set(mode='POSE')
bpy.ops.pose.select_all(action='SELECT')
bpy.ops.pose.armature_apply(selected=False)
bpy.ops.object.mode_set(mode='OBJECT')
rig.animation_data_clear()
for pb in rig.pose.bones:
    pb.matrix_basis.identity()
for o in skinned:
    o.modifiers.new('Armature', 'ARMATURE').object = rig
uni.vertex_groups.remove(uni.vertex_groups['pin'])
thick.show_viewport = thick.show_render = True
uni.data.materials.append(uni.data.materials[0])  # the lining and edges get slot 1 (build_bake.py bakes the outside)
thick.material_offset = thick.material_offset_rim = 1
activate(uni)
bpy.ops.object.modifier_move_to_index(modifier='Thick', index=0)
bpy.ops.object.modifier_apply(modifier='Thick')
h.hide_set(True); h.hide_render = True
h.modifiers.remove(h.modifiers['ColliderMask'])
h.vertex_groups.remove(h.vertex_groups['collider'])
sc.frame_set(1)
sc['pose'] = dict(YAW_DEG=pose.YAW_DEG)
bpy.ops.outliner.orphans_purge(do_recursive=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
print('saved', OUT, os.path.getsize(OUT))

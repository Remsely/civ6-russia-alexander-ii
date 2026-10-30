# The finished leader out to the game: FBX for tools/fbx_to_fgx.ps1 (the Firaxis FBX importer), then
# art/3d/make_leader_asset.py writes the .geo, .anm, .ast, materials and textures around the .fgx files.
#
# blender -b art/3d/alexander_leader.blend --python art/3d/export_leader.py -- geometry
# blender -b art/3d/alexander_leader.blend --python art/3d/export_leader.py -- animation
#
# geometry:  art/build/export/AlexanderII.fbx - root empty, the rig and every rendered mesh beside it (the layout the
#            importer walks), in the rest pose (= the stance), triangulated, one material = one triangle group per
#            mesh, at most 4 bones a vertex; AlexanderII.json - what the .geo lists (meshes, groups, counts, bones).
# animation: art/build/export/AlexanderII_Idle.fbx - root and rig only, the idle loop (tools/blender/motion.py, the loose
#            pieces simulated, 24 fps) retimed to 30 fps as the vanilla leaders' and baked a key a frame, frame 1
#            repeated after the last so the loop closes on itself.
# Leader space (see .claude/skills/civ6-asset-pipeline): centimetres, Z up, facing +X; the figure turned by 90 deg plus
# the pose's YAW_DEG and scaled TARGET_CM tall, exactly as render_leader.py and motion.camera place it. The importer
# reads raw FBX values, so the map is baked into the data. The .blend is not saved.
import bpy, bmesh, json, math, os, sys
import numpy as np
from mathutils import Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools', 'blender'))
import motion  # noqa: E402

OUT = os.path.join(HERE, '..', 'build', 'export')
ROOT = 'AlexanderII'  # the root node: the .geo's model name and the animation's track group (bones: Root is taken)
PREFIX = 'LEAD_REMSELY_ALEXANDER_II_'  # Civ VI material = triangle group: PREFIX + the Blender material's part name
PARTS = {'Uniform_Cloth': 'Uniform', 'Body_Skin': 'Hands', 'Head_Skin': 'Head', 'Eyes': 'Eyes',
         'Details': 'Details', 'Regalia': 'Regalia', 'Orders': 'Orders'}
MAX_BONES = 4  # bones a vertex (the rest pose does not depend on the weights; only motion does)
# Triangles with no UV area (a part painted one colour from an atlas swatch, so all its UVs on one point, or slivers along
# an island's edge) and with no area at all give the importer's tangents 0/0: NaN in the shader blanks the whole leader
# and blows out the scene's exposure. Such UVs are spread around their point by the mesh's own smart projection, as far
# as the atlas keeps that point's colour (SPREAD_MAX texels at most; HALF_TEXEL for slivers and colour edges).
ALBEDO = {'Uniform': 'uniform', 'Hands': 'hands', 'Head': 'head', 'Eyes': 'eye', 'Details': 'details',
          'Regalia': 'regalia', 'Orders': 'orders'}  # art/3d/textures/<name>_albedo.png
SPREAD_MAX, HALF_TEXEL, COLOUR_TOL = 12, 0.5, 6 / 255
MIN_UV_AREA, MIN_AREA = 1e-12, 1e-12  # UV units^2, m^2
GAME_FPS = 30  # LEAD_RUSS_Peter_*.fgx: TimeStep 1/30 s
FBX = dict(apply_scale_options='FBX_SCALE_UNITS',  # root scale stays 1 (FBX_SCALE_NONE gives the root a x100 scale)
           axis_forward='Y', axis_up='Z', bake_space_transform=False,  # raw Blender axes = leader space
           add_leaf_bones=False, use_armature_deform_only=True)

# Smooth skinning through the Firaxis importer (FbxImporter.dll, read off its code: 0x5be40, 0x6b680, 0x6b5a0).
# Blender writes the Skin deformer with no SkinningType = eRigid: each vertex then goes wholly to the first cluster that
# holds it, whatever the weights (the jaw, the coat's skirts, the epaulettes' arms were lost). For any other type the
# importer takes a vertex's influence count from the times it appears in the Skin's own Indexes array (which the FBX
# SDK reads only for SkinningType "Blend"; with "Linear" every vertex had none and fell to bone 0), and its k-th
# influence from the first cluster (in cluster order) that holds the vertex k+1 times, with the weight of that (k+1)-th
# entry. So: "Blend"; each vertex in the Skin's Indexes once per bone; and in the cluster of its j-th bone (bones in
# cluster order) j+1 times, all with that bone's weight. BlendWeights (the linear/dual-quaternion mix) all 0: unused.
from io_scene_fbx import export_fbx_bin as _fbx_bin  # noqa: E402
_f64, _i32s, _f64s, _arm_elems = (_fbx_bin.elem_data_single_float64, _fbx_bin.elem_data_single_int32_array,
                                  _fbx_bin.elem_data_single_float64_array, _fbx_bin.fbx_data_armature_elements)
_skins = []  # [Skin element, [[cluster element, indexes, weights], ...] in the order written]


def _skin_type(elem, name, value):
    e = _f64(elem, name, value)
    if name == b'Link_DeformAcuracy':  # written once per Skin deformer, its clusters next
        _fbx_bin.elem_data_single_string(elem, b'SkinningType', b'Blend')
        _skins.append([elem, []])
    return e


def _cluster_indexes(elem, name, value):
    if name == b'Indexes' and _skins:
        _skins[-1][1].append([elem, list(value), None])
        return None  # rewritten in _skin_indexes
    return _i32s(elem, name, value)


def _cluster_weights(elem, name, value):
    if name == b'Weights' and _skins and _skins[-1][1] and _skins[-1][1][-1][0] is elem:
        _skins[-1][1][-1][2] = list(value)
        return None
    return _f64s(elem, name, value)


def _skin_indexes(root, arm_obj, scene_data):
    _arm_elems(root, arm_obj, scene_data)
    for skin, clusters in _skins:
        bones = {}  # vertex -> [(cluster, weight)] in cluster order
        for c, (_, idx, w) in enumerate(clusters):
            for v, x in zip(idx, w):
                bones.setdefault(v, []).append((c, x))
        out = [([], []) for _ in clusters]
        for v, bw in bones.items():
            for j, (c, x) in enumerate(bw):
                out[c][0].extend([v] * (j + 1))
                out[c][1].extend([x] * (j + 1))
        for (elem, _, _), (idx, w) in zip(clusters, out):
            _i32s(elem, b'Indexes', idx)
            _f64s(elem, b'Weights', w)
        sk = [v for v in sorted(bones) for _ in bones[v]]
        _i32s(skin, b'Indexes', sk)
        _f64s(skin, b'BlendWeights', [0.0] * len(sk))
    _skins.clear()


_fbx_bin.elem_data_single_float64 = _skin_type
_fbx_bin.elem_data_single_int32_array = _cluster_indexes
_fbx_bin.elem_data_single_float64_array = _cluster_weights
_fbx_bin.fbx_data_armature_elements = _skin_indexes

mode = sys.argv[sys.argv.index('--') + 1] if '--' in sys.argv else 'geometry'
sc = bpy.data.scenes['Human']
bpy.context.window.scene = sc
rig = next(o for o in sc.objects if o.type == 'ARMATURE')
meshes = [o for o in sc.objects if o.type == 'MESH' and not o.hide_render]
# geometry -- Name1,Name2: only these meshes in the FBX (the figure's size and placement still from all of them),
# to find which part the game will not take
ONLY = sys.argv[sys.argv.index('--') + 2].split(',') if mode == 'geometry' and len(sys.argv) > sys.argv.index('--') + 2 else None
os.makedirs(OUT, exist_ok=True)

# the same map as motion.camera: rest-pose mesh data of everything rendered
pts = [o.matrix_world @ v.co for o in meshes for v in o.data.vertices]
z0, z1 = min(p.z for p in pts), max(p.z for p in pts)
YAW = float(sc.get('pose', {}).get('YAW_DEG', 0.0))
S = motion.TARGET_CM / (z1 - z0)
LEADER = Matrix.Rotation(math.radians(90 + YAW), 4, 'Z') @ Matrix.Scale(S, 4)
print('height %.4f m -> %.0f cm (x%.3f), yaw %.1f' % (z1 - z0, motion.TARGET_CM, S, YAW))


def select(objs, active=None):
    for o in bpy.context.view_layer.objects:
        o.select_set(o in objs)
    bpy.context.view_layer.objects.active = active or objs[0]


def to_leader(objs):
    for o in objs:
        o.matrix_world = LEADER @ o.matrix_world
    select(objs)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def root_over(objs):
    root = bpy.data.objects.new(ROOT, None)
    sc.collection.objects.link(root)
    for o in objs:
        mw = o.matrix_world.copy()
        o.parent = root
        o.matrix_world = mw
    return root


_albedo = {}


def albedo(part):
    if part not in _albedo:
        img = bpy.data.images.load(os.path.join(HERE, 'textures', ALBEDO[part] + '_albedo.png'))
        a = np.empty(img.size[0] * img.size[1] * 4, np.float32)
        img.pixels.foreach_get(a)
        _albedo[part] = a.reshape(img.size[1], img.size[0], 4)[..., :3]  # rows bottom-up, as UV v
        bpy.data.images.remove(img)
    return _albedo[part]


def flat_radius(part, uv):
    """Texels round uv the atlas keeps its colour (SPREAD_MAX at most)."""
    a = albedo(part)
    h, w = a.shape[:2]
    x, y = min(int(uv[0] * w), w - 1), min(int(uv[1] * h), h - 1)
    r = 0
    while r < SPREAD_MAX:
        blk = a[max(0, y - r - 1):y + r + 2, max(0, x - r - 1):x + r + 2]
        if np.abs(blk - a[y, x]).max() > COLOUR_TOL:
            break
        r += 1
    return max(r, HALF_TEXEL), w


def uv_area(a, b, c):
    return abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) / 2


def open_uvs(me, part):
    """No triangle without area or UV area (see MIN_UV_AREA); returns (zero-area dropped, UV-spread) counts."""
    flat = [p.index for p in me.polygons if p.area < MIN_AREA]
    if flat:
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.faces.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[bm.faces[i] for i in flat], context='FACES_ONLY')
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
        bm.to_mesh(me)
        bm.free()
    uv = me.uv_layers[0].data
    bad = [p for p in me.polygons if uv_area(*[uv[i].uv for i in p.loop_indices]) < MIN_UV_AREA]
    if bad:
        w = albedo(part).shape[1]
        lo = [min(v.co[k] for v in me.vertices) for k in range(3)]
        size = max(max(v.co[k] for v in me.vertices) - lo[k] for k in range(3))
        jitter = ((0, 0), (HALF_TEXEL / w, 0), (0, HALF_TEXEL / w))
        for p in bad:
            pts = [tuple(uv[i].uv) for i in p.loop_indices]
            if max(pts) == min(pts):
                # one colour: a box projection of the face (on its dominant axis' plane) round the point, as far as
                # the atlas keeps the colour; neighbours on the same plane stay joined
                span = 2 * flat_radius(part, pts[0])[0] / w
                ax = max(range(3), key=lambda k: abs(p.normal[k]))
                a, b = [k for k in range(3) if k != ax]
                for i in p.loop_indices:
                    co = me.vertices[me.loops[i].vertex_index].co
                    uv[i].uv = (pts[0][0] + ((co[a] - lo[a]) / size - 0.5) * span,
                                pts[0][1] + ((co[b] - lo[b]) / size - 0.5) * span)
            if uv_area(*[uv[i].uv for i in p.loop_indices]) < MIN_UV_AREA:
                # a sliver along an island's edge (or a face the projection sees edge-on): a half-texel triangle
                for i, o, (du, dv) in zip(p.loop_indices, pts, jitter):
                    uv[i].uv = (o[0] + du, o[1] + dv)
            if uv_area(*[uv[i].uv for i in p.loop_indices]) < MIN_UV_AREA:
                for i, (du, dv) in zip(p.loop_indices, jitter):
                    uv[i].uv = (pts[0][0] + du, pts[0][1] + dv)
    left = sum(1 for p in me.polygons if uv_area(*[uv[i].uv for i in p.loop_indices]) < MIN_UV_AREA)
    assert not left, '%d faces still without UV area' % left
    return len(flat), len(bad)


SECOND_WEIGHT = 0.01  # above the importer's 8-bit weight step (1/255), too little to see


def second_bone(ob):
    """A mesh skinned to one bone only gets a second (its parent's) on one vertex, 1 %: with a single bone the leader
    crashed the game on the diplomacy screen, even in the skinned vertex format; every two-bone mesh renders."""
    deform = {b.name for b in rig.data.bones if b.use_deform}
    names = {g.index: g.name for g in ob.vertex_groups}
    used = {names[g.group] for v in ob.data.vertices for g in v.groups if g.weight > 0 and names[g.group] in deform}
    if len(used) != 1:
        return None
    bone = rig.data.bones[used.pop()]
    par = bone.parent
    while par is not None and not par.use_deform:
        par = par.parent
    other = par.name if par else next(b.name for b in rig.data.bones if b.use_deform and b.name != bone.name)
    g = ob.vertex_groups.get(other) or ob.vertex_groups.new(name=other)
    g.add([0], SECOND_WEIGHT, 'REPLACE')
    ob.vertex_groups[bone.name].add([0], 1.0 - SECOND_WEIGHT, 'REPLACE')
    return other


MERGE_VERTS = 40000  # vertices of a merged mesh at most, as the importer counts them (corners + ~15 % tangent splits)


def game_verts(ob):
    me = ob.data
    uv = me.uv_layers.active.data
    corners = {(l.vertex_index, tuple(round(c, 6) for c in uv[l.index].uv)) for l in me.loops}
    return int(len(corners) * 1.15)


def merge(out):
    """The meshes of one material joined, first fit by size under MERGE_VERTS: the 36 parts as separate meshes left the
    leader unloaded (its first 18 loaded; Peter's body is 9 meshes), and fewer meshes are fewer draw calls."""
    by_mat = {}
    for ob in out:
        by_mat.setdefault(ob.data.materials[0].name, []).append(ob)
    merged = []
    for mat, obs in by_mat.items():
        bins = []
        for ob in sorted(obs, key=game_verts, reverse=True):
            n = game_verts(ob)
            b = next((b for b in bins if b[0] + n <= MERGE_VERTS), None)
            if b:
                b[0] += n
                b[1].append(ob)
            else:
                bins.append([n, [ob]])
        part = mat[len(PREFIX):]
        for i, (n, group) in enumerate(bins):
            names = [o.name for o in group]
            if len(group) > 1:
                select(group, group[0])
                bpy.ops.object.join()
            ob = group[0]
            ob.name = part if len(bins) == 1 else '%s%d' % (part, i + 1)
            print('merged %-10s ~%5d verts: %s' % (ob.name, n, ', '.join(names)))
            merged.append(ob)
    return merged


def geometry():
    rig.data.pose_position = 'REST'
    rig.animation_data_clear()
    out, info = [], {'model': ROOT, 'meshes': []}
    for o in meshes:
        if ONLY and o.name not in ONLY:
            continue
        part = PARTS[o.active_material.name]
        tri = o.modifiers.new('_tri', 'TRIANGULATE')
        tri.keep_custom_normals = True
        tri.quad_method, tri.ngon_method = 'BEAUTY', 'BEAUTY'
        dg = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
        o.modifiers.remove(tri)
        me.transform(o.matrix_world)
        fixed = open_uvs(me, part)
        me.materials.clear()
        mat = bpy.data.materials.get(PREFIX + part) or bpy.data.materials.new(PREFIX + part)
        me.materials.append(mat)
        name = o.name
        o.name = name + '_src'
        ob = bpy.data.objects.new(name, me)
        sc.collection.objects.link(ob)
        for vg in o.vertex_groups:
            ob.vertex_groups.new(name=vg.name)
        ob.modifiers.new('Armature', 'ARMATURE').object = rig
        select([ob])
        bpy.ops.object.vertex_group_limit_total(group_select_mode='BONE_DEFORM', limit=MAX_BONES)
        bpy.ops.object.vertex_group_normalize_all(group_select_mode='BONE_DEFORM', lock_active=False)
        second = second_bone(ob)
        print('%-20s %-8s mods %s, dropped %d zero-area, spread %d UV%s' % ((name, part, [m.type for m in o.modifiers]) + fixed
                                                                            + (', second bone ' + second if second else '',)))
        out.append(ob)
    for o in meshes:
        bpy.data.objects.remove(o)
    out = merge(out)
    to_leader([rig] + out)
    root = root_over([rig] + out)
    bones = {b.name for b in rig.data.bones if b.use_deform}
    for ob in out:
        me = ob.data
        uv = me.uv_layers.active.data
        corners = {(l.vertex_index, tuple(round(c, 6) for c in uv[l.index].uv),
                    tuple(round(c, 4) for c in me.corner_normals[l.index].vector)) for l in me.loops}
        used = {ob.vertex_groups[g.group].name for v in me.vertices for g in v.groups if g.weight > 0}
        info['meshes'].append(dict(name=ob.name, group=me.materials[0].name, tris=len(me.polygons),
                                   verts=len(corners), bound_bones=len(used & bones)))
    # nodes in hierarchy order, as the importer makes them skeleton bones
    order, todo = [], [root]
    while todo:
        n = todo.pop(0)
        order.append(n.name)
        if n is rig:
            stack = [b for b in rig.data.bones if b.parent is None]
            while stack:
                b = stack.pop(0)
                if b.use_deform:
                    order.append(b.name)
                stack[:0] = list(b.children)
        else:
            todo += sorted(n.children, key=lambda c: (c.type != 'ARMATURE', c.name))
    info['bones'] = order
    select([root, rig] + out, rig)
    path = os.path.join(OUT, ROOT + '.fbx')
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={'EMPTY', 'ARMATURE', 'MESH'},
                             use_mesh_modifiers=False, mesh_smooth_type='FACE', use_tspace=True, bake_anim=False, **FBX)
    with open(os.path.join(OUT, ROOT + '.json'), 'w', encoding='utf-8') as f:
        json.dump(info, f, indent=1)
    print('exported', path, os.path.getsize(path), '%d meshes, %d tris' % (len(out), sum(m['tris'] for m in info['meshes'])))


def animation():
    n = motion.apply(sc, rig, 'idle')
    act = rig.animation_data.action
    # the loop closes on itself: frame n + 1 is frame 1 again (the springs were wound up to meet it)
    for fc in act.fcurves:
        fc.keyframe_points.insert(n + 1, fc.evaluate(1), options={'FAST'})
        fc.update()
    # retimed to the game's rate (vanilla leader animations: a key every 1/30 s), the same seconds
    k = GAME_FPS / motion.FPS
    for fc in act.fcurves:
        for kp in fc.keyframe_points:
            for p in (kp.co, kp.handle_left, kp.handle_right):
                p[0] = 1 + (p[0] - 1) * k
        fc.update()
    last = round(1 + n * k)
    sc.render.fps, sc.render.fps_base = GAME_FPS, 1.0
    to_leader([rig])
    # a uniform scale S and a rotation R of rest and pose alike leave each bone's own rotation as it was and scale its
    # own translation by S (basis' = S basis S^-1)
    for fc in act.fcurves:
        if fc.data_path.endswith('.location'):
            for k in fc.keyframe_points:
                for p in (k.co, k.handle_left, k.handle_right):
                    p[1] *= S
            fc.update()
    root = root_over([rig])
    sc.frame_start, sc.frame_end = 1, last
    select([root, rig], rig)
    path = os.path.join(OUT, ROOT + '_Idle.fbx')
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={'EMPTY', 'ARMATURE'}, bake_anim=True,
                             bake_anim_use_all_actions=False, bake_anim_use_nla_strips=False,
                             bake_anim_force_startend_keying=True, bake_anim_step=1.0, bake_anim_simplify_factor=0.0,
                             **FBX)
    with open(os.path.join(OUT, ROOT + '_Idle.json'), 'w', encoding='utf-8') as f:
        json.dump({'frames': last - 1, 'fps': GAME_FPS, 'duration': n / motion.FPS}, f)
    print('exported', path, os.path.getsize(path), 'frames 1..%d at %d fps (%.3f s)' % (last, GAME_FPS, n / motion.FPS))


{'geometry': geometry, 'animation': animation}[mode]()

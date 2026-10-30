# Pipeline smoke test: export the MPFB human (scene 'Human' in alexander_assembly.blend) for the Civ VI Asset Editor.
# blender -b art/3d/alexander_assembly.blend --python art/3d/test/export_test_fbx.py
# Firaxis importer needs: a material per triangle group, triangles, one root node holding skeleton + meshes.
import bpy, math, os
from mathutils import Matrix

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'LEAD_REMSELY_TEST.fbx')
ROOT = 'LEAD_REMSELY_TEST'

sc = bpy.data.scenes['Human']
bpy.context.window.scene = sc
h, rig = bpy.data.objects['Human'], bpy.data.objects['HumanRig']
print('mats', [m and m.name for m in h.data.materials], 'mods', [m.type for m in h.modifiers],
      'parent', h.parent and h.parent.name)

# The idle pose (arms down, frame 1) becomes the rest pose: Blender's FBX exporter drops constant channels, so a pose
# held only by constant keys never reaches the animation. The action keeps just the motion relative to frame 1.
# Not saved back to the .blend: the script always starts from the MPFB A-pose rig.
sc.frame_set(1)
dg = bpy.context.evaluated_depsgraph_get()
me = bpy.data.meshes.new_from_object(h.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
me.name = 'LEAD_REMSELY_TEST_Body'
act = rig.animation_data.action
base = {(fc.data_path, fc.array_index): fc.evaluate(1) for fc in act.fcurves}
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode='POSE')
bpy.ops.pose.armature_apply(selected=False)
bpy.ops.object.mode_set(mode='OBJECT')
GAIN = 3.0  # breathing exaggerated for the smoke test, so it is visible in the previewer
for fc in act.fcurves:
    b = base[(fc.data_path, fc.array_index)]
    for k in fc.keyframe_points:
        k.co[1] = (k.co[1] - b) * GAIN
        k.handle_left[1] = k.handle_right[1] = k.co[1]
    fc.update()
sc.frame_set(1)
for old in [o for o in bpy.data.objects if o.name.startswith('Body')]:
    bpy.data.objects.remove(old)
body = bpy.data.objects.new('Body', me)
sc.collection.objects.link(body)
for vg in h.vertex_groups:
    body.vertex_groups.new(name=vg.name)
m = body.modifiers.new('Armature', 'ARMATURE'); m.object = rig
mat = bpy.data.materials.get('LEAD_REMSELY_TEST_Skin') or bpy.data.materials.new('LEAD_REMSELY_TEST_Skin')
me.materials.clear(); me.materials.append(mat)
tri = body.modifiers.new('Tri', 'TRIANGULATE')
print('body verts', len(me.vertices), 'groups', len(body.vertex_groups))

root = bpy.data.objects.get(ROOT) or bpy.data.objects.new(ROOT, None)
if root.name not in sc.collection.objects:
    sc.collection.objects.link(root)
# Maya-style layout the Firaxis importer walks: root -> (skeleton, mesh) as siblings, skinning via the modifier
rig.parent = root
body.parent = root
body.matrix_world = h.matrix_world.copy()

# Civ VI leader space (from LEAD_RUSS_Peter_Camera.fgx): centimetres, Z up, the leader faces +X (camera at x=320).
# The importer takes raw FBX values, so bake it into the data: MPFB faces -Y -> rotate +90 deg about Z, metres -> cm.
# Fit Peter's framing (his camera, no lens data in our own): Peter stands ~158 cm tall in leader space (estimated from
# in-game screenshots: frame spans ~56..165 cm at x=0), so the model is scaled to TARGET_CM whatever its MPFB height.
TARGET_CM = 150.0  # 160 cut off the top of the head
zs = [(h.matrix_world @ v.co).z for v in me.vertices]
height_m = max(zs) - min(zs)
print('model height %.3f m -> %.0f cm' % (height_m, TARGET_CM))
LEADER_SPACE = Matrix.Rotation(math.radians(90), 4, 'Z') @ Matrix.Scale(TARGET_CM / height_m, 4)
for o in (rig, body):
    o.matrix_world = LEADER_SPACE @ o.matrix_world
for o in sc.objects:
    o.select_set(o in (rig, body))
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

FBX = dict(apply_scale_options='FBX_SCALE_UNITS',  # root scale stays 1 (FBX_SCALE_NONE gives the root a x100 scale)
           axis_forward='Y', axis_up='Z', bake_space_transform=False,  # raw Blender axes = leader space
           add_leaf_bones=False, use_armature_deform_only=True, bake_anim=True, bake_anim_use_all_actions=False,
           bake_anim_use_nla_strips=False, bake_anim_simplify_factor=0.0)
for o in sc.objects:
    o.select_set(o in (root, rig, body))
bpy.context.view_layer.objects.active = rig
bpy.ops.export_scene.fbx(filepath=OUT, use_selection=True, object_types={'EMPTY', 'ARMATURE', 'MESH'},
                         use_mesh_modifiers=True, mesh_smooth_type='FACE', use_tspace=False, **FBX)
print('exported', OUT, os.path.getsize(OUT))

# Animation-only file (root + skeleton, no mesh): with a mesh inside, the Asset Editor routes an animation import through
# the geometry exporter and crashes in ParseWigFiles.
OUT_ANIM = OUT.replace('.fbx', '_Anim.fbx')
for o in sc.objects:
    o.select_set(o in (root, rig))
bpy.ops.export_scene.fbx(filepath=OUT_ANIM, use_selection=True, object_types={'EMPTY', 'ARMATURE'}, **FBX)
print('exported', OUT_ANIM, os.path.getsize(OUT_ANIM))

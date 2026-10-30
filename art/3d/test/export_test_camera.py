# Pipeline smoke test: leader camera for the Asset Editor (like LEAD_RUSS_Peter_Camera: root node + node 'LeaderCamera').
# blender -b art/3d/alexander_assembly.blend --python art/3d/test/export_test_camera.py
# Leader space and camera convention read from LEAD_RUSS_Peter_Camera.fgx (tools/dump_fgx.ps1): centimetres, Z up,
# leader faces +X; 'LeaderCamera' at (320, 0, 137.741) looks down its local -Z (tilted 4.9 deg down), local +Y up.
import bpy, os
from mathutils import Vector

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'LEAD_REMSELY_TEST_Camera.fbx')
EYE = Vector((320.0, 0.0, 137.741))   # Peter's camera, exactly
TARGET = Vector((0.0, 0.0, 110.39))   # along his view direction (-0.996, 0, -0.085)

sc = bpy.data.scenes['Human']
bpy.context.window.scene = sc
for name in ('LeaderCamera', 'LEAD_REMSELY_TEST_Camera'):
    if name in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects[name])
root = bpy.data.objects.new('LEAD_REMSELY_TEST_Camera', None)
cam = bpy.data.objects.new('LeaderCamera', None)
for o in (root, cam):
    sc.collection.objects.link(o)
cam.parent = root
cam.empty_display_type = 'ARROWS'
cam.location = EYE
cam.rotation_mode = 'QUATERNION'
cam.rotation_quaternion = (TARGET - EYE).to_track_quat('-Z', 'Y')

for o in sc.objects:
    o.select_set(o in (root, cam))
bpy.ops.export_scene.fbx(filepath=OUT, use_selection=True, object_types={'EMPTY'},
                         apply_scale_options='FBX_SCALE_UNITS', bake_anim=False,  # FBX_SCALE_NONE gives the root a x100 scale
                         axis_forward='Y', axis_up='Z', bake_space_transform=False)
print('exported', OUT, os.path.getsize(OUT))

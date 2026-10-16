# What the diplomacy screen shows: a render from Peter's leader camera, with the model placed the way the export puts
# it into leader space. Compare this, not the viewport, with the reference portrait.
# python tools/blend.py render art/3d/alexander_leader.blend [--scene Human] [--out shot.png] [--frame N]
#        [--target-cm 150] [--res 1280x720] [--transparent] [--samples 32]
# The .blend is not saved. Prints the output path and where the model's top and bottom fall in the frame
# (0 = bottom edge, 1 = top edge) between RENDER_BEGIN / RENDER_END.
#
# Leader space (LEAD_RUSS_Peter_Camera.fgx, see .claude/skills/civ6-asset-pipeline): centimetres, Z up, the leader
# faces +X; 'LeaderCamera' at (320, 0, 137.741) looks at (0, 0, 110.39). The export (art/3d/test/export_test_fbx.py)
# maps MPFB space (metres, faces -Y) into it by rotating +90 deg about Z and scaling the model to TARGET_CM tall.
# Here the camera is brought into MPFB space by the inverse of that map, so the scene itself is left as it is.
# Lens: not in the camera .fgx; vertical FOV 19.2 deg is estimated from in-game screenshots of Peter (the frame spans
# ~56..165 cm at x=0). The game's own lights are not reproduced: a neutral key/fill/rim rig.
import bpy, math, os, sys, argparse
from mathutils import Vector, Matrix
from bpy_extras.object_utils import world_to_camera_view

EYE = Vector((320.0, 0.0, 137.741))
TARGET = Vector((0.0, 0.0, 110.39))
VFOV_DEG = 19.2
REF_SIZE, REF_CROWN, REF_SOLES, REF_X = (1024, 1536), 12, 1510, 515  # alexander_ii_full.png: px of the crown, soles, midline

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser(prog='render_leader.py')
ap.add_argument('--scene')
ap.add_argument('--out', default=os.path.join('art', 'build', 'leader_camera.png'))
ap.add_argument('--frame', type=int)
ap.add_argument('--target-cm', type=float, default=150.0, help='model height in leader space, as in the export')
ap.add_argument('--res', default='1280x720')
ap.add_argument('--samples', type=int, default=32)
ap.add_argument('--transparent', action='store_true')
ap.add_argument('--views', help='comma list instead of the game shot: full<yaw>, bust<yaw>, head<yaw> (yaw in degrees round the '
                'model, 0 = front, 90 = his left side, 180 = back; @deg - camera elevation, default 3), e.g. full0,full45,full90,full180,head0,head45,head90; '
                'ref - orthographic front framed like art/source/alexander_ii_full.png (1024x1536, crown at REF_CROWN px, soles '
                'at REF_SOLES px) for an overlay on it; each goes to <out stem>_<view>.png')
ap.add_argument('--hide', help='comma list of objects (name prefixes) left out of the render, e.g. Collar,Uniform')
args = ap.parse_args(argv)

sc = bpy.data.scenes[args.scene] if args.scene else bpy.context.scene
if bpy.context.window:
    bpy.context.window.scene = sc
if args.frame is not None:
    sc.frame_set(args.frame)

for o in sc.objects:
    if args.hide and o.name.startswith(tuple(args.hide.split(','))):
        o.hide_render = True
meshes = [o for o in sc.objects if o.type == 'MESH' and not o.hide_render]
dg = bpy.context.evaluated_depsgraph_get()
pts = []
for o in meshes:
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    pts += [ev.matrix_world @ v.co for v in me.vertices]
    ev.to_mesh_clear()
z0, z1 = min(p.z for p in pts), max(p.z for p in pts)
height = z1 - z0
leader = Matrix.Rotation(math.radians(90), 4, 'Z') @ Matrix.Scale(args.target_cm / height, 4)
to_model = leader.inverted()

for name in ('_LeaderCam', '_Key', '_Fill', '_Rim'):
    if name in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects[name])
cam_data = bpy.data.cameras.new('_LeaderCam')
cam_data.sensor_fit = 'VERTICAL'
cam_data.angle_y = math.radians(VFOV_DEG)
cam_data.clip_start, cam_data.clip_end = 0.01, 100.0
cam = bpy.data.objects.new('_LeaderCam', cam_data)
sc.collection.objects.link(cam)
cam.rotation_mode = 'QUATERNION'
sc.camera = cam


def aim(eye, target):
    """Camera at eye looking at target, both in leader space (cm)."""
    cam.location = to_model @ eye
    rot = (target - eye).to_track_quat('-Z', 'Y')
    cam.rotation_quaternion = Matrix.Rotation(math.radians(-90), 4, 'Z').to_quaternion() @ rot
    bpy.context.view_layer.update()


aim(EYE, TARGET)


def light(name, kind, energy, loc_leader, size=1.0):
    d = bpy.data.lights.new(name, kind)
    d.energy = energy
    if kind == 'AREA':
        d.size = size
    o = bpy.data.objects.new(name, d)
    sc.collection.objects.link(o)
    o.location = to_model @ Vector(loc_leader)
    o.rotation_mode = 'QUATERNION'
    o.rotation_quaternion = (to_model @ Vector((0, 0, 120)) - o.location).to_track_quat('-Z', 'Y')


# Leader space positions (cm): key front-left high, fill front-right low, rim behind
light('_Key', 'AREA', 400, (250, 150, 260), 1.5)
light('_Fill', 'AREA', 120, (250, -180, 120), 2.0)
light('_Rim', 'AREA', 250, (-150, -60, 230), 1.0)

for engine in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
    try:
        sc.render.engine = engine
        break
    except TypeError:
        pass
if hasattr(sc, 'eevee'):
    sc.eevee.taa_render_samples = args.samples
w, h = (int(x) for x in args.res.lower().split('x'))
sc.render.resolution_percentage = 100
sc.render.film_transparent = args.transparent
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.color_mode = 'RGBA' if args.transparent else 'RGB'
if not args.transparent:
    world = sc.world or bpy.data.worlds.new('_World')
    sc.world = world
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == 'BACKGROUND')
    bg.inputs['Color'].default_value = (0.05, 0.05, 0.06, 1)
    bg.inputs['Strength'].default_value = 1.0


def shoot(path, rw, rh):
    sc.render.resolution_x, sc.render.resolution_y = rw, rh
    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path


print('RENDER_BEGIN')
if args.views:
    # turntable views: the camera goes round the model (leader space: faces +X, crown at target_cm), lights stay
    stem = os.path.splitext(args.out)[0]
    half = math.tan(math.radians(VFOV_DEG) / 2)
    for view in args.views.split(','):
        name, _, pitch = view.partition('@')
        kind, yaw = name.rstrip('0123456789-'), math.radians(float(name.lstrip('fulheadbstr') or 0))
        pitch = math.radians(float(pitch or 3))
        if kind == 'ref':
            px = args.target_cm / (REF_SOLES - REF_CROWN)  # cm per pixel
            cam_data.type = 'ORTHO'
            cam_data.ortho_scale = REF_SIZE[1] * px * height / args.target_cm  # in the scene's own units
            c = Vector((0, -(REF_SIZE[0] / 2 - REF_X) * px, (REF_SOLES - REF_SIZE[1] / 2) * px))
            aim(c + Vector((1000, 0, 0)), c)
            print(shoot('%s_ref.png' % stem, *REF_SIZE))
            cam_data.type = 'PERSP'
            continue
        if kind == 'full':
            target, span, size = Vector((0, 0, args.target_cm * 0.5)), args.target_cm * 1.1, (600, 900)
        elif kind == 'bust':
            target, span, size = Vector((0, 0, args.target_cm * 0.72)), args.target_cm * 0.42, (700, 700)
        else:
            target, span, size = Vector((0, 0, args.target_cm * 0.925)), args.target_cm * 0.19, (700, 700)
        d = span / 2 / half
        eye = target + Vector((math.cos(yaw) * math.cos(pitch), math.sin(yaw) * math.cos(pitch), math.sin(pitch))) * d
        aim(eye, target)
        print(shoot('%s_%s.png' % (stem, view.replace('@', 'e')), *size))
else:
    print(shoot(args.out, w, h))
top = max(pts, key=lambda p: p.z)
bottom = min(pts, key=lambda p: p.z)
aim(EYE, TARGET)
v_top = world_to_camera_view(sc, cam, top).y
v_bot = world_to_camera_view(sc, cam, bottom).y
print('model %.3f m -> %.0f cm; frame: top of head at %.2f, feet at %.2f (0 bottom, 1 top)%s' % (
    height, args.target_cm, v_top, v_bot, '  HEAD CUT OFF' if v_top > 1 else ''))
print('RENDER_END')

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
# close views (fraction of the height: centre, span): the shoulders and epaulettes, the chest, the elbows and the waist,
# the hips (the hand on the hilt, the tassels), the shins (the scabbard's end)
ZOOMS = {'shoulder': (0.82, 0.2), 'chest': (0.76, 0.22), 'waist': (0.62, 0.26), 'hip': (0.47, 0.3), 'shin': (0.25, 0.3), 'feet': (0.09, 0.3)}
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
ap.add_argument('--views', help='comma list instead of the game shot: full<yaw>, bust<yaw>, head<yaw>, shoulder|chest|waist|hip|shin|feet<yaw> (yaw in degrees round the '
                'model, 0 = front, 90 = his left side, 180 = back; @deg - camera elevation, default 3), e.g. full0,full45,full90,full180,head0,head45,head90; '
                'ref - orthographic front framed like art/source/alexander_ii_full.png (1024x1536, crown at REF_CROWN px, soles '
                'at REF_SOLES px) for an overlay on it; each goes to <out stem>_<view>.png')
ap.add_argument('--motion', help='a motion from tools/blender/motion.py (idle, test) keyed on the rig, the loose pieces '
                'simulated over it; with --frames')
ap.add_argument('--frames', help='comma list of frames (or first-last[:step]): the views shot at each '
                '(<out stem>_f<frame>_<view>.png); view game = the leader camera\'s shot')
ap.add_argument('--movie', help='with --motion: the whole motion rendered to this .mp4 (the leader camera, or the one view '
                'given in --views), 24 fps')
ap.add_argument('--spot', action='append', default=[], help='name=x,y,z,span: a close view of a point in the scene (metres, '
                'model space) span wide, shot as view <name><yaw>[@elev], e.g. --spot eye=0.03,-0.1,1.66,0.06 --views eye0,eye30@10')
ap.add_argument('--hide', help='comma list of objects (name prefixes) left out of the render, e.g. Collar,Uniform')
ap.add_argument('--flat', action='store_true', help='every surface in its own colour (the albedo as the model wears '
                'it, AO left out), no light: what is painted into the textures, shading included, shows as it is')
ap.add_argument('--studio', action='store_true', help='lit like the viewport\'s Material Preview (its default HDRI, '
                'forest.exr, and AgX), not by the key/fill/rim rig: to compare with screenshots of the viewport')
args = ap.parse_args(argv)

sc = bpy.data.scenes[args.scene] if args.scene else bpy.context.scene
if bpy.context.window:
    bpy.context.window.scene = sc
if args.motion:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import motion
    rig = next(o for o in sc.objects if o.type == 'ARMATURE')
    print('motion %s: %d frames' % (args.motion, motion.apply(sc, rig, args.motion)))
    sc.frame_set(1)
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
# the figure is turned towards his left in front of the camera by the pose's yaw (art/3d/pose.py), as in the export
YAW = float(sc.get('pose', {}).get('YAW_DEG', 0.0))
leader = Matrix.Rotation(math.radians(90 + YAW), 4, 'Z') @ Matrix.Scale(args.target_cm / height, 4)
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
    cam.rotation_quaternion = to_model.to_3x3().normalized().to_quaternion() @ rot
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
# Plain sRGB output: Blender's default AgX washes saturated colours (skin, gold) out towards grey, and the shots are
# compared with the portrait's colours
sc.view_settings.view_transform = 'Standard'
sc.view_settings.look = 'None'
sc.view_settings.exposure = -1.0  # the lights below were set for AgX's compressed highlights
# The world: what metal and cloth reflect - a soft warm room light (the game's leader scenes are lit by an environment
# too); the camera sees a plain dark background instead.
world = sc.world or bpy.data.worlds.new('_World')
sc.world = world
world.use_nodes = True
wnt = world.node_tree
for nd in list(wnt.nodes):
    wnt.nodes.remove(nd)
out = wnt.nodes.new('ShaderNodeOutputWorld')
env = wnt.nodes.new('ShaderNodeBackground'); env.inputs['Color'].default_value = (0.42, 0.36, 0.30, 1)
env.inputs['Strength'].default_value = 0.6
seen = wnt.nodes.new('ShaderNodeBackground'); seen.inputs['Color'].default_value = (0.05, 0.05, 0.06, 1)
lp = wnt.nodes.new('ShaderNodeLightPath')
mix = wnt.nodes.new('ShaderNodeMixShader')
wnt.links.new(lp.outputs['Is Camera Ray'], mix.inputs['Fac'])
wnt.links.new(env.outputs[0], mix.inputs[1]); wnt.links.new(seen.outputs[0], mix.inputs[2])
wnt.links.new(mix.outputs[0], out.inputs['Surface'])
if args.studio:
    for o in ('_Key', '_Fill', '_Rim'):
        bpy.data.objects[o].hide_render = True
    hdri = os.path.join(os.path.dirname(bpy.app.binary_path), '%d.%d' % bpy.app.version[:2], 'datafiles', 'studiolights',
                        'world', 'forest.exr')
    tex = wnt.nodes.new('ShaderNodeTexEnvironment'); tex.image = bpy.data.images.load(hdri)
    wnt.links.new(tex.outputs['Color'], env.inputs['Color']); env.inputs['Strength'].default_value = 1.0
    seen.inputs['Color'].default_value = (0.045, 0.045, 0.045, 1)
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.exposure = 0.0
if args.flat:
    for o in ('_Key', '_Fill', '_Rim'):
        bpy.data.objects[o].hide_render = True
    env.inputs['Strength'].default_value = 0.0
    sc.view_settings.exposure = 0.0
    for mat in bpy.data.materials:
        if not mat.use_nodes:
            continue
        nt = mat.node_tree
        bsdf = next((nd for nd in nt.nodes if nd.type == 'BSDF_PRINCIPLED'), None)
        mo = next((nd for nd in nt.nodes if nd.type == 'OUTPUT_MATERIAL'), None)
        if bsdf is None or mo is None:
            continue
        em = nt.nodes.new('ShaderNodeEmission')
        src = bsdf.inputs['Base Color']
        lk = src.links[0].from_node if src.links else None
        if lk is not None and lk.type == 'MIX' and lk.blend_type == 'MULTIPLY':  # the preview's AO: left out
            a = lk.inputs['A']
            if a.links:
                nt.links.new(a.links[0].from_socket, em.inputs['Color'])
            else:
                em.inputs['Color'].default_value = a.default_value
        elif src.links:
            nt.links.new(src.links[0].from_socket, em.inputs['Color'])
        else:
            em.inputs['Color'].default_value = src.default_value
        for l in list(mo.inputs['Surface'].links):
            nt.links.remove(l)
        nt.links.new(em.outputs[0], mo.inputs['Surface'])


def shoot(path, rw, rh):
    sc.render.resolution_x, sc.render.resolution_y = rw, rh
    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path


spots = {}
for sp in args.spot:
    n, _, v = sp.partition('=')
    x, y, z, w_ = (float(t) for t in v.split(','))
    spots[n] = (Vector((x, y, z)), w_)
def frame_list(spec):
    out = []
    for part in spec.split(','):
        rng, _, step = part.partition(':')
        a, _, b = rng.partition('-')
        out += list(range(int(a), int(b or a) + 1, int(step or 1)))
    return out


print('RENDER_BEGIN')
frames = frame_list(args.frames) if args.frames else [None]
for frame in frames if args.views and not args.movie else []:
    # turntable views: the camera goes round the model (leader space: faces +X, crown at target_cm), lights stay
    stem = os.path.splitext(args.out)[0]
    if frame is not None:
        sc.frame_set(frame)
        stem += '_f%03d' % frame
    half = math.tan(math.radians(VFOV_DEG) / 2)
    for view in args.views.split(','):
        name, _, pitch = view.partition('@')
        kind = name.rstrip('0123456789-')
        yaw = math.radians(float(name[len(kind):] or 0))
        if kind != 'ref':
            yaw += math.radians(YAW)  # turntable views go round the figure itself: 0 is square to its torso
        pitch = math.radians(float(pitch or 3))
        if kind == 'game':
            aim(EYE, TARGET)
            print(shoot('%s_game.png' % stem, w, h))
            continue
        if kind == 'ref':
            px = args.target_cm / (REF_SOLES - REF_CROWN)  # cm per pixel
            cam_data.type = 'ORTHO'
            cam_data.ortho_scale = REF_SIZE[1] * px * height / args.target_cm  # in the scene's own units
            c = Vector((0, -(REF_SIZE[0] / 2 - REF_X) * px, (REF_SOLES - REF_SIZE[1] / 2) * px))
            aim(c + Vector((1000, 0, 0)), c)
            print(shoot('%s_ref.png' % stem, *REF_SIZE))
            cam_data.type = 'PERSP'
            continue
        if kind in spots:
            p, sp = spots[kind]
            target, span, size = leader @ p, sp * args.target_cm / height, (700, 700)
        elif kind == 'full':
            target, span, size = Vector((0, 0, args.target_cm * 0.5)), args.target_cm * 1.1, (600, 900)
        elif kind in ZOOMS:
            target, span, size = Vector((0, 0, args.target_cm * ZOOMS[kind][0])), args.target_cm * ZOOMS[kind][1], (700, 700)
        elif kind == 'bust':
            target, span, size = Vector((0, 0, args.target_cm * 0.72)), args.target_cm * 0.42, (700, 700)
        else:
            target, span, size = Vector((0, 0, args.target_cm * 0.925)), args.target_cm * 0.19, (700, 700)
        d = span / 2 / half
        eye = target + Vector((math.cos(yaw) * math.cos(pitch), math.sin(yaw) * math.cos(pitch), math.sin(pitch))) * d
        aim(eye, target)
        print(shoot('%s_%s.png' % (stem, view.replace('@', 'e')), *size))
if args.movie:
    if args.views and args.views != 'game':  # one turntable view (full, bust, head or a close one), framed as above
        name, _, pitch = args.views.split(',')[0].partition('@')
        kind = name.rstrip('0123456789-')
        yaw = math.radians(float(name[len(kind):] or 0) + YAW)
        pitch = math.radians(float(pitch or 3))
        span = {'full': 1.1, 'bust': 0.42}.get(kind, ZOOMS.get(kind, (0, 0.19))[1]) * args.target_cm
        cz = {'full': 0.5, 'bust': 0.72}.get(kind, ZOOMS.get(kind, (0.925,))[0]) * args.target_cm
        target = Vector((0, 0, cz))
        d = span / 2 / math.tan(math.radians(VFOV_DEG) / 2)
        aim(target + Vector((math.cos(yaw) * math.cos(pitch), math.sin(yaw) * math.cos(pitch), math.sin(pitch))) * d,
            target)
        w, h = 700, 700
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.fps = 24
    sc.render.image_settings.file_format = 'FFMPEG'
    sc.render.ffmpeg.format = 'MPEG4'
    sc.render.ffmpeg.codec = 'H264'
    sc.render.ffmpeg.constant_rate_factor = 'HIGH'
    sc.render.filepath = os.path.abspath(args.movie)
    os.makedirs(os.path.dirname(sc.render.filepath), exist_ok=True)
    bpy.ops.render.render(animation=True)
    print(sc.render.filepath)
elif not args.views:
    print(shoot(args.out, w, h))
top = max(pts, key=lambda p: p.z)
bottom = min(pts, key=lambda p: p.z)
aim(EYE, TARGET)
v_top = world_to_camera_view(sc, cam, top).y
v_bot = world_to_camera_view(sc, cam, bottom).y
print('model %.3f m -> %.0f cm; frame: top of head at %.2f, feet at %.2f (0 bottom, 1 top)%s' % (
    height, args.target_cm, v_top, v_bot, '  HEAD CUT OFF' if v_top > 1 else ''))
print('RENDER_END')

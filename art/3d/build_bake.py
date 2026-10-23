# Ambient occlusion of the posed uniform, baked with everything on it (epaulettes, sash, belt, collar, orders, arms):
# the creases, the shade under the epaulettes and the belt, where the arms lie against the body. The game takes it as
# the material's AO map (textures/uniform_ao.png); the preview multiplies it into the colour.
# blender -b art/3d/alexander_leader.blend --python art/3d/build_bake.py   (the last step; rewrites in place)
import bpy, bmesh, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mat_util  # noqa: E402

OUT = os.path.join(HERE, 'alexander_leader.blend')
AO_OUT = os.path.join(HERE, 'textures', 'uniform_ao.png')
TEX, SAMPLES, AO_DIST = 2048, 96, 0.12  # AO_DIST: metres - how far something still shades
AO_BLUR = 2                       # px of blur over the baked AO (its noise)
# Hands (and what else of the body shows): the skin of the face (build_head.py's portrait colour, sRGB), redder over the
# knuckles and fingertips, darker in the creases and between the fingers (their own AO), a fine pore relief.
SKIN_SRGB, SKIN_RED = (0.88, 0.62, 0.48), (1.0, 0.82, 0.76)
SKIN_AO_DIST, SKIN_TEX, PORE_H = 0.03, 2048, 0.35
SKIN_OUT = os.path.join(HERE, 'textures', 'hands_albedo.png')
SKIN_NORMAL_OUT = os.path.join(HERE, 'textures', 'hands_normal.png')

sc = bpy.context.scene
uni = bpy.data.objects['Uniform']
# the outside of the cloth only: the lining (slot 1, build_pose.py) shares its UVs and would bake black over it
bm = bmesh.new(); bm.from_mesh(uni.data)
bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index == 1], context='FACES')
me = bpy.data.meshes.new('_AOTarget'); bm.to_mesh(me); bm.free()
tgt = bpy.data.objects.new('_AOTarget', me); sc.collection.objects.link(tgt)
tgt.matrix_world = uni.matrix_world
if bpy.data.images.get('Uniform_AO'):
    bpy.data.images.remove(bpy.data.images['Uniform_AO'])
img = bpy.data.images.new('Uniform_AO', TEX, TEX)
bake_mat = bpy.data.materials.new('_AOBake'); bake_mat.use_nodes = True
node = bake_mat.node_tree.nodes.new('ShaderNodeTexImage'); node.image = img
bake_mat.node_tree.nodes.active = node
me.materials.clear(); me.materials.append(bake_mat)
uni.hide_render = True
engine = sc.render.engine
sc.render.engine = 'CYCLES'
sc.cycles.samples = SAMPLES
sc.cycles.device = 'CPU'
sc.world = sc.world or bpy.data.worlds.new('World')
sc.world.light_settings.distance = AO_DIST
bk = sc.render.bake
bk.use_selected_to_active = False
bk.margin = 8
for o in sc.objects:
    o.select_set(o == tgt)
bpy.context.view_layer.objects.active = tgt
bpy.ops.object.bake(type='AO')
sc.render.engine = engine
uni.hide_render = False
# the bake's sampling noise out (on the cloth it read as grain): a masked blur, the islands not bled into each other
ao = np.array(img.pixels[:], np.float32).reshape(TEX, TEX, 4)
cov = (ao[..., 0] > 1e-4).astype(np.float32)  # baked texels (the empty background is black)
v = ao[..., 0] * cov
num, den = mat_util.blur(v, AO_BLUR), mat_util.blur(cov, AO_BLUR)
ao[..., :3] = np.where(cov[..., None] > 0, (num / np.maximum(den, 1e-6))[..., None], ao[..., :3])
img.pixels.foreach_set(ao.ravel())
img.filepath_raw = AO_OUT; img.file_format = 'PNG'; mat_util.write(img)
img.filepath = AO_OUT; img.source = 'FILE'; img.colorspace_settings.name = 'Non-Color'
bpy.data.objects.remove(tgt); bpy.data.materials.remove(bake_mat)
# one material slot again
for p in uni.data.polygons:
    p.material_index = 0
while len(uni.data.materials) > 1:
    uni.data.materials.pop()


def bake_ao(ob, res, dist):
    """Cycles AO of ob's UVs (everything in the scene shading it) into a new image."""
    me = ob.data
    keep = list(me.materials)
    im = bpy.data.images.new('_AO_' + ob.name, res, res)
    mat = bpy.data.materials.new('_AOBake2'); mat.use_nodes = True
    nd = mat.node_tree.nodes.new('ShaderNodeTexImage'); nd.image = im
    mat.node_tree.nodes.active = nd
    me.materials.clear(); me.materials.append(mat)
    sc.render.engine = 'CYCLES'
    sc.world.light_settings.distance = dist
    for o in sc.objects:
        o.select_set(o == ob)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.bake(type='AO')
    sc.render.engine = engine
    me.materials.clear()
    for m in keep:
        me.materials.append(m)
    bpy.data.materials.remove(mat)
    a = np.array(im.pixels[:], np.float32).reshape(res, res, 4)[..., 0]
    bpy.data.images.remove(im)
    return a


def paint_skin():
    under = bpy.data.objects.get('BodyUnder')
    if under is None:
        return
    me = under.data
    # convexity per vertex: how far it stands out of its neighbours along its normal (knuckles +, creases -)
    n = len(me.vertices)
    co = np.array([v.co[:] for v in me.vertices]); nr = np.array([v.normal[:] for v in me.vertices])
    acc = np.zeros((n, 3)); cnt = np.zeros(n)
    for e in me.edges:
        a, b = e.vertices
        acc[a] += co[b]; acc[b] += co[a]; cnt[a] += 1; cnt[b] += 1
    lap = co - acc / np.maximum(cnt, 1)[:, None]
    conv = np.clip((lap * nr).sum(1) / 0.0015, -1, 1)
    data, cov = mat_util.raster(me, SKIN_TEX, conv[:, None])
    conv_t = mat_util.blur(data[..., 6], 2)
    ao = bake_ao(under, SKIN_TEX, SKIN_AO_DIST)
    rng = np.random.default_rng(7)
    mottle = mat_util.blur(rng.random((SKIN_TEX, SKIN_TEX)).astype(np.float32), 6)
    mottle = (mottle - mottle.mean()) / (mottle.std() + 1e-6)
    base = np.array(SKIN_SRGB, np.float32) * (1 + 0.03 * mottle)[..., None]
    red = np.clip(conv_t, 0, 1)[..., None]
    col = base * (1 - red * 0.6 + red * 0.6 * np.array(SKIN_RED, np.float32))
    col *= (1 + np.clip(conv_t, -1, 0) * 0.25)[..., None]          # creases
    col *= (0.55 + 0.45 * np.clip(ao, 0, 1))[..., None]             # between the fingers, under the cuffs
    pores = mat_util.blur(rng.random((SKIN_TEX, SKIN_TEX)).astype(np.float32), 1) * PORE_H
    alb = mat_util.save('Hands_Albedo', np.clip(col, 0, 1).astype(np.float32), SKIN_OUT, 'sRGB')
    nrm = mat_util.save('Hands_Normal', (mat_util.normals(pores) * 0.5 + 0.5).astype(np.float32), SKIN_NORMAL_OUT,
                        'Non-Color')
    mat_util.material(me.materials[0].name, alb, None, nrm, rough=0.5, sheen=0.1, sheen_tint=(0.9, 0.6, 0.5))
    print('skin', SKIN_OUT)


paint_skin()
imgs = bpy.data.images
mat_util.material('Uniform_Cloth', imgs['Uniform_Albedo'], None, imgs['Uniform_Normal'], ao=img, rough=0.95, sheen=0.25, sheen_tint=(0.04, 0.045, 0.07))  # build_uniform.WOOL_SHEEN, SHEEN_TINT
print('baked', AO_OUT)
bpy.ops.outliner.orphans_purge(do_recursive=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
print('saved', OUT, os.path.getsize(OUT))

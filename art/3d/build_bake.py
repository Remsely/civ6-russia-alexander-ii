# Ambient occlusion of the posed uniform, baked with everything on it (epaulettes, sash, belt, collar, orders, arms):
# the creases, the shade under the epaulettes and the belt, where the arms lie against the body. The game takes it as
# the material's AO map (textures/uniform_ao.png); the preview multiplies it into the colour.
# blender -b art/3d/alexander_leader.blend --python art/3d/build_bake.py   (the last step; rewrites in place)
import bpy, bmesh, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mat_util  # noqa: E402

OUT = os.path.join(HERE, 'alexander_leader.blend')
AO_OUT = os.path.join(HERE, 'textures', 'uniform_ao.png')
TEX, SAMPLES, AO_DIST = 2048, 48, 0.12  # AO_DIST: metres - how far something still shades

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
img.filepath_raw = AO_OUT; img.file_format = 'PNG'; img.save()
img.filepath = AO_OUT; img.source = 'FILE'; img.colorspace_settings.name = 'Non-Color'
bpy.data.objects.remove(tgt); bpy.data.materials.remove(bake_mat)
# one material slot again
for p in uni.data.polygons:
    p.material_index = 0
while len(uni.data.materials) > 1:
    uni.data.materials.pop()
imgs = bpy.data.images
mat_util.material('Uniform_Cloth', imgs['Uniform_Albedo'], None, imgs['Uniform_Normal'], ao=img, rough=0.95, sheen=0.6, sheen_tint=(0.09, 0.10, 0.14))
print('baked', AO_OUT)
bpy.ops.outliner.orphans_purge(do_recursive=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
print('saved', OUT, os.path.getsize(OUT))

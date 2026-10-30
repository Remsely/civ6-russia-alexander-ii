"""Repair existing eyeballs without rebuilding the head; safe to run again.

blender -b --python art/3d/fix_eye_winding.py
Backs up and checks both working files. Changes only Eyes polygon winding/normals.
"""
from pathlib import Path
import hashlib
import shutil
import struct

import bpy
import numpy as np
from mathutils import Vector

HERE = Path(__file__).resolve().parent
BACKUP = HERE.parent / 'build' / 'eye-winding-source-backup'


def mesh_digest(ob):
    me = ob.data
    h = hashlib.sha256()
    for items, name, width, dtype in ((me.vertices, 'co', 3, np.float32),
                                      (me.loops, 'vertex_index', 1, np.int32)):
        a = np.empty(len(items) * width, dtype=dtype)
        items.foreach_get(name, a)
        h.update(a.tobytes())
    for layer in me.uv_layers:
        a = np.empty(len(layer.data) * 2, np.float32)
        layer.data.foreach_get('uv', a)
        h.update(a.tobytes())
    for v in me.vertices:
        for g in v.groups:
            h.update(struct.pack('<If', g.group, g.weight))
    return h.hexdigest()


def eye_sides(ob):
    """Count nondegenerate faces pointing away from / towards each eyeball centre."""
    me = ob.data
    group_names = {g.index: g.name for g in ob.vertex_groups}
    side = {v.index: next(group_names[g.group] for g in v.groups
                         if g.weight > 0.5 and group_names[g.group] in ('eye_l', 'eye_r'))
            for v in me.vertices}
    centres = {}
    for s in ('eye_l', 'eye_r'):
        vs = [v.co for v in me.vertices if side[v.index] == s]
        centres[s] = sum(vs, Vector()) / len(vs)
    out = inside = 0
    for p in me.polygons:
        if p.area < 1e-14:
            continue
        assert len({side[i] for i in p.vertices}) == 1
        radial = p.center - centres[side[p.vertices[0]]]
        if p.normal.dot(radial) > 0:
            out += 1
        else:
            inside += 1
    return out, inside


def uv_corners(me):
    return sorted((loop.vertex_index, *me.uv_layers.active.data[loop.index].uv)
                  for loop in me.loops)


for name in ('alexander_rest.blend', 'alexander_leader.blend'):
    path = HERE / name
    bpy.ops.wm.open_mainfile(filepath=str(path))
    sc = bpy.data.scenes['Human']
    bpy.context.window.scene = sc
    eyes = sc.objects['Eyes']
    before = eye_sides(eyes)
    print(name, 'outward/inward before', before)
    if before[1] == 0:
        print('already outward; not saved')
        continue
    assert before[0] == 0, 'Mixed winding needs a separate inspection'
    other = {o.name: mesh_digest(o) for o in sc.objects if o.type == 'MESH' and o is not eyes}
    positions = [tuple(v.co) for v in eyes.data.vertices]
    weights = [[(g.group, g.weight) for g in v.groups] for v in eyes.data.vertices]
    uv = uv_corners(eyes.data)
    rig = next(o for o in sc.objects if o.type == 'ARMATURE')
    bones = [(b.name, tuple(x for row in b.matrix_local for x in row)) for b in rig.data.bones]
    assert not eyes.data.has_custom_normals, 'Inspect custom eye normals before flipping'
    eyes.data.flip_normals()
    eyes.data.update()
    after = eye_sides(eyes)
    assert after == (before[1], 0), after
    assert positions == [tuple(v.co) for v in eyes.data.vertices]
    assert weights == [[(g.group, g.weight) for g in v.groups] for v in eyes.data.vertices]
    assert uv == uv_corners(eyes.data), 'UV moved to different vertices'
    assert other == {o.name: mesh_digest(o) for o in sc.objects if o.type == 'MESH' and o is not eyes}
    assert bones == [(b.name, tuple(x for row in b.matrix_local for x in row)) for b in rig.data.bones]
    BACKUP.mkdir(parents=True, exist_ok=True)
    if not (BACKUP / name).exists():
        shutil.copy2(path, BACKUP / name)
    # Preserve the existing .blend1 history; the explicit backup above is this operation's rollback.
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(path), compress=True)
    print(name, 'outward/inward after', after, 'positions, UVs, weights, other meshes and rig unchanged')

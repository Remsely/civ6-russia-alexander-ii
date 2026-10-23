# Scene audit for a Civ VI leader: numbers, not screenshots, so a build step can be checked without looking.
# python tools/blend.py audit art/3d/alexander_leader.blend [--scene Human] [--json out.json]
# or: blender -b <file.blend|-> --python tools/blender/audit.py -- [--scene S] [--fbx file.fbx] [--json out.json]
# Prints one JSON object between AUDIT_BEGIN / AUDIT_END. 'errors' break the Firaxis FBX importer or the game,
# 'warnings' are worth a look. Limits (see .claude/skills/civ6-asset-pipeline):
#  - every mesh needs a material on every face: a triangle group = a material, a mesh without one is dropped;
#  - a vertex is weighted to at most 8 bones;
#  - a skinned vertex with no deform weight stays at the origin when the leader moves.
import bpy, bmesh, json, os, sys, argparse
from collections import Counter

MAX_INFLUENCES = 8
WEIGHT_EPS = 1e-4

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser(prog='audit.py')
ap.add_argument('--scene', help='scene to audit (default: the active one)')
ap.add_argument('--fbx', help='import this FBX into an empty scene and audit it')
ap.add_argument('--json', help='also write the report here')
args = ap.parse_args(argv)

if args.fbx:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=os.path.abspath(args.fbx))
sc = bpy.data.scenes[args.scene] if args.scene else bpy.context.scene
if bpy.context.window:
    bpy.context.window.scene = sc
dg = bpy.context.evaluated_depsgraph_get()


def mesh_report(o):
    me = o.data
    rep = {'object': o.name, 'parent': o.parent and o.parent.name, 'verts': len(me.vertices),
           'faces': len(me.polygons), 'tris': sum(len(p.vertices) - 2 for p in me.polygons),
           'ngons': sum(len(p.vertices) > 4 for p in me.polygons),
           'materials': [m.name if m else None for m in me.materials], 'uv_layers': [uv.name for uv in me.uv_layers],
           'modifiers': [m.type for m in o.modifiers], 'hidden_render': o.hide_render}
    # Evaluated triangle count: what the exporter writes with use_mesh_modifiers (subdivision, triangulate...)
    ev = o.evaluated_get(dg).to_mesh()
    rep['tris_evaluated'] = sum(len(p.vertices) - 2 for p in ev.polygons)
    o.evaluated_get(dg).to_mesh_clear()
    used = Counter(p.material_index for p in me.polygons)
    rep['faces_without_material'] = sum(n for i, n in used.items()
                                        if i >= len(me.materials) or me.materials[i] is None)
    bm = bmesh.new(); bm.from_mesh(me)
    rep['non_manifold_edges'] = sum(not e.is_manifold and not e.is_boundary for e in bm.edges)
    rep['boundary_edges'] = sum(e.is_boundary for e in bm.edges)
    rep['loose_verts'] = sum(not v.link_edges for v in bm.verts)
    bm.free()

    arm_mods = [m for m in o.modifiers if m.type == 'ARMATURE' and m.object]
    rig = arm_mods[0].object if arm_mods else (o.parent if o.parent and o.parent.type == 'ARMATURE'
                                               and o.parent_type == 'OBJECT' else None)
    rep['rig'] = rig and rig.name
    if rig:
        deform = {b.name for b in rig.data.bones if b.use_deform}
        gname = {g.index: g.name for g in o.vertex_groups}
        rep['groups_without_bone'] = sorted(n for n in gname.values() if n not in deform and n not in
                                            {b.name for b in rig.data.bones})
        infl = Counter(); over, none, unnorm = 0, 0, 0
        for v in me.vertices:
            ws = [g.weight for g in v.groups if g.weight > WEIGHT_EPS and gname.get(g.group) in deform]
            infl[len(ws)] += 1
            over += len(ws) > MAX_INFLUENCES
            none += not ws
            unnorm += bool(ws) and abs(sum(ws) - 1) > 0.01
        rep['influences_histogram'] = dict(sorted(infl.items()))
        rep['verts_over_%d_bones' % MAX_INFLUENCES] = over
        rep['verts_without_weight'] = none
        rep['verts_unnormalized'] = unnorm
        used_bones = {gname[g.group] for v in me.vertices for g in v.groups
                      if g.weight > WEIGHT_EPS and gname.get(g.group) in deform}
        rep['bones_used'] = len(used_bones)
    return rep


report = {'file': bpy.data.filepath or args.fbx, 'scene': sc.name, 'blender': bpy.app.version_string,
          'unit_scale': sc.unit_settings.scale_length, 'meshes': [], 'armatures': [], 'images': [],
          'errors': [], 'warnings': []}
meshes = [o for o in sc.objects if o.type == 'MESH']
for o in meshes:
    report['meshes'].append(mesh_report(o))
for o in (o for o in sc.objects if o.type == 'ARMATURE'):
    bones = o.data.bones
    report['armatures'].append({'object': o.name, 'bones': len(bones), 'deform_bones': sum(b.use_deform for b in bones),
                                'roots': [b.name for b in bones if not b.parent],
                                'action': o.animation_data and o.animation_data.action and
                                o.animation_data.action.name})

# Bounding box of everything that renders, in scene units (MPFB: metres, feet at 0)
pts = [o.matrix_world @ v.co for o in meshes if not o.hide_render for v in o.data.vertices]
if pts:
    lo = [min(p[i] for p in pts) for i in range(3)]; hi = [max(p[i] for p in pts) for i in range(3)]
    report['bbox'] = {'min': [round(x, 4) for x in lo], 'max': [round(x, 4) for x in hi],
                      'size': [round(h - l, 4) for l, h in zip(lo, hi)]}
report['tris_total'] = sum(m['tris_evaluated'] for m in report['meshes'] if not m['hidden_render'])

for img in bpy.data.images:
    if img.source != 'FILE':
        continue
    path = bpy.path.abspath(img.filepath)
    report['images'].append({'name': img.name, 'size': list(img.size), 'file': img.filepath,
                             'missing': not img.packed_file and not os.path.exists(path)})

err, warn = report['errors'], report['warnings']
for m in report['meshes']:
    n = m['object']
    if m['hidden_render']:
        continue
    if not any(m['materials']):
        err.append('%s: no material (the importer drops the mesh)' % n)
    elif m['faces_without_material']:
        err.append('%s: %d faces without material' % (n, m['faces_without_material']))
    if not m['uv_layers']:
        warn.append('%s: no UV layer' % n)
    if m.get('verts_over_%d_bones' % MAX_INFLUENCES):
        err.append('%s: %d verts weighted to more than %d bones' % (n, m['verts_over_%d_bones' % MAX_INFLUENCES],
                                                                    MAX_INFLUENCES))
    if m.get('verts_without_weight'):
        err.append('%s: %d skinned verts without weight' % (n, m['verts_without_weight']))
    if m.get('verts_unnormalized'):
        warn.append('%s: %d verts with weights not summing to 1' % (n, m['verts_unnormalized']))
    if m.get('groups_without_bone'):
        warn.append('%s: vertex groups with no bone: %s' % (n, ', '.join(m['groups_without_bone'][:10])))
    if not m['rig'] and report['armatures']:
        warn.append('%s: not skinned (stays still when the leader moves)' % n)
    if m['non_manifold_edges']:
        warn.append('%s: %d non-manifold edges' % (n, m['non_manifold_edges']))
    if m['loose_verts']:
        warn.append('%s: %d loose verts' % (n, m['loose_verts']))
for i in report['images']:
    if i['missing']:
        err.append('image %s: file missing (%s)' % (i['name'], i['file']))
    elif any(s & (s - 1) for s in i['size']):
        warn.append('image %s: %dx%d is not a power of two' % (i['name'], *i['size']))

text = json.dumps(report, ensure_ascii=False, indent=1)
if args.json:
    with open(args.json, 'w', encoding='utf-8') as f:
        f.write(text)
print('AUDIT_BEGIN'); print(text); print('AUDIT_END')

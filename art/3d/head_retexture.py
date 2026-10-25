# The head's colour redone without touching its mesh: build_head.py is not repeatable (its remesh and decimation come
# out a little different each run - other vertices, other UVs, up to 3 mm off), so after the leader is built its head
# keeps its mesh and only its albedo is made anew:
#   python art/3d/head_retexture.py
# 1. build_head.py runs on a copy of alexander_rest.blend: a new head with its own UVs and textures (head_albedo.png;
#    the eyes' eye_albedo.png too - polar, the same on any eyeball);
# 2. alexander_rest.blend, head_mr.png and head_normal.png are put back as they were (the leader's head was built from
#    them);
# 3. that albedo is carried onto the head of alexander_rest.blend (its UVs are the leader's): per texel the nearest
#    point of the new head's surface (both in the rest pose) and the new texture there (this file again, in Blender).
import os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REST = os.path.join(HERE, 'alexander_rest.blend')
TEXDIR = os.path.join(HERE, 'textures')
ALBEDO = os.path.join(TEXDIR, 'head_albedo.png')
KEEP = ('head_mr.png', 'head_normal.png')
TEX = 2048
FAR = 0.003  # m: texels whose nearest new surface is further than this are counted (a sign the heads differ)


def run():
    blender = os.environ.get('BLENDER', r'C:\Program Files\Blender Foundation\Blender 4.5\blender.exe')
    tmp = tempfile.mkdtemp(prefix='head_retexture_')
    shutil.copy2(REST, os.path.join(tmp, 'rest.blend'))
    for f in KEEP:
        shutil.copy2(os.path.join(TEXDIR, f), os.path.join(tmp, f))
    try:
        p = subprocess.run([blender, '-b', REST, '--python-exit-code', '1', '--python',
                            os.path.join(HERE, 'build_head.py')], capture_output=True, text=True, encoding='utf-8',
                           errors='replace')
        if p.returncode:
            sys.exit((p.stdout + p.stderr)[-3000:] + '\nbuild_head.py failed')
        shutil.copy2(REST, os.path.join(tmp, 'new.blend'))
        shutil.copy2(ALBEDO, os.path.join(tmp, 'new_albedo.png'))
    finally:  # the leader's head was built from these
        shutil.copy2(os.path.join(tmp, 'rest.blend'), REST)
        for f in KEEP:
            shutil.copy2(os.path.join(tmp, f), os.path.join(TEXDIR, f))
    p = subprocess.run([blender, '-b', REST, '--python-exit-code', '1', '--python', os.path.abspath(__file__), '--',
                        os.path.join(tmp, 'new.blend'), os.path.join(tmp, 'new_albedo.png'), ALBEDO],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    print('\n'.join(l for l in (p.stdout + p.stderr).splitlines() if l.startswith(('carried', 'Traceback', 'Error'))))
    if p.returncode:
        sys.exit(p.stderr[-3000:])
    shutil.rmtree(tmp, ignore_errors=True)


def carry(new_blend, new_png, out_png):
    """In Blender, on alexander_rest.blend: new_png (on new_blend's Head, its UVs) onto this file's Head's UVs."""
    import bpy
    import numpy as np
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    from mathutils.interpolate import poly_3d_calc
    sys.path.insert(0, HERE)
    import mat_util
    head = bpy.data.objects['Head']
    with bpy.data.libraries.load(new_blend) as (_, dst):
        dst.objects = ['Head']
    new = dst.objects[0]
    me = new.data
    co = [new.matrix_world @ v.co for v in me.vertices]
    polys = [tuple(p.vertices) for p in me.polygons]
    bvh = BVHTree.FromPolygons(co, polys)
    uvl = me.uv_layers.active.data
    puv = [[Vector(uvl[li].uv) for li in p.loop_indices] for p in me.polygons]
    img = bpy.data.images.load(new_png)
    nw, nh = img.size
    npx = np.array(img.pixels[:], np.float32).reshape(nh, nw, 4)[..., :3]
    data, cov = mat_util.raster(head.data, TEX)
    ys, xs = np.nonzero(cov)
    uvs = np.zeros((len(ys), 2), np.float32)
    far = 0
    for k, (y, x) in enumerate(zip(ys, xs)):
        loc, _, fi, d = bvh.find_nearest(head.matrix_world @ Vector(data[y, x, :3].tolist()))
        if fi is None:
            continue
        far += d > FAR
        w = poly_3d_calc([co[i] for i in polys[fi]], loc)
        uvs[k] = sum((u * wi for u, wi in zip(puv[fi], w)), Vector((0, 0)))
    fx, fy = np.clip(uvs[:, 0] * nw - 0.5, 0, nw - 1.001), np.clip(uvs[:, 1] * nh - 0.5, 0, nh - 1.001)
    x0, y0 = fx.astype(int), fy.astype(int)
    ax, ay = (fx - x0)[:, None], (fy - y0)[:, None]
    c = (npx[y0, x0] * (1 - ax) * (1 - ay) + npx[y0, x0 + 1] * ax * (1 - ay) + npx[y0 + 1, x0] * (1 - ax) * ay
         + npx[y0 + 1, x0 + 1] * ax * ay)
    out = np.zeros((TEX, TEX, 3), np.float32)
    out[ys, xs] = c
    mat_util.save('_head_retexture', mat_util.pad(out, cov), out_png, 'sRGB')
    print('carried %d texels, %d over %.0f mm from the new surface -> %s' % (len(ys), far, FAR * 1000, out_png))


if __name__ == '__main__':
    try:
        import bpy  # noqa: F401
    except ImportError:
        run()
    else:
        carry(*sys.argv[sys.argv.index('--') + 1:][:3])

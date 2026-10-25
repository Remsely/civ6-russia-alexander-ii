# The uniform's texture: dark wool with red piping, cuffs and trouser stripes - its albedo (textures/uniform_albedo.png)
# and the weave's and the piping's relief (textures/uniform_normal.png). build_uniform.py paints it on the single sheet
# it builds (smart UV first); run on its own, this repaints the front closure's piping (CLOSURE_ZONE) of the finished
# uniform over the UVs it has, the rest of the maps kept as they are:
# blender -b art/3d/alexander_rest.blend --python art/3d/uniform_paint.py
# (alexander_rest.blend's Uniform is in the rest pose the colours are placed by - the skirt shaped since the painting,
# its piping would come out a little elsewhere; the leader file's uniform, subdivided and posed, keeps the UV layout and
# reads the same files, so nothing else is rebuilt).
import bpy, math, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mat_util  # noqa: E402

# Colours linear RGB; widths are half-widths in metres unless said otherwise.
TEX = 2048
TEX_OUT = os.path.join(HERE, 'textures', 'uniform_albedo.png')
NORMAL_OUT = os.path.join(HERE, 'textures', 'uniform_normal.png')
CLOTH_RGB = (0.0034, 0.0037, 0.0058)  # the portrait's near-black broadcloth (at twice this the lit chest read grey)
PIPING_RGB = (0.50, 0.012, 0.010)
PIPING_W, STRIPE_W = 0.007, 0.012
FRONT_PIPING_W = 0.005            # the closure's piping: this wide (whole width) on the flap from its edge in (the
                                  # portrait's ~6 mm; from 2 mm short of the edge, 9 mm wide, it lay over the flap's
                                  # step and the next UV island: a broad ragged red band down the chest)
WOOL_REPEATS, WOOL_CONTRAST = 10, 0.07  # textures/gen/wool.png over the UVs (~15 cm a tile), its weave's strength (the
                                    # portrait's broadcloth is smooth: a stronger weave read as grain)
WOOL_H, PIPING_H = 0.06, 2.5        # px of relief: the weave; the piping, a cord sewn into the seams
WOOL_SHEEN, SHEEN_TINT = 0.15, (0.04, 0.045, 0.07)  # broadcloth's fuzz at grazing angles: a faint dark blue (the portrait's cloth is near black)
CLOTH_SPEC = 0.2                  # the wool's white specular (Specular IOR Level): at 0.5 a white veil, the scarlet
                                  # piping and stripes pink in the light
PLEAT_ANGLE = (66.0, 80.0)        # degrees from the front centre (at the belt, at the hem) to the piped pleats of the skirt: in the portrait (the
                                  # 'ref' view) the piping runs from x ~435 at the belt out to ~350 at the hem on his
                                  # right, ~655 on his left - the front panel's edge, the back panel stepping out
                                  # behind it in a fold
CLOSURE_ZONE = 0.012              # standalone: texels this near the closure's edge repainted, the rest kept
HAND_PREFIX = ('hand_', 'index_', 'middle_', 'pinky_', 'ring_', 'thumb_')
ARM = {'upperarm_l', 'upperarm_r', 'lowerarm_l', 'lowerarm_r'}


def uniform_colour(pos, part, bones, P):
    """Albedo (linear RGB) per surface point of the uniform in the rest pose: dark wool with red piping, cuffs and
    trouser stripes. Gold, collar and the rest are separate detail meshes, not painted. part: 0 the coat, 2 the
    trousers, 3 the sleeves (the coat's faces the arms move). bones: name -> (head, tail) in the rest pose; P: the
    uniform's measurements (build_uniform.py, sc['uniform'])."""
    x, y, z = pos[:, 0], pos[:, 1], pos[:, 2]
    red = np.zeros(len(pos), bool)
    coat = part != 2
    # piping down the front closure, from the collar to the hem: on the flap, from its edge in
    red |= coat & (y < -0.03) & (x > P['FLAP_X']) & (x < P['FLAP_X'] + FRONT_PIPING_W)
    # cuffs: the last CUFF_T of the forearm
    for s_ in 'lr':
        a, b = (np.array(v) for v in bones['lowerarm_' + s_])
        d = b - a
        t = (pos - a) @ d / (d @ d)
        radial = np.linalg.norm(pos - a - np.outer(t, d), axis=1)
        # (on the sleeves only: the coat is built round the portrait's stance, his right forearm lies across the small
        # of the back, and the cloth there came out in red patches)
        red |= (part == 3) & (t > P['SLEEVE_T'] - P['CUFF_T']) & (t <= P['SLEEVE_T'] + 0.05) & (radial < 0.09)
    # lampas: a stripe down the outer seam of each trouser leg
    zs = [bones['thigh_l'][0].z, bones['calf_l'][0].z, bones['calf_l'][1].z][::-1]
    ys = [bones['thigh_l'][0].y, bones['calf_l'][0].y, bones['calf_l'][1].y][::-1]
    xs = [bones['thigh_l'][0].x, bones['calf_l'][0].x, bones['calf_l'][1].x][::-1]
    yc, xc = np.interp(z, zs, ys), np.interp(z, zs, xs)
    red |= (part == 2) & (np.abs(y - yc) < STRIPE_W) & (np.abs(x) > xc)  # outer side only
    # piping on the skirt's rear pleats, seen at the sides from the front: from the belt to the hem
    waist, hem = P['WAIST_Z'], P['HEM_Z']
    ang = np.degrees(np.arctan2(np.abs(x), -y))
    pa = PLEAT_ANGLE[0] + (PLEAT_ANGLE[1] - PLEAT_ANGLE[0]) * np.clip((waist - z) / (waist - hem), 0, 1)
    dist = np.radians(np.abs(ang - pa)) * np.hypot(x, y)
    red |= coat & (z < waist - 0.03) & (dist < PIPING_W)
    col = np.tile(np.array(CLOTH_RGB, np.float32), (len(pos), 1))
    col[red] = PIPING_RGB
    return col


def wool_detail():
    """The weave of the generated broadcloth (textures/gen/wool.png, seamless) as a brightness factor round 1, tiled
    WOOL_REPEATS times over the uniform's UVs (smart UV keeps the texel density even)."""
    img = bpy.data.images.load(os.path.join(HERE, 'textures', 'gen', 'wool.png'), check_existing=False)
    w, hh = img.size
    a = np.array(img.pixels[:], np.float32).reshape(hh, w, 4)[..., :3] @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    bpy.data.images.remove(img)
    a /= a.mean()
    ys = (np.arange(TEX) * WOOL_REPEATS * hh // TEX) % hh
    xs = (np.arange(TEX) * WOOL_REPEATS * w // TEX) % w
    return (1 + (a[np.ix_(ys, xs)] - 1) * WOOL_CONTRAST).astype(np.float32)


def paint(ob, mat, P, bones, unwrap=True, only=None):
    """Smart-UV the uniform (unwrap) and rasterise uniform_colour() into its albedo (supersampled, island edges
    dilated), its relief into the normal map; mat wired to them. only: pos -> bool, the texels repainted (the files'
    other texels kept)."""
    sc = bpy.context.scene
    if unwrap:
        for o in sc.objects:
            o.select_set(o == ob)
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.004)
        bpy.ops.object.mode_set(mode='OBJECT')
    me = ob.data
    me.calc_loop_triangles()
    n = TEX * 2
    acc = np.zeros((n, n, 3), np.float32); cov = np.zeros((n, n), bool); sel = np.zeros((n, n), bool)
    uv = np.zeros(len(me.loops) * 2, np.float32); me.uv_layers.active.data.foreach_get('uv', uv); uv = uv.reshape(-1, 2) * n
    co = np.zeros(len(me.vertices) * 3, np.float32); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    part = np.zeros(len(me.polygons), np.int32); me.attributes['part'].data.foreach_get('value', part)
    armg = {g.index for g in ob.vertex_groups if g.name in ARM or g.name.startswith(HAND_PREFIX)}
    arm_w = np.array([sum(g.weight for g in v.groups if g.group in armg) for v in me.vertices])
    sleeve = np.array([arm_w[list(p.vertices)].mean() > 0.5 for p in me.polygons])
    part[(part == 0) & sleeve] = 3
    print('uniform painter: %d sleeve faces' % int((part == 3).sum()))
    for tri in me.loop_triangles:
        t_uv = uv[list(tri.loops)]; t_co = co[list(tri.vertices)]
        x0, y0 = np.floor(t_uv.min(0)).astype(int); x1, y1 = np.ceil(t_uv.max(0)).astype(int)
        xs, ys_ = np.meshgrid(np.arange(max(x0, 0), min(x1 + 1, n)), np.arange(max(y0, 0), min(y1 + 1, n)))
        px = np.stack([xs.ravel() + 0.5, ys_.ravel() + 0.5], 1)
        (ax, ay), (bx, by), (cx, cy) = t_uv
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-9:
            continue
        l1 = ((by - cy) * (px[:, 0] - cx) + (cx - bx) * (px[:, 1] - cy)) / den
        l2 = ((cy - ay) * (px[:, 0] - cx) + (ax - cx) * (px[:, 1] - cy)) / den
        l3 = 1 - l1 - l2
        inside = (l1 >= -0.02) & (l2 >= -0.02) & (l3 >= -0.02)
        if not inside.any():
            continue
        bary = np.stack([l1, l2, l3], 1)[inside]
        pos = bary @ t_co
        ix, iy = px[inside, 0].astype(int), px[inside, 1].astype(int)
        acc[iy, ix] = uniform_colour(pos, np.full(len(pos), part[tri.polygon_index]), bones, P)
        cov[iy, ix] = True
        if only is not None:
            sel[iy, ix] = only(pos)
    for _ in range(8):  # dilate islands so mip-mapping and filtering never pull in the empty background
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            src = np.roll(np.roll(cov, dy, 0), dx, 1); fill = src & ~cov
            acc[fill] = np.roll(np.roll(acc, dy, 0), dx, 1)[fill]; sel[fill] = np.roll(np.roll(sel, dy, 0), dx, 1)[fill]
            cov |= fill
    acc[~cov] = CLOTH_RGB
    img_px = acc.reshape(TEX, 2, TEX, 2, 3).mean((1, 3))
    wool = wool_detail()
    img_px *= wool[..., None]
    piping = (img_px[..., 0] > 0.1).astype(np.float32)  # the red (linear) of the piping and stripes
    height = mat_util.blur(piping, 2) * PIPING_H + (wool - 1) / WOOL_CONTRAST * WOOL_H
    img_px = np.where(img_px <= 0.0031308, img_px * 12.92, 1.055 * np.power(img_px, 1 / 2.4) - 0.055)  # to sRGB
    nrm_px = mat_util.normals(height) * 0.5 + 0.5
    if only is not None:  # the rest as the files have it
        k = sel.reshape(TEX, 2, TEX, 2).any((1, 3))
        for data, path in ((img_px, TEX_OUT), (nrm_px, NORMAL_OUT)):
            old = bpy.data.images.load(path, check_existing=False)
            data[~k] = np.array(old.pixels[:], np.float32).reshape(TEX, TEX, 4)[..., :3][~k]
            bpy.data.images.remove(old)
        print('repainted %d texels' % int(k.sum()))
    albedo = mat_util.save('Uniform_Albedo', img_px, TEX_OUT, 'sRGB')
    nrm = mat_util.save('Uniform_Normal', nrm_px, NORMAL_OUT, 'Non-Color')
    mat_util.material(mat.name, albedo, None, nrm, rough=0.95, sheen=WOOL_SHEEN, sheen_tint=SHEEN_TINT, spec=CLOTH_SPEC)
    print('painted', TEX_OUT)


if __name__ == '__main__':
    uni = bpy.data.objects['Uniform']
    rig = bpy.data.objects['HumanRig']
    P = bpy.context.scene['uniform'].to_dict()
    paint(uni, uni.data.materials[0], P,
          {b.name: (rig.matrix_world @ b.head_local, rig.matrix_world @ b.tail_local) for b in rig.data.bones},
          unwrap=False, only=lambda pos: (pos[:, 1] < -0.03) & (np.abs(pos[:, 0] - P['FLAP_X']) < CLOSURE_ZONE))

# Texture maps and materials shared by the build steps: relief (height) -> tangent-space normal map, maps saved as
# PNG next to the model, a Principled material wired to albedo + metal/roughness + normal (+ AO multiplied into the
# colour for the preview; the game takes AO as its own map).
# Arrays are Blender's pixel order: row 0 = bottom, values 0..1; normal maps OpenGL (green = +V).
import math
import os
import bpy
import numpy as np

LUM = np.array([0.2126, 0.7152, 0.0722], np.float32)
# One gold for everything (embroidery, belt, epaulettes, cords, orders, sabre): the portrait's, sRGB - the median of its
# gold pixels is (183, 118, 52) in the light it is painted in, the highlights (238, 188, 118).
GOLD_SRGB = (225, 150, 62)


def belt_z(P, x, y):
    """The belt's middle height over (x, y): its plane through BELT_ZC tilted by BELT_TILT (build_uniform.py)."""
    side, front = (math.tan(math.radians(a)) for a in P.get('BELT_TILT', (0.0, 0.0)))
    return P['BELT_ZC'] - side * (x - P['BELT_C'][0]) + front * (y - P['BELT_C'][1])


def gold_grade(rgb, mask):
    """sRGB picture pixels turned to GOLD_SRGB's hue, keeping their light and dark, by mask (0..1)."""
    tgt = np.array(GOLD_SRGB, np.float32) / 255
    lum = rgb @ LUM
    graded = np.clip(tgt * (lum / float(tgt @ LUM))[..., None], 0, 1)
    m = np.asarray(mask, np.float32)[..., None]
    return rgb * (1 - m) + graded * m


def pad(rgb, mask, rounds=32):
    """Texels outside the UV islands (mask False) filled outwards from the islands' edges, so filtering and mipmaps
    pull no black (or other background) into the islands' rims - small islands come out speckled otherwise."""
    rgb = rgb.copy(); m = mask.astype(np.float32)
    for _ in range(rounds):
        acc = np.zeros_like(rgb); cnt = np.zeros_like(m)
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            acc += np.roll(np.roll(rgb * m[..., None], dy, 0), dx, 1)
            cnt += np.roll(np.roll(m, dy, 0), dx, 1)
        grow = (m == 0) & (cnt > 0)
        rgb[grow] = acc[grow] / cnt[grow][:, None]
        m = np.maximum(m, grow.astype(np.float32))
    rest = m == 0
    if rest.any():
        rgb[rest] = rgb[~rest].mean(0)
    return rgb


def blur(a, r=1):
    """Box blur, r pixels each way, wrapping (the regions are tiles)."""
    for ax in (0, 1):
        a = sum(np.roll(a, k, ax) for k in range(-r, r + 1)) / (2 * r + 1)
    return a


def normals(height, mx=1.0, my=1.0):
    """Tangent-space normals of a height field (same units as mx / my, the size of a pixel along u / v)."""
    gy, gx = np.gradient(height)
    n = np.stack([-gx / mx, -gy / my, np.ones_like(height)], -1)
    return n / np.linalg.norm(n, axis=-1, keepdims=True)


def relief(rgb, strength, r=1):
    """A picture's own light and dark as its relief: raised where bright. strength: height per unit of brightness,
    in pixels (1 = a step from black to white rises one pixel)."""
    return blur(rgb @ LUM, r) * strength


def write(img, tries=20):
    """img.save() that waits out a moment's lock on the file (a viewer or indexer reading it: 'Invalid argument')."""
    import time
    for k in range(tries):
        try:
            img.save()
            return
        except RuntimeError:
            if k == tries - 1:
                raise
            time.sleep(0.5)


def save(name, data, path, colorspace):
    """data (h, w, 3) -> image 'name' saved to path and kept linked to it."""
    hh, w = data.shape[:2]
    img = bpy.data.images.get(name) or bpy.data.images.new(name, w, hh)
    img.scale(w, hh)
    img.pixels.foreach_set(np.concatenate([data, np.ones((hh, w, 1), np.float32)], 2).astype(np.float32).ravel())
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.filepath_raw = path; img.file_format = 'PNG'; write(img)
    img.filepath = path; img.source = 'FILE'
    img.colorspace_settings.name = colorspace
    return img


def material(name, albedo, mr=None, normal=None, ao=None, ao_strength=0.85, sheen=0.0, rough=None, normal_strength=1.0,
             sheen_tint=(1, 1, 1)):
    """Principled material from images: albedo; mr (R metal, G roughness) or a constant rough; normal; ao multiplied
    into the colour; sheen (wool's fuzz) in sheen_tint (linear)."""
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    for nd in [nd for nd in nt.nodes if nd.type not in ('BSDF_PRINCIPLED', 'OUTPUT_MATERIAL')]:
        nt.nodes.remove(nd)
    bsdf = next(nd for nd in nt.nodes if nd.type == 'BSDF_PRINCIPLED')

    def tex(img):
        t = nt.nodes.new('ShaderNodeTexImage'); t.image = img
        return t
    col = tex(albedo).outputs['Color']
    if ao is not None:
        mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'
        mix.inputs['Factor'].default_value = ao_strength
        nt.links.new(col, mix.inputs['A']); nt.links.new(tex(ao).outputs['Color'], mix.inputs['B'])
        col = mix.outputs['Result']
    nt.links.new(col, bsdf.inputs['Base Color'])
    if mr is not None:
        sep = nt.nodes.new('ShaderNodeSeparateColor')
        nt.links.new(tex(mr).outputs['Color'], sep.inputs['Color'])
        nt.links.new(sep.outputs[0], bsdf.inputs['Metallic']); nt.links.new(sep.outputs[1], bsdf.inputs['Roughness'])
    elif rough is not None:
        bsdf.inputs['Roughness'].default_value = rough
    if normal is not None:
        nm = nt.nodes.new('ShaderNodeNormalMap')
        nm.inputs['Strength'].default_value = normal_strength
        nt.links.new(tex(normal).outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
    bsdf.inputs['Sheen Weight'].default_value = sheen
    bsdf.inputs['Sheen Roughness'].default_value = 0.6
    bsdf.inputs['Sheen Tint'].default_value = (*sheen_tint, 1)
    return mat


def raster(me, res, values=None):
    """Per texel of mesh me's active UV map (res x res): the surface point (3), its normal (3) and, if given, a
    per-vertex value array (n, k) interpolated; plus the coverage mask. Texels outside every island are filled from
    their neighbours (8 rounds) so filtering never reads the background."""
    me.calc_loop_triangles()
    uv = np.zeros(len(me.loops) * 2, np.float32); me.uv_layers.active.data.foreach_get('uv', uv)
    uv = uv.reshape(-1, 2) * res
    co = np.zeros(len(me.vertices) * 3, np.float32); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    vn = np.zeros(len(me.vertices) * 3, np.float32); me.vertices.foreach_get('normal', vn); vn = vn.reshape(-1, 3)
    cols = [co, vn] + ([np.asarray(values, np.float32).reshape(len(co), -1)] if values is not None else [])
    k = sum(c.shape[1] for c in cols)
    data = np.concatenate(cols, 1)
    out = np.zeros((res, res, k), np.float32); cov = np.zeros((res, res), bool)
    for tri in me.loop_triangles:
        t_uv = uv[list(tri.loops)]; t_d = data[list(tri.vertices)]
        x0, y0 = np.floor(t_uv.min(0)).astype(int); x1, y1 = np.ceil(t_uv.max(0)).astype(int)
        xs, ys = np.meshgrid(np.arange(max(x0, 0), min(x1 + 1, res)), np.arange(max(y0, 0), min(y1 + 1, res)))
        px = np.stack([xs.ravel() + 0.5, ys.ravel() + 0.5], 1)
        (ax, ay), (bx, by), (cx, cy) = t_uv
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-9:
            continue
        l1 = ((by - cy) * (px[:, 0] - cx) + (cx - bx) * (px[:, 1] - cy)) / den
        l2 = ((cy - ay) * (px[:, 0] - cx) + (ax - cx) * (px[:, 1] - cy)) / den
        l3 = 1 - l1 - l2
        ins = (l1 >= -0.02) & (l2 >= -0.02) & (l3 >= -0.02)
        if not ins.any():
            continue
        bary = np.stack([l1, l2, l3], 1)[ins]
        ix, iy = px[ins, 0].astype(int), px[ins, 1].astype(int)
        out[iy, ix] = bary @ t_d; cov[iy, ix] = True
    filled = cov.copy()
    for _ in range(8):
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            src = np.roll(np.roll(filled, dy, 0), dx, 1); fill = src & ~filled
            out[fill] = np.roll(np.roll(out, dy, 0), dx, 1)[fill]; filled |= fill
    return out, cov

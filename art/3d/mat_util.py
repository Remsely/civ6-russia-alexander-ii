# Texture maps and materials shared by the build steps: relief (height) -> tangent-space normal map, maps saved as
# PNG next to the model, a Principled material wired to albedo + metal/roughness + normal (+ AO multiplied into the
# colour for the preview; the game takes AO as its own map).
# Arrays are Blender's pixel order: row 0 = bottom, values 0..1; normal maps OpenGL (green = +V).
import os
import bpy
import numpy as np

LUM = np.array([0.2126, 0.7152, 0.0722], np.float32)


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


def save(name, data, path, colorspace):
    """data (h, w, 3) -> image 'name' saved to path and kept linked to it."""
    hh, w = data.shape[:2]
    img = bpy.data.images.get(name) or bpy.data.images.new(name, w, hh)
    img.scale(w, hh)
    img.pixels.foreach_set(np.concatenate([data, np.ones((hh, w, 1), np.float32)], 2).astype(np.float32).ravel())
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.filepath_raw = path; img.file_format = 'PNG'; img.save()
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

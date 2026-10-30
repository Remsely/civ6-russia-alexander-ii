"""The game's side of the 3D leader around the FBX from art/3d/export_leader.py.

.venv\\Scripts\\python.exe art\\3d\\make_leader_asset.py [--no-fgx]

1. FBX -> .fgx (tools/fbx_to_fgx.ps1): mod/Geometries/AlexanderII.fgx/.wig, mod/Animations/AlexanderII_Idle.fgx
   (--no-fgx: keep the .fgx files there are);
2. mod/Geometries/AlexanderII.geo - meshes, triangle groups and bones as they are in the .fgx (tools/fgx_info.ps1, the
   same reading the Asset Editor does on import). Counts guessed from Blender instead (vertices, bound bones a few
   off) left the game showing no leader at all;
3. mod/Animations/AlexanderII_Idle.anm - the idle loop, its length;
4. mod/Textures/LEAD_REMSELY_ALEXANDER_II_<part>_<map>.dds/.tex and mod/Materials/LEAD_REMSELY_ALEXANDER_II_<part>.mtl -
   a material of class Leader a part (the triangle group's name), its maps from art/3d/textures as the .blend's materials
   use them: BaseColor (albedo), Normal (as baked, OpenGL), Metalness and Gloss (1 - roughness) from the MR map
   (R metal, G roughness) or the material's constants, AO (the tunic's own, white elsewhere), no anisotropy or fuzz,
   the vanilla flat tangents. Material and texture settings as Peter's tunic (LEAD_RUSS_Peter_Uniform.mtl/_*.tex),
   single-channel maps one byte a pixel;
5. mod/Assets/AlexanderII.ast - Peter's (DSG, timelines, cook params, his camera and shadow box) with our body, a group
   state a mesh with its material, and the idle in every animation slot.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from lxml import etree
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from make_art import write_dds  # noqa: E402

MOD = ROOT / "mod"
EXPORT = ROOT / "art" / "build" / "export"
TEX = ROOT / "art" / "3d" / "textures"
PANTRY = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization VI SDK Assets\Civ6\pantry")
NAME = "AlexanderII"
ANIM = "AlexanderII_Idle"
PREFIX = "LEAD_REMSELY_ALEXANDER_II_"
# part -> (albedo, normal, MR map or (metal, roughness) constants, AO) - as the .blend's materials (Principled BSDF)
PARTS = {
    "Uniform": ("uniform_albedo", "uniform_normal", (0.0, 0.95), "uniform_ao"),
    "Hands": ("hands_albedo", "hands_normal", (0.0, 0.5), None),
    "Head": ("head_albedo", "head_normal", "head_mr", None),
    "Eyes": ("eye_albedo", None, (0.0, 0.12), None),
    "Details": ("details_albedo", "details_normal", "details_mr", None),
    "Regalia": ("regalia_albedo", "regalia_normal", "regalia_mr", None),
    "Orders": ("orders_albedo", "orders_normal", "orders_mr", None),
}
FLAT = 8  # constant maps (flat normal, white AO, one metalness or gloss): this many pixels a side
# map -> (texture class, pixel format, gamma, cook params) as Peter's
MAPS = {
    "BaseColor": ("Leader_BaseColor", "PF_R8G8B8A8_UNORM", 2.2, (("Skip Compression", False), ("Quality Loss - Luma", 2),
                  ("Quality Loss - Chroma", 2), ("Resolution Loss - Luma", 0), ("Resolution Loss - Chroma", 2))),
    "Normal": ("Leader_Normal", "PF_R8G8B8A8_UNORM", 1.0, (("Quality Loss", 2), ("Skip Compression", False))),
    "Metalness": ("Leader_Metalness", "PF_R8_UNORM", 1.0, (("Quality Loss", 3), ("Skip Compression", False))),
    "Gloss": ("Leader_Gloss", "PF_R8_UNORM", 1.0, (("Quality Loss", 3), ("Skip Compression", False))),
    "AO": ("Leader_AO", "PF_R8_UNORM", 1.0, (("Quality Loss", 3), ("Skip Compression", False))),
    "Anisotropy": ("Leader_Anisotropy", "PF_R8G8B8A8_UNORM", 1.0, (("Quality Loss", 4), ("Skip Compression", False))),
    "Fuzz": ("Leader_Fuzz", "PF_R8_UNORM", 1.0, (("Quality Loss", 3), ("Skip Compression", False))),
}
SUFFIX = {"BaseColor": "albedo", "Normal": "normal", "Metalness": "metalness", "Gloss": "gloss", "AO": "ao",
          "Anisotropy": "anisotropy", "Fuzz": "fuzz"}
# Every vanilla material of class Leader fills Anisotropy, Tangent and Fuzz; with them left empty (as in
# Empty_Leader_Material.mtl) the game showed no leader at all. Ours: none of either effect (black, as the unbrushed parts
# of Peter's maps), and the shared flat tangents ten vanilla materials use.
TANGENT = "horizontal_tangents"


def fgx():
    ps = ["powershell", "-STA", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "tools" / "fbx_to_fgx.ps1")]
    for args in (["-Fbx", str(EXPORT / f"{NAME}.fbx"), "-Mode", "Geometry", "-Node", NAME, "-Out", str(MOD / "Geometries"), "-Name", NAME],
                 ["-Fbx", str(EXPORT / f"{ANIM}.fbx"), "-Mode", "Animation", "-Node", NAME, "-Out", str(MOD / "Animations"), "-Name", ANIM]):
        r = subprocess.run(ps + args, capture_output=True, text=True, errors="replace")
        print(r.stdout.strip(), r.stderr.strip())


def fgx_info():
    out = EXPORT / f"{NAME}_fgx.json"
    r = subprocess.run(["powershell", "-STA", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "tools" / "fgx_info.ps1"),
                        "-Fgx", str(MOD / "Geometries" / f"{NAME}.fgx"), "-Out", str(out)],
                       capture_output=True, text=True, errors="replace")
    print(r.stdout.strip(), r.stderr.strip())
    info = json.loads(out.read_text(encoding="utf-8-sig"))
    for m in info["meshes"]:
        assert len(m["groups"]) == 1, m  # a mesh = one material = one triangle group (export_leader.py)
        m["group"] = m["groups"][0]
    return info


def parse(path):
    return etree.parse(str(path), etree.XMLParser(remove_blank_text=True))


def save(tree, path):
    path.parent.mkdir(exist_ok=True)
    tree.write(str(path), encoding="UTF-8", xml_declaration=True, pretty_print=True)
    print("wrote", path.relative_to(ROOT))


def sub(parent, tag, text=None, value=None):
    el = etree.SubElement(parent, tag)
    if text is not None:
        el.set("text", text)
    if value is not None:
        el.text = str(value)
    return el


def geo(info):
    tree = parse(MOD / "Geometries" / f"{NAME}.geo")  # cook params (hair) and layout of the first one, by the editor
    g = tree.getroot()
    meshes = g.find("m_Meshes")
    meshes.clear()
    for m in info["meshes"]:
        el = sub(meshes, "Element")
        sub(el, "m_Name", m["name"])
        groups = sub(el, "m_Groups")
        gr = sub(groups, "Element")
        sub(gr, "m_Name", m["group"])
        sub(gr, "m_nFirstPrim", value=0)
        sub(gr, "m_nPrims", value=m["tris"])
        sub(el, "m_nBoundBoneCount", value=m["bound_bones"])
        sub(el, "m_nPrimitiveCount", value=m["tris"])
        sub(el, "m_nVertexCount", value=m["verts"])
    bones = g.find("m_Bones")
    bones.clear()
    for b in info["bones"]:
        sub(bones, "Element", b)
    g.find("m_ModelName").set("text", info["model"])
    g.find("m_SourceFilePath").set("text", f"//civ6/main/art\\build\\export\\{NAME}.fbx")
    g.find("m_SourceObjectName").set("text", info["model"])
    save(tree, MOD / "Geometries" / f"{NAME}.geo")


def anm(info):
    old = MOD / "Animations" / "AlexanderIIBreathing.anm"
    path = MOD / "Animations" / f"{ANIM}.anm"
    tree = parse(path if path.exists() else old)
    a = tree.getroot()
    a.find("m_fDuration").text = "%.6f" % info["duration"]
    a.find("m_SourceFilePath").set("text", f"//civ6/main/art\\build\\export\\{ANIM}.fbx")
    a.find("m_SourceObjectName").set("text", NAME)
    a.find("m_DataFiles/Element/m_RelativePath").set("text", f"{ANIM}.fgx")
    a.find("m_Name").set("text", ANIM)
    save(tree, path)
    for f in (old, old.with_suffix(".fgx")):  # the pipeline test's breathing, replaced
        if f.exists():
            f.unlink()
            print("removed", f.relative_to(ROOT))


def tex_xml(name, kind, size, mips):
    cls, fmt, gamma, params = MAPS[kind]
    t = parse(PANTRY / "Textures" / "LEAD_RUSS_Peter_Uniform_gloss.tex").getroot()
    t.find("m_ExportSettings/ePixelformat").text = fmt
    t.find("m_ExportSettings/fGammaIn").text = t.find("m_ExportSettings/fGammaOut").text = "%.6f" % gamma
    vals = t.find("m_CookParams/m_Values")
    vals.clear()
    for pname, v in params:
        el = sub(vals, "Element")
        if isinstance(v, bool):
            el.set("class", "AssetObjects..BoolValue")
            sub(el, "m_bValue", value=str(v).lower())
        else:
            el.set("class", "AssetObjects..IntValue")
            sub(el, "m_nValue", value=v)
        sub(el, "m_ParamName", pname)
    t.find("m_Height").text, t.find("m_Width").text = str(size[1]), str(size[0])
    t.find("m_NumMipMaps").text = str(mips)
    t.find("m_SourceFilePath").set("text", f"Textures\\{name}.dds")
    t.find("m_ExportedTime").text = "0"
    t.find("m_ClassName").set("text", cls)
    t.find("m_DataFiles/Element/m_RelativePath").set("text", f"{name}.dds")
    t.find("m_Name").set("text", name)
    tags = t.find("m_Tags")
    tags.clear()
    for tag in (cls, "Leader", kind):
        sub(tags, "Element", tag)
    return etree.ElementTree(t)


def gray(v):
    return Image.fromarray(np.full((FLAT, FLAT), round(255 * v), np.uint8))


def textures(part):
    albedo, normal, mr, ao = PARTS[part]
    maps = {"BaseColor": Image.open(TEX / f"{albedo}.png").convert("RGB")}
    maps["Normal"] = (Image.open(TEX / f"{normal}.png").convert("RGB") if normal
                      else Image.new("RGB", (FLAT, FLAT), (128, 128, 255)))
    if isinstance(mr, str):
        a = np.asarray(Image.open(TEX / f"{mr}.png").convert("RGB"))
        maps["Metalness"] = Image.fromarray(a[..., 0])
        maps["Gloss"] = Image.fromarray(255 - a[..., 1])
    else:
        maps["Metalness"], maps["Gloss"] = gray(mr[0]), gray(1.0 - mr[1])
    maps["AO"] = Image.open(TEX / f"{ao}.png").convert("L") if ao else gray(1.0)
    maps["Anisotropy"] = Image.new("RGBA", (FLAT, FLAT), (0, 0, 0, 255))
    maps["Fuzz"] = gray(0.0)
    names = {"Tangent": TANGENT}
    for kind, im in maps.items():
        name = f"{PREFIX}{part}_{SUFFIX[kind]}"
        r8 = MAPS[kind][1] == "PF_R8_UNORM"  # one byte a pixel, as the .tex says (Peter's gloss/metalness/AO)
        mips = write_dds(im, MOD / "Textures" / f"{name}.dds", mips=True, r8=r8)
        save(tex_xml(name, kind, im.size, mips), MOD / "Textures" / f"{name}.tex")
        names[kind] = name
    return names


def material(part, names):
    # Peter's tunic (class Leader, as the game uses it: translucency colour, version) with our maps in its slots
    tree = parse(PANTRY / "Materials" / "LEAD_RUSS_Peter_Uniform.mtl")
    m = tree.getroot()
    for el in m.find("m_CookParams/m_Values"):
        kind = el.find("m_ParamName").get("text")
        if kind in names:
            el.find("m_ObjectName").set("text", names[kind])
    m.find("m_Name").set("text", PREFIX + part)
    save(tree, MOD / "Materials" / f"{PREFIX}{part}.mtl")


def ast(info):
    tree = parse(PANTRY / "Assets" / "LEAD_RUSS_Peter.ast")
    a = tree.getroot()
    for el in a.iter("m_AnimationName"):
        el.set("text", ANIM)
    models = a.find("m_GeometrySet/m_ModelInstances")
    body = next(m for m in models if m.find("m_Name").get("text") == "Root")
    body.find("m_GeoName").set("text", NAME)
    states = body.find("m_GroupStates")
    proto = states[0]
    for s in list(states):
        states.remove(s)
    for m in info["meshes"]:
        s = etree.fromstring(etree.tostring(proto))
        s.find("m_MeshName").set("text", m["name"])
        s.find("m_GroupName").set("text", m["group"])
        s.find(".//m_ObjectName").set("text", m["group"])
        states.append(s)
    a.find("m_Name").set("text", NAME)
    save(tree, MOD / "Assets" / f"{NAME}.ast")


def main():
    if "--no-fgx" not in sys.argv:
        fgx()
    info = fgx_info()
    geo(info)
    anm(json.loads((EXPORT / f"{ANIM}.json").read_text(encoding="utf-8")))
    for part in PARTS:
        material(part, textures(part))
    ast(info)


if __name__ == "__main__":
    main()

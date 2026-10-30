"""Pipeline smoke test: build Assets/AlexanderII.ast from the vanilla LEAD_RUSS_Peter.ast.

.venv\\Scripts\\python.exe art\\3d\\test\\make_test_ast.py

Keeps Peter's DSG, timelines, cook params, camera and shadow box (vanilla entities, fine for the previewer);
binds every animation slot to our idle and swaps his body for our geometry with one placeholder material.
"""
import copy
import sys
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parents[3]
MOD = ROOT / "mod"
PETER = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization VI SDK Assets\Civ6\pantry\Assets\LEAD_RUSS_Peter.ast")
NAME = "AlexanderII"
GEO = "AlexanderII"
ANIM = "AlexanderIIBreathing"
CAMERA_GEO = "AlexanderII_Camera"  # our camera (--our-camera), from art/3d/test/LEAD_REMSELY_TEST_Camera.fbx
# triangle group (= FBX material) and mesh names from Geometries/AlexanderII.geo
GROUPS = [("Body", "LEAD_REMSELY_TEST_Skin", "LEAD_RUSS_Peter_Skin")]


def main():
    tree = etree.parse(str(PETER), etree.XMLParser(remove_blank_text=True))
    ast = tree.getroot()
    if "--peter" in sys.argv:
        # bisect: Peter's own body, animations and materials, only our name and camera (is our geometry the problem?)
        models = ast.find("m_GeometrySet/m_ModelInstances")
        return save(tree, ast, models)
    for el in ast.iter("m_AnimationName"):
        el.set("text", ANIM)
    models = ast.find("m_GeometrySet/m_ModelInstances")
    body = next(m for m in models if m.find("m_Name").get("text") == "Root")
    body.find("m_GeoName").set("text", GEO)
    states = body.find("m_GroupStates")
    proto = copy.deepcopy(states[0])
    for s in list(states):
        states.remove(s)
    for mesh, group, material in GROUPS:
        s = copy.deepcopy(proto)
        s.find("m_MeshName").set("text", mesh)
        s.find("m_GroupName").set("text", group)
        s.find(".//m_ObjectName").set("text", material)
        states.append(s)
    return save(tree, ast, models)


def save(tree, ast, models):
    # Peter's camera by default: our FBX camera has the same transform but renders black (the Maya-exported
    # .fgx is 3x larger, probably lens data our FBX export lacks); --our-camera to test ours
    if "--our-camera" in sys.argv:
        cam = next(m for m in models if m.find("m_GeoName").get("text") == "LEAD_RUSS_Peter_Camera")
        cam.find("m_Name").set("text", CAMERA_GEO)
        cam.find("m_GeoName").set("text", CAMERA_GEO)
    ast.find("m_Name").set("text", NAME)
    out = MOD / "Assets" / f"{NAME}.ast"
    out.parent.mkdir(exist_ok=True)
    tree.write(str(out), encoding="UTF-8", xml_declaration=True, pretty_print=True)
    print("wrote", out)


if __name__ == "__main__":
    main()

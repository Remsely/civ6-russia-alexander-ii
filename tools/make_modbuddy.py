"""Generate the ModBuddy project files from mod/RemselysAlexanderII.modinfo.

python tools/make_modbuddy.py

Writes RemselysAlexanderII.civ6sln (repo root) and mod/RemselysAlexanderII.civ6proj, mod/RemselysAlexanderII.Art.xml.
The project lives in mod/ because the Asset Editor and the cooker scan the whole project folder (the "pantry"):
in the repo root they would also pick up reference/ (junctions to the game, DLC and SDK samples) and .venv.
The .modinfo stays the source of truth: id, properties, actions and <Files> are copied from it, so a ModBuddy
build (Mods/RemselysAlexanderII + cooked BLPs) matches tools/install.py. The art specification is the one
from the EmptyMod1 project the BLPs were first cooked in (requires Expansion2 art, same consumers/libraries).
Re-run after editing the .modinfo.
"""
import sys
import uuid
from pathlib import Path
from xml.sax.saxutils import escape

from lxml import etree

ROOT = Path(__file__).resolve().parent.parent
NAME = "RemselysAlexanderII"
MOD = ROOT / "mod"
MODINFO = MOD / f"{NAME}.modinfo"
# Fixed so regenerating does not churn the solution file.
PROJECT_GUID = "7d0c3b8e-5f21-4c6a-9a4e-2b8f1e6d3c95"
MOD_PROJECT_TYPE = "5DAE07AF-E217-45C1-8DE7-FF99D6011E8A"  # ModBuddy Civ6 project type

SLN = f"""Microsoft Visual Studio Solution File, Format Version 12.00
# ModBuddy Solution File, Format Version 12.00
VisualStudioVersion = 12.0.21005.1
MinimumVisualStudioVersion = 10.0.40219.1
Project("{{{MOD_PROJECT_TYPE}}}") = "{NAME}", "mod\\{NAME}.civ6proj", "{{{PROJECT_GUID.upper()}}}"
EndProject
Global
\tGlobalSection(SolutionConfigurationPlatforms) = preSolution
\t\tDefault|Civ6 = Default|Civ6
\tEndGlobalSection
\tGlobalSection(ProjectConfigurationPlatforms) = postSolution
\t\t{{{PROJECT_GUID.upper()}}}.Default|Civ6.ActiveCfg = Default|Civ6
\t\t{{{PROJECT_GUID.upper()}}}.Default|Civ6.Build.0 = Default|Civ6
\tEndGlobalSection
\tGlobalSection(SolutionProperties) = preSolution
\t\tHideSolutionNode = FALSE
\tEndGlobalSection
EndGlobal
"""

# Art consumers and game libraries of the EmptyMod1 art specification (ModBuddy's default list).
CONSUMERS = [
    ("Units", ["Unit", "VFX", "Light"]), ("Clutter", ["Landmark"]),
    ("Landmarks", ["CityBuildings", "TileBase", "RouteDecalMaterial"]), ("Farms", ["TileBase", "CityBuildings"]),
    ("GameLighting", ["ColorKey", "GameLighting"]), ("StrategicView_Properties", None),
    ("StrategicView_Sprite", ["StrategicView_Sprite", "StrategicView_DirectedAsset"]),
    ("StrategicView_Route", ["StrategicView_Route", "StrategicView_DirectedAsset"]),
    ("StrategicView_TerrainType", ["StrategicView_TerrainBlend", "StrategicView_TerrainBlendCorners",
                                   "StrategicView_TerrainType", "StrategicView_DirectedAsset"]),
    ("StrategicView_TerrainBlendCorners", ["StrategicView_TerrainBlendCorners", "StrategicView_DirectedAsset"]),
    ("StrategicView_TerrainBlend", ["StrategicView_TerrainBlend", "StrategicView_DirectedAsset"]),
    ("Terrain", ["TerrainAsset", "TerrainElement", "TerrainMaterial"]),
    ("WorldViewRoutes", ["RouteDecalMaterial", "RouteDoodad"]), ("UI", ["UITexture"]),
    ("FOW", ["FOWSprite", "FOWTexture"]), ("WonderMovie", ["WonderMovie", "TileBase", "GameLighting", "ColorKey"]),
    ("UILensAsset", ["OverlayTexture", "UILensAsset"]), ("Overlay", ["OverlayTexture", "UILensAsset"]),
    ("VFX", ["VFX", "Light"]), ("Water", ["Water"]), ("ColorKeys", ["ColorKey"]), ("ScreenWashEffects", ["ColorKey"]),
    ("Camera", None), ("Terrains", None), ("Features", None), ("Civilizations", None), ("Cultures", None),
    ("Resources", None), ("Improvements", None), ("WorldView_Translate", None), ("StrategicView_Translate", None),
    ("Audio", None), ("LeaderLighting", ["LeaderLighting", "ColorKey"]),
    ("Leaders", ["Leader", "LeaderLighting", "ColorKey"]), ("LeaderFallback", ["LeaderFallback"]),
    ("Lenses", None), ("IndirectGrid", None), ("AOSystem", None), ("GenericObject", None), ("Wave", ["Wave"]),
    ("DynamicGeometry", ["DynamicGeometry"]), ("UIPreview", None), ("SkyBox", ["SkyBoxTexture"]),
    ("Minimap", None), ("UnitSimulation", None), ("RangeArrows", ["OverlayTexture", "UILensAsset"]),
]
LIBRARIES = sorted({lib for _, libs in CONSUMERS for lib in libs or []})


def art_xml(mod_id: str) -> str:
    """The ArtDef cook writes the mod's .dep from this file, so artdefs, packages and required art come from our .dep
    (consumers of the EmptyMod1 spec fill the rest). Package paths are written without .blp, as in vanilla Art.xml."""
    dep = etree.parse(str(MOD / f"{NAME}.dep")).getroot()
    own_artdefs = {p.name for p in (MOD / "ArtDefs").glob("*.artdef")}
    dep_artdefs = {e.findtext("ConsumerName") or e.find("ConsumerName").get("text"):
                   [x.get("text") for x in e.find("ArtDefDependencyPaths") if x.get("text") in own_artdefs]
                   for e in dep.find("SystemDependencies")}
    dep_packages = {e.find("LibraryName").get("text"): [x.get("text").removesuffix(".blp") for x in e.find("PackageDependencies")]
                    for e in dep.find("LibraryDependencies")}
    required = [(e.find("name").get("text"), e.find("id").get("text")) for e in dep.find("RequiredGameArtIDs")]
    out = ['<?xml version="1.0" encoding="UTF-8" ?>', "<AssetObjects..GameArtSpecification>",
           "  <id>", f'    <name text="{NAME}"/>', f'    <id text="{mod_id}"/>', "  </id>", "  <artConsumers>"]
    for name, libs in CONSUMERS:
        out += ["    <Element>", f'      <consumerName text="{name}"/>']
        paths = dep_artdefs.get(name, [])
        out += (["      <relativeArtDefPaths>"] + [f'        <Element text="{p}"/>' for p in paths]
                + ["      </relativeArtDefPaths>"]) if paths else ["      <relativeArtDefPaths/>"]
        if libs:
            out += ["      <libraryDependencies>"] + [f'        <Element text="{l}"/>' for l in libs]
            out += ["      </libraryDependencies>", "      <loadsLibraries>true</loadsLibraries>"]
        else:
            out += ["      <libraryDependencies/>", "      <loadsLibraries>false</loadsLibraries>"]
        out += ["    </Element>"]
    out += ["  </artConsumers>", "  <gameLibraries>"]
    for lib in sorted(set(LIBRARIES) | set(dep_packages)):
        pkgs = dep_packages.get(lib, [])
        out += ["    <Element>", f'      <libraryName text="{lib}"/>']
        out += (["      <relativePackagePaths>"] + [f'        <Element text="{p}"/>' for p in pkgs]
                + ["      </relativePackagePaths>"]) if pkgs else ["      <relativePackagePaths/>"]
        out += ["    </Element>"]
    out += ["  </gameLibraries>", "  <requiredGameArtIDs>"]
    for name, art_id in required:
        out += ["    <Element>", f'      <name text="{name}" />', f'      <id text="{art_id}" />', "    </Element>"]
    out += ["  </requiredGameArtIDs>", "</AssetObjects..GameArtSpecification>", ""]
    return "\n".join(out)


def inner_xml(el) -> str:
    """The element serialised as-is (ModBuddy pastes these blocks into the generated .modinfo)."""
    return etree.tostring(el, encoding="unicode").strip() if el is not None else ""


def civ6proj(mi) -> str:
    props = mi.find("Properties")
    text = lambda tag, default="": (props.findtext(tag) or default).strip()
    deps = mi.find("Dependencies")
    assoc = "<Associations>" + "".join(
        f'<Dependency type="Dlc" title="{escape(d.get("title"), {chr(34): "&quot;"})}" id="{d.get("id")}" />'
        for d in (deps if deps is not None else [])) + "</Associations>"
    files = [f.text.strip() for f in mi.findall("./Files/File")]
    content = "\n".join(f'    <Content Include="{escape(f.replace("/", chr(92)))}">\n'
                        f"      <SubType>Content</SubType>\n    </Content>" for f in files)
    folders = sorted({str(Path(f).parent).replace("/", "\\") for f in files} - {"."})
    yes = lambda v: "true" if v.strip() in ("1", "true") else "false"
    return f"""﻿<?xml version="1.0" encoding="utf-8"?>
<!-- Generated by tools/make_modbuddy.py from {NAME}.modinfo. Do not edit by hand: edit the .modinfo and re-run. -->
<Project ToolsVersion="12.0" DefaultTargets="Default" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
  <PropertyGroup>
    <Configuration Condition=" '$(Configuration)' == '' ">Default</Configuration>
    <Name>{escape(text("Name"))}</Name>
    <Guid>{mi.get("id")}</Guid>
    <ProjectGuid>{PROJECT_GUID}</ProjectGuid>
    <ModVersion>{mi.get("version", "1")}</ModVersion>
    <Teaser>{escape(text("Teaser"))}</Teaser>
    <Description>{escape(text("Description"))}</Description>
    <Authors>{escape(text("Authors"))}</Authors>
    <SpecialThanks>
    </SpecialThanks>
    <AffectsSavedGames>{yes(text("AffectsSavedGames", "1"))}</AffectsSavedGames>
    <SupportsSinglePlayer>true</SupportsSinglePlayer>
    <SupportsMultiplayer>true</SupportsMultiplayer>
    <SupportsHotSeat>true</SupportsHotSeat>
    <CompatibleVersions>{text("CompatibleVersions")}</CompatibleVersions>
    <AssociationData><![CDATA[{assoc}]]></AssociationData>
    <AssemblyName>{NAME}</AssemblyName>
    <RootNamespace>{NAME}</RootNamespace>
    <FrontEndActionData><![CDATA[{inner_xml(mi.find("FrontEndActions"))}]]></FrontEndActionData>
    <InGameActionData><![CDATA[{inner_xml(mi.find("InGameActions"))}]]></InGameActionData>
  </PropertyGroup>
  <PropertyGroup Condition=" '$(Configuration)' == 'Default' ">
    <OutputPath>.</OutputPath>
  </PropertyGroup>
  <ItemGroup>
    <None Include="{NAME}.Art.xml" />
    <None Include="{NAME}.modinfo" />
  </ItemGroup>
  <ItemGroup>
{chr(10).join(f'    <Folder Include="{d}" />' for d in folders)}
  </ItemGroup>
  <ItemGroup>
{content}
  </ItemGroup>
  <Import Project="$(MSBuildLocalExtensionPath)Civ6.targets" />
  <!-- The ArtDef cook writes its own {NAME}.dep from the .Art.xml (no package lists): put ours back, the game loads BLPs from it. -->
  <Target Name="RestoreDep" AfterTargets="Build">
    <Copy SourceFiles="{NAME}.dep" DestinationFolder="$(BuildDir)" />
    <Message Text="Restored {NAME}.dep" />
  </Target>
</Project>
"""


def main() -> int:
    mi = etree.parse(str(MODINFO), etree.XMLParser(remove_blank_text=True)).getroot()
    uuid.UUID(mi.get("id"))  # sanity check
    missing = [f.text for f in mi.findall("./Files/File") if not (MOD / f.text.strip()).exists()]
    if missing:
        print("missing files listed in .modinfo:", *missing, sep="\n  ")
        return 1
    for path, body, enc in ((ROOT / f"{NAME}.civ6sln", SLN, "utf-8-sig"), (MOD / f"{NAME}.civ6proj", civ6proj(mi), "utf-8"),
                            (MOD / f"{NAME}.Art.xml", art_xml(mi.get("id")), "utf-8")):
        path.write_text(body, encoding=enc, newline="\r\n")
        print("wrote", path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())

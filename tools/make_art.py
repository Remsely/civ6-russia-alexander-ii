"""Генерирует арт-файлы мода по образцу JFD Russia - Elisabeth (reference/samples/JFD-Russia-Elisabeth).

Берёт art/build/* (результат tools/slice_art.py) и пишет в мод (mod/):
  Textures/*.dds, Textures/*.tex   - несжатый RGBA DDS (заголовок как в образце) и описание текстуры для Asset Editor
  XLPs/Icons.xlp, XLPs/LeaderFallbacks.xlp
  ArtDefs/FallbackLeaders.artdef, ArtDefs/Leaders.artdef, ArtDefs/UserInterface.artdef
  RemselysAlexanderII.dep
  Data/Icons.sql                   - IconTextureAtlases / IconDefinitions
Не создаёт .blp: их собирает Asset Editor (см. README, раздел про арт).

Запуск: .venv\\Scripts\\python.exe tools\\make_art.py
"""
import re
import struct
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "art" / "build"
MOD = ROOT / "mod"
TEXTURES = MOD / "Textures"

LEADER = "LEADER_REMSELY_ALEXANDER_II"
ICON_SIZES = (256, 80, 64, 55, 50, 48, 45, 32)
PORTRAIT = f"{LEADER}_NEUTRAL"
FALLBACK = "FALLBACK_NEUTRAL_REMSELY_ALEXANDER_II"
PORTRAIT_SELECT = f"{LEADER}_SELECT"  # Players.Portrait (карточка на экране выбора лидера, другой кадр)
BACKGROUND_LOADING = f"{LEADER}_BACKGROUND"  # LoadingInfo.BackgroundImage
ATLAS = "ICON_ATLAS_REMSELY_ALEXANDER_II"
DEP_GUID = "9c1f5b0e-4a3d-4f7e-8b21-6d5a0c9e7f13"
DEP_NAME = "Remsely's Alexander II"


def icon_name(size: int) -> str:
    return f"RemselysAlexanderII_Icon{size}"


def write_dds(image: Image.Image, path: Path, mips: bool) -> int:
    """Несжатый RGBA8 DDS: маски R=ff, G=ff00, B=ff0000, A=ff000000 (как у файлов Firaxis/JFD)."""
    image = image.convert("RGBA")
    levels = [image]
    if mips:
        while levels[-1].width > 1 or levels[-1].height > 1:
            last = levels[-1]
            levels.append(last.resize((max(1, last.width // 2), max(1, last.height // 2)), Image.BOX))
    header = bytearray(128)
    header[0:4] = b"DDS "
    struct.pack_into("<I", header, 4, 124)
    struct.pack_into("<I", header, 8, 0x21007)  # CAPS | HEIGHT | WIDTH | PIXELFORMAT | MIPMAPCOUNT
    struct.pack_into("<II", header, 12, image.height, image.width)
    struct.pack_into("<I", header, 24, 0)  # depth
    struct.pack_into("<I", header, 28, len(levels))
    struct.pack_into("<IIIIIIII", header, 76, 32, 0x41, 0, 32, 0xFF, 0xFF00, 0xFF0000, 0xFF000000)
    struct.pack_into("<I", header, 108, 0x401008)  # caps: COMPLEX | TEXTURE | MIPMAP
    path.write_bytes(bytes(header) + b"".join(level.tobytes() for level in levels))
    return len(levels) - 1


TEX_TEMPLATE = """<?xml version="1.0" encoding="UTF-8" ?>
<AssetObjects:TextureInstance>
	<m_ExportSettings>
		<ePixelformat>PF_R8G8B8A8_UNORM</ePixelformat>
		<eFilterType>FT_BOX</eFilterType>
		<bUseMips>{use_mips}</bUseMips>
		<iNumManualMips>0</iNumManualMips>
		<bCompleteMipChain>true</bCompleteMipChain>
		<fValueClampMin>0.000000</fValueClampMin>
		<fValueClampMax>1.000000</fValueClampMax>
		<fSupportScale>1.000000</fSupportScale>
		<fGammaIn>2.200000</fGammaIn>
		<fGammaOut>2.200000</fGammaOut>
		<iSlabWidth>0</iSlabWidth>
		<iSlabHeight>0</iSlabHeight>
		<iColorKeyX>64</iColorKeyX>
		<iColorKeyY>64</iColorKeyY>
		<iColorKeyZ>64</iColorKeyZ>
		<eExportMode>TEXTURE_2D</eExportMode>
		<bSampleFromTopLayer>false</bSampleFromTopLayer>
	</m_ExportSettings>
	<m_CookParams>
		<m_Values/>
	</m_CookParams>
	<m_Version>
		<major>1</major>
		<minor>0</minor>
		<build>0</build>
		<revision>0</revision>
	</m_Version>
	<m_Height>{height}</m_Height>
	<m_Width>{width}</m_Width>
	<m_Depth>1</m_Depth>
	<m_NumMipMaps>{mip_count}</m_NumMipMaps>
	<m_SourceFilePath text="Textures\\{name}.dds"/>
	<m_SourceObjectName text=""/>
	<m_ImportedTime>0</m_ImportedTime>
	<m_ExportedTime>0</m_ExportedTime>
	<m_ClassName text="{class_name}"/>
	<m_DataFiles>
		<Element>
			<m_ID text="DDS"/>
			<m_RelativePath text="{name}.dds"/>
		</Element>
	</m_DataFiles>
	<m_Name text="{name}"/>
	<m_Description text=""/>
	<m_Tags>
{tags}
	</m_Tags>
	<m_Groups/>
</AssetObjects:TextureInstance>
"""


def write_texture(image: Image.Image, name: str, fallback: bool = False) -> None:
    mip_count = write_dds(image, TEXTURES / f"{name}.dds", mips=fallback)
    tags = ("Leader_Fallback", "Leader", "Fallback") if fallback else ("UserInterface",)
    text = TEX_TEMPLATE.format(
        use_mips="true" if fallback else "false",
        height=image.height, width=image.width, mip_count=mip_count, name=name,
        class_name="Leader_Fallback" if fallback else "UserInterface",
        tags="\n".join(f'\t\t<Element text="{tag}"/>' for tag in tags),
    )
    (TEXTURES / f"{name}.tex").write_text(text, encoding="utf-8", newline="\n")


def xlp(class_name: str, package: str, entries: list, version: tuple) -> str:
    items = "".join(
        f'\n\t\t<Element>\n\t\t\t<m_EntryID text="{e}"/>\n\t\t\t<m_ObjectName text="{e}"/>\n\t\t</Element>' for e in entries
    )
    platforms = "".join(f"\n\t\t<Element>{p}</Element>" for p in ("WINDOWS", "LINUX", "MACOS", "IOS"))
    major, minor, build, revision = version
    return f"""<?xml version="1.0" encoding="UTF-8" ?>
<AssetObjects..XLP>
	<m_Version>
		<major>{major}</major>
		<minor>{minor}</minor>
		<build>{build}</build>
		<revision>{revision}</revision>
	</m_Version>
	<m_ClassName text="{class_name}"/>
	<m_PackageName text="{package}"/>
	<m_Entries>{items}
	</m_Entries>
	<m_AllowedPlatforms>{platforms}
	</m_AllowedPlatforms>
</AssetObjects..XLP>
"""


FALLBACK_ARTDEF = f"""<?xml version="1.0" encoding="UTF-8" ?>
<AssetObjects..ArtDefSet>
	<m_Version>
		<major>4</major>
		<minor>0</minor>
		<build>253</build>
		<revision>293</revision>
	</m_Version>
	<m_TemplateName text="LeaderFallback"/>
	<m_RootCollections>
		<Element>
			<m_CollectionName text="Leaders"/>
			<m_ReplaceMergedCollectionElements>false</m_ReplaceMergedCollectionElements>
		</Element>
		<Element>
			<m_CollectionName text="Leaders"/>
			<m_ReplaceMergedCollectionElements>false</m_ReplaceMergedCollectionElements>
			<Element>
				<m_Fields>
					<m_Values/>
				</m_Fields>
				<m_ChildCollections>
					<Element>
						<m_CollectionName text="Animations"/>
						<m_ReplaceMergedCollectionElements>false</m_ReplaceMergedCollectionElements>
						<Element>
							<m_Fields>
								<m_Values>
									<Element class="AssetObjects..BLPEntryValue">
										<m_EntryName text="{FALLBACK}"/>
										<m_XLPClass text="LeaderFallback"/>
										<m_XLPPath text="LeaderFallbacks.xlp"/>
										<m_BLPPackage text="LeaderFallbacks"/>
										<m_LibraryName text="LeaderFallback"/>
										<m_ParamName text="BLP Entry"/>
									</Element>
								</m_Values>
							</m_Fields>
							<m_ChildCollections/>
							<m_Name text="DEFAULT"/>
							<m_AppendMergedParameterCollections>false</m_AppendMergedParameterCollections>
						</Element>
					</Element>
				</m_ChildCollections>
				<m_Name text="{LEADER}"/>
				<m_AppendMergedParameterCollections>false</m_AppendMergedParameterCollections>
			</Element>
		</Element>
	</m_RootCollections>
</AssetObjects..ArtDefSet>
"""

LEADERS_ARTDEF = f"""<?xml version="1.0" encoding="UTF-8" ?>
<AssetObjects..ArtDefSet>
	<m_Version>
		<major>4</major>
		<minor>0</minor>
		<build>253</build>
		<revision>867</revision>
	</m_Version>
	<m_TemplateName text="Leaders"/>
	<m_RootCollections>
		<Element>
			<m_CollectionName text="Leaders"/>
			<m_ReplaceMergedCollectionElements>false</m_ReplaceMergedCollectionElements>
			<Element>
				<m_Fields>
					<m_Values>
						<Element class="AssetObjects..StringValue">
							<m_Value text="Russia"/>
							<m_ParamName text="Audio"/>
						</Element>
						<Element class="AssetObjects..BLPEntryValue">
							<m_EntryName text=""/>
							<m_XLPClass text=""/>
							<m_XLPPath text=""/>
							<m_BLPPackage text=""/>
							<m_LibraryName text="Leader"/>
							<m_ParamName text="Leader_BLP_Entry"/>
						</Element>
						<Element class="AssetObjects..BLPEntryValue">
							<m_EntryName text=""/>
							<m_XLPClass text=""/>
							<m_XLPPath text="Leader_LightRigs.xlp"/>
							<m_BLPPackage text=""/>
							<m_LibraryName text="LeaderLighting"/>
							<m_ParamName text="Leader_Lightrig_BLP_Entry"/>
						</Element>
						<Element class="AssetObjects..BLPEntryValue">
							<m_EntryName text="CK_Identity"/>
							<m_XLPClass text="ColorKey"/>
							<m_XLPPath text="ColorKeys.xlp"/>
							<m_BLPPackage text="ColorKeys"/>
							<m_LibraryName text="ColorKey"/>
							<m_ParamName text="Leader_ColorKey_BLP_Entry"/>
						</Element>
						<Element class="AssetObjects..BLPEntryValue">
							<m_EntryName text=""/>
							<m_XLPClass text="Leader"/>
							<m_XLPPath text=""/>
							<m_BLPPackage text=""/>
							<m_LibraryName text=""/>
							<m_ParamName text="Leader_Background_BLP_Entry"/>
						</Element>
						<Element class="AssetObjects..StringValue">
							<m_Value text=""/>
							<m_ParamName text="Leader_Background_Animation_State"/>
						</Element>
					</m_Values>
				</m_Fields>
				<m_ChildCollections/>
				<m_Name text="{LEADER}"/>
				<m_AppendMergedParameterCollections>false</m_AppendMergedParameterCollections>
			</Element>
		</Element>
	</m_RootCollections>
</AssetObjects..ArtDefSet>
"""

UI_ARTDEF = """<?xml version="1.0" encoding="UTF-8" ?>
<AssetObjects..ArtDefSet>
	<m_Version>
		<major>4</major>
		<minor>0</minor>
		<build>253</build>
		<revision>867</revision>
	</m_Version>
	<m_TemplateName text="UserInterfaceBLPs"/>
	<m_RootCollections/>
</AssetObjects..ArtDefSet>
"""

ICONS_SQL = f"""--==========================================================================================================================
-- ICONS: leader icon (ICON_<LeaderType> is the name the UI looks up for a leader)
--==========================================================================================================================
INSERT INTO IconTextureAtlases
		(Name,		IconSize,	IconsPerRow,	IconsPerColumn,	Filename)
VALUES
""" + ",\n".join(f"\t\t('{ATLAS}',\t{s},\t1,\t1,\t'{icon_name(s)}.dds')" for s in ICON_SIZES) + f""";

INSERT INTO IconDefinitions
		(Name,	Atlas,	'Index')
VALUES	('ICON_{LEADER}',	'{ATLAS}',	0);
"""


def write_dep() -> str:
    """.dep: идентификатор мода, зависимость от арта игры, список файлов. Системные зависимости - как у образца."""
    sample = (ROOT / "reference" / "samples" / "JFD-Russia-Elisabeth" / "JFD's Russia - Elisabeth.dep").read_text(encoding="utf-8")
    start = sample.index("<SystemDependencies>")
    end = sample.index("</SystemDependencies>") + len("</SystemDependencies>")
    tail_start = sample.index("</SystemDependencies>") + len("</SystemDependencies>")
    # хвост образца после SystemDependencies (до списка файлов) переносим как есть
    after = sample[tail_start:]
    after_end = after.index("<File>") if "<File>" in after else len(after)
    head = f"""<?xml version="1.0" encoding="UTF-8" ?>
<AssetObjects..GameDependencyData>
	<ID>
		<name text="{DEP_NAME}"/>
		<id text="{DEP_GUID}"/>
	</ID>
	<RequiredGameArtIDs>
		<Element>
			<name text="Civ6"/>
			<id text="cb2f71b7-843e-4af3-9ca7-992acda9c195"/>
		</Element>
	</RequiredGameArtIDs>
	<Description>Alexander II, the Tsar Liberator: leader portrait, fallback and icons.</Description>
	<Dependencies>
	</Dependencies>
	"""
    middle = sample[start:end] + after[:after_end].rstrip()
    # записи образца про артдефы, которых у нас нет (здания, стратегический вид)
    artdefs = "".join(
        f'\t\t<Element>\n\t\t\t<ArtDefPath text="{name}.artdef"/>\n\t\t\t<ArtDefDependencyPaths/>\n\t\t</Element>\n'
        for name in ("UserInterface", "Leaders", "FallbackLeaders")
    )
    middle = re.sub(r"<ArtDefDependencies>.*?</ArtDefDependencies>", lambda _: f"<ArtDefDependencies>\n{artdefs}\t</ArtDefDependencies>", middle, flags=re.S)
    return head + middle.rstrip() + "\n"


def main() -> None:
    TEXTURES.mkdir(exist_ok=True)
    (MOD / "XLPs").mkdir(exist_ok=True)
    (MOD / "ArtDefs").mkdir(exist_ok=True)

    portrait = Image.open(BUILD / "portrait_827x1024.png")
    write_texture(portrait, PORTRAIT)
    write_texture(Image.open(BUILD / "portrait_select_827x1024.png"), PORTRAIT_SELECT)
    write_texture(Image.open(BUILD / "fallback_827x1024.png"), FALLBACK, fallback=True)
    write_texture(Image.open(BUILD / "background_loading_1920x955.png"), BACKGROUND_LOADING)
    for size in ICON_SIZES:
        write_texture(Image.open(BUILD / f"icon_{size}.png"), icon_name(size))

    icon_entries = [icon_name(s) for s in ICON_SIZES] + [PORTRAIT, PORTRAIT_SELECT, BACKGROUND_LOADING]
    (MOD / "XLPs" / "Icons.xlp").write_text(xlp("UITexture", "UI/Icons", icon_entries, (4, 0, 315, 805)), encoding="utf-8", newline="\n")
    (MOD / "XLPs" / "LeaderFallbacks.xlp").write_text(xlp("LeaderFallback", "LeaderFallbacks", [FALLBACK], (4, 0, 260, 754)), encoding="utf-8", newline="\n")
    (MOD / "ArtDefs" / "FallbackLeaders.artdef").write_text(FALLBACK_ARTDEF, encoding="utf-8", newline="\n")
    (MOD / "ArtDefs" / "Leaders.artdef").write_text(LEADERS_ARTDEF, encoding="utf-8", newline="\n")
    (MOD / "ArtDefs" / "UserInterface.artdef").write_text(UI_ARTDEF, encoding="utf-8", newline="\n")
    (MOD / "Data" / "Icons.sql").write_text(ICONS_SQL, encoding="utf-8", newline="\n")

    (MOD / "RemselysAlexanderII.dep").write_text(write_dep(), encoding="utf-8", newline="\n")
    print("Готово: mod/Textures/, mod/XLPs/, mod/ArtDefs/, mod/Data/Icons.sql, mod/RemselysAlexanderII.dep")


if __name__ == "__main__":
    main()

---
name: civ6-asset-pipeline
description: 3D-арт для Civilization VI без Asset Editor - FBX из Blender в Granny .fgx/.wig, сущности .geo/.anm/.ast, 3D-лидер (геометрия, анимация, камера LeaderCamera), чтение .fgx, координаты сцены лидера. Обязательно используй, когда речь о 3D-модели лидера, FBX, скелете, анимации, камере, .fgx/.geo/.anm/.ast, Asset Editor (запустить, импортировать, падает, не открывается), а также когда в игре вместо лидера Клеопатра, чёрный экран дипломатии или модель не та - даже если пользователь не называет Asset Editor.
---

# 3D-ассеты без Asset Editor

Asset Editor хрупкий (падает на импорте FBX-анимации, на русской локали, на чужих путях) и запускается только руками. Поэтому файлы `.fgx` делаем сами, а редактор нужен разве что один раз, чтобы создать новую сущность `.geo`.

## Как устроен 3D-лидер
- `mod/Geometries/<Имя>.geo` + `.fgx` + `.wig` — тело (класс `Leader`); `<Имя>_Camera.geo` — камера: корень и узел `LeaderCamera`, без сетки.
- `mod/Animations/<Имя>.anm` + `.fgx` — анимация; одна может стоять во всех ~28 слотах.
- `mod/Assets/<Имя>.ast` — ассет: DSG `Standard_Leader`, привязки слотов к анимациям, модели и материалы групп треугольников. Собирается скриптом по ассету Петра: `art/3d/test/make_test_ast.py`.
- Подключение в мод (XLP, `Leaders.artdef`, `.dep`, `.modinfo`): `tools/make_leader3d.py` (`--off` — назад к 2D). Сборка — скилл `civ6-mod-build`.
- Образцы: `...\Sid Meier's Civilization VI SDK Assets\Civ6\pantry\` (`Assets/LEAD_RUSS_Peter.ast`, `Geometries/LEAD_RUSS_Peter*`, `Animations/LEAD_RUSS_Peter_*`).

## Сцена лидера (прочитано из LEAD_RUSS_Peter_Camera.fgx)
Сантиметры, Z вверх, лидер смотрит на +X. `LeaderCamera` в (320, 0, 137.741), кватернион (x,y,z,w) = (0.478, 0.478, 0.521, 0.521): смотрит вдоль своей −Z, верх +Y, наклон 4.9° вниз. Импортёр берёт сырые значения FBX и не применяет трансформ корня, поэтому всё запекается в данные.

## Экспорт FBX из Blender (образец — `art/3d/test/export_test_fbx.py`, `export_test_camera.py`)
- Корневой Empty, внутри **рядом** скелет и сетка (сетка внутри арматуры не импортируется). Source Object = корень.
- У каждой сетки материал: группа треугольников = материал, без него сетка пропадает. Триангулировать.
- Данные повернуть и ×100 (`transform_apply`), `apply_scale_options='FBX_SCALE_UNITS'`, `axis_forward='Y'`, `axis_up='Z'`, `bake_space_transform=False`. С `FBX_SCALE_NONE` корень получает масштаб ×100.
- Анимация — отдельный FBX только со скелетом (`*_Anim.fbx`).
- Экспортёр Blender выкидывает постоянные каналы: удерживаемую позу (руки вниз) сделать позой покоя (`armature_apply`), в анимации только движение.
- Blender запускать в фоне: `blender -b art/3d/alexander_assembly.blend --python <скрипт>`; в живом Blender — через MCP (MCP for Blender, пакет `mcp-for-blender` в `.mcp.json`; пользователь нажимает Start MCP Server в N-панели).

## Проверка сцены: числа и кадр игры (после каждого шага сборки)
Не судить по вьюпорту и не показывать пользователю непроверенное:
```
.venv\Scripts\python.exe tools\blend.py audit art\3d\alexander_leader.blend --scene Human [--json out.json] [--full]
.venv\Scripts\python.exe tools\blend.py audit --fbx art\3d\test\LEAD_REMSELY_TEST.fbx
.venv\Scripts\python.exe tools\blend.py render art\3d\alexander_leader.blend --scene Human [--frame N] [--out art\build\x.png]
```
- `audit` (`tools/blender/audit.py`) — по каждой сетке треугольники, материалы, UV, кости, гистограмма влияний; ошибки: сетка или грани без материала, вершины с >8 костями, вершины без веса, пропавшие текстуры. Код выхода 1 при ошибках. Прогонять и по экспортированному FBX (`--fbx`): это то, что видит импортёр.
- `render` (`tools/blender/render_leader.py`) — кадр с камеры Петра, модель поставлена как при экспорте (поворот +90° по Z, рост `--target-cm`, по умолчанию 150). Пишет, где в кадре макушка и ноги (0 — низ, 1 — верх). Объектив в `.fgx` камеры не хранится: вертикальный угол 19.2° оценён по скриншотам Петра; свет нейтральный, не игровой. Сравнивать кадр с референсом (`art/source/`) и только потом показывать пользователю.
- Оба скрипта ничего не сохраняют в .blend; ~2–3 с каждый.

## FBX → .fgx
```
powershell -STA -ExecutionPolicy Bypass -File tools\fbx_to_fgx.ps1 -Fbx <fbx> -Mode List
powershell -STA -ExecutionPolicy Bypass -File tools\fbx_to_fgx.ps1 -Fbx <fbx> -Mode Geometry -Node <корень> -Out mod\Geometries -Name <Имя>
powershell -STA -ExecutionPolicy Bypass -File tools\fbx_to_fgx.ps1 -Fbx <fbx_Anim> -Mode Animation -Out mod\Animations -Name <Имя>
```
У анимации `-Node` — корневой узел (по умолчанию первый корень), **не** имя дубля: с именем дубля `.fgx` выходит без групп дорожек, и модель в игре стоит неподвижно. Проверка дампом: должна быть строка `trackgroup <корень>: N tracks`. Имя группы = `m_ModelName` тела в `.geo` (у Петра оба `Root`).

Это тот же FBX-импортёр, что вызывает Asset Editor (`Autodesk_FBXInterface`), результат совпадает. `.geo` при этом не меняется: если поменялись имена мешей, групп или костей, `.geo` нужно обновить (Asset Editor → Import или правкой XML по образцу). В `.anm` поправь `m_fDuration`, если сменилась длина.

## Проверка .fgx
`powershell -File tools\dump_fgx.ps1 <прогрев.fgx> <файл.fgx> [-Bones a,b]` — модели, кости (позиция, кватернион, масштаб), дорожки анимации. Первый файл в процессе обёртка не читает — ставь любой прогревочный (например `Animations\LEAD_RUSS_Peter_Neutral_Idle.fgx`). Пути с апострофом («Sid Meier's») не читаются: скопируй файл во временную папку. Тело с сеткой обёртка иногда не открывает (NullReference) — тогда проверяй через FBX в Blender.

## Если всё же нужен Asset Editor
Запуск — из ModBuddy (сам по себе требует аргументы проекта). Падения на старте:
- `ThemeServiceCommands` / `FormatException` — десятичный разделитель Windows запятая; нужна точка (`intl.cpl` → Числа).
- `Logs is invalid` — создать `Documents\My Games\Sid Meier's Civilization VI\Logs`.
- `FbxImporter.dll not found` — рядом с exe нужна копия `FbxImporter_Release.dll` под именем `FbxImporter.dll`.
- Висит после «GameArtSpecificationEditor» — очистить `AutoDocuments` в `%APPDATA%\AssetEditor\1.1\AppSettings.xml` (там несохранённый Untitled).
- Логи: `%APPDATA%\AssetEditor\1.1\Logs\` (свежий по времени); кэш проекта `%APPDATA%\AssetCloud\mod-*-asset-deps.json` можно удалить.
Импорт FBX-анимации в редакторе всегда падает (`ParseWigFiles`) после записи `.fgx` — не используй его, бери `fbx_to_fgx.ps1`. Превью редактора ориентацию показывает не так, как игра; верить игре.

## Симптомы в игре
- Клеопатра вместо лидера — пакет лидера не загрузился (`.dep` без пакетов, нет BLP). Смотри `ArtDef.log`: строка `Loading Package: ...leaders/<пакет>.blp`.
- Чёрный экран, пакет загружен — сначала камера. Камера из нашего FBX (то же положение и кватернион, что у Петра) даёт чёрный экран: `.fgx` Петра из Maya втрое больше, видимо там параметры объектива, которых нет в FBX-экспорте. Поэтому в ассете стоит ванильная `LEAD_RUSS_Peter_Camera` (`make_test_ast.py`, своя — `--our-camera`). Затем модель вне кадра: единицы (метры вместо см), оси (Y вверх), рост. В кадр камеры Петра на x=0 попадает примерно 56..165 см; модель MPFB масштабируется при экспорте до `TARGET_CM` (150, макушка Петра ~158).
- Модель стоит неподвижно — в `.fgx` анимации нет групп дорожек (см. «FBX → .fgx»).
- Бисекция без пересборки: временно направить `Leader_BLP_Entry` в установленном `Leaders.artdef` на ванильный пакет (`ART_LEADER_PETER`, `Leader_Peter.xlp`, `leaders/leader_peter`). Виден Пётр — подключение, свет и UI в порядке, сломан наш пакет. `make_test_ast.py --peter` — наш пакет с телом и анимациями Петра.

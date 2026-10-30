# AGENTS.md

This file provides guidance to Codex when working with code in this repository.

Codex: источник проектных скиллов — `.agents/skills/`; `.claude/skills/` и `.zcode/skills/` — зеркала. После изменения скиллов синхронизируй их через `claude-config-sync`. `AGENTS.md`, `CLAUDE.md` и конфиги MCP ведутся отдельно и обычной синхронизацией не перезаписываются.

Последние наработки импорта 3D и границы их проверки — `docs/3d-game-import.md`. При работе с импортом используй `civ6-3d-import`, при движении — `civ6-3d-animation`, при художественной проверке — `civ6-3d-review`. История и принятые решения важнее ранних предположений; успешный cooker не подтверждает корректную анимацию в игре.

## Состояние проекта

Репозиторий — мод «Remsely's Alexander II» (альтернативный лидер России для Civilization VI). Реализовано: лидер, способность «Великие реформы», повестка «Освободитель», города и столица, 31 реплика дипломатии, арт (портреты, иконки, фоны). Идут проверка в игре, вычитка текстов, полировка (см. `ROADMAP.md`).

Источники истины:
- `ROADMAP.md` / `ROADMAP.ru.md` — двуязычный план версий и задач.
- `docs/ru/design.md` / `docs/en/design.md` — двуязычный обзор дизайна; код и игровые проверки определяют фактическое поведение.
- `docs/ru/art-pipeline.md` — как собирается арт; `docs/ru/terms.md` — русские термины.
- `docs/3d-workflow-lessons.md` — выводы из истории работы над 3D, порядок визуальной проверки и причины регрессий; раннее исследование `docs/3d-research.md` сохранено как историческое.

Один репозиторий = один мод. Сам мод (то, что уходит в `Mods`) лежит в `mod/` — это проект ModBuddy (решение `RemselysAlexanderII.civ6sln` в корне). Пути файлов мода в документах (`Data/...`, `Text/...`, `.modinfo`) — относительно `mod/`. Мод вынесен из корня, потому что Asset Editor и cooker сканируют всю папку проекта, а в корне лежат `reference/` (junction на игру и SDK) и `.venv`: с ними Asset Editor падает.

## Архитектура мода

Мод лидера — это база данных, тексты, 2D-арт и 3D-ассет лидера:
- `RemselysAlexanderII.modinfo` (пишется руками) описывает файлы и действия: во FrontEnd `Data/Config.sql` (экран выбора лидера), во InGame `Data/GameDefines.sql` (всё остальное); `Data/Icons.sql` (иконка лидера), `Data/Colors.sql` (цвета), `Text/{en_US,ru_RU}.xml`, `UpdateArt` с `RemselysAlexanderII.dep`.
- `Lua/RemselysAlexanderII_Farms.lua` — смежность ферм (считает соседей, ставит свойства клетки, которые читают XML-модификаторы).
- `art/source/` — исходные картинки; `tools/slice_art.py` режет их в `art/build/` (не в git), `tools/make_art.py` генерирует `Textures/*.dds|.tex`, `XLPs/`, `ArtDefs/`, `.dep`, `Data/Icons.sql`. BLP (`Platforms/{Windows,MacOS}/BLPs/`) собирает `tools/build.py` (cooker SDK); после изменения картинок их нужно пересобрать.
- `tools/validate.py`, `tools/install.py` — проверка и установка. `art/prompts.md` — промпты для нейросетей.
- `reference/` — в `.gitignore`: ванильные файлы игры, образцы модов, копии баз.

Игру из Codex не запускай: на этом шаге объясни пользователю ручную проверку. Логи в `%LOCALAPPDATA%\Firaxis Games\Sid Meier's Civilization VI\Logs\` читай сам, если они доступны; для 3D особенно важен `ArtDef.log`.

## Окружение (Windows)

- Python-зависимости в `.venv`: `.venv\Scripts\python.exe -m pip install -r tools\requirements.txt`; запуск — `.venv\Scripts\python.exe tools\validate.py`. `sqlite3` CLI не установлен — для SQLite использовать модуль `sqlite3` из Python. `gh` стоит в `C:\Program Files\GitHub CLI\gh.exe`; способ доступа Git проверять по фактическому окружению.
- Игра: `C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization VI`; SDK (ModBuddy, Asset Editor, FireTuner) — рядом, в `... Civilization VI SDK`.
- `reference/` в `.gitignore` и состоит из junction-ссылок на установку игры: `vanilla/{Base,Expansion1,Expansion2}` (данные и тексты), `samples/DLC` (официальные DLC-лидеры как образцы), `samples/SDK-{Examples,Documentation}`. `reference/game-db/` — копии `DebugGameplay.sqlite`, `DebugLocalization.sqlite`, `DebugConfiguration.sqlite` из `%LOCALAPPDATA%\Firaxis Games\Sid Meier's Civilization VI\Cache` (перезаписываются при каждой загрузке набора правил игрой; в них могут быть следы сторонних модов).
- Моды ставятся в `Documents\My Games\Sid Meier's Civilization VI\Mods`.

## Команды

- `.venv\Scripts\python.exe tools\validate.py` — проверка: файлы из `.modinfo`, SQL прогоняется по копиям `DebugGameplay.sqlite` / `DebugConfiguration.sqlite` (ловит несуществующие таблицы и колонки, нарушения внешних ключей), парность `en_US`/`ru_RU`, префикс `REMSELY`, шесть падежей у имён, существование `LOC_`-ссылок; цвета (`UpdateColors`) проверяются по ванильным XML из `reference/vanilla/Base/UI/Colors` (в игре у таблицы `PlayerColors` нет `TextColor`, зато есть `Alt1..3`). Lua не проверяется.
- `.venv\Scripts\python.exe tools\build.py` (`--no-install`) — сборка без ModBuddy: cooker SDK собирает все `mod/XLPs/*.xlp` в `mod/Platforms/{Windows,MacOS}/BLPs` (те же аргументы, что у ModBuddy; результат совпадает байт в байт), затем `install.py`.
- `.venv\Scripts\python.exe tools\install.py` — validate + копирование файлов из `<Files>` в `Documents\My Games\...\Mods\RemselysAlexanderII` (`--remove` удаляет). После установки игру нужно перезапустить.
- `.venv\Scripts\python.exe tools\package.py` — validate + `dist/release/RemselysAlexanderII-v<версия>.zip` (+ `.sha256`) для GitHub Releases; `tools\make_preview.py` — `workshop/preview.png`. Порядок выпуска: `docs/ru/RELEASING.md`, проверка в игре: `docs/ru/TESTING.md`.
- Новый файл мода нужно внести в `<Files>` и в действие `.modinfo` вручную (`.modinfo` пишется руками).
- `.venv\Scripts\python.exe tools\make_modbuddy.py` — генерирует из `.modinfo` проект ModBuddy (`RemselysAlexanderII.civ6sln` в корне, `mod/RemselysAlexanderII.civ6proj` и `.Art.xml`; настройки арта как в первом проекте EmptyMod1, где пеклись BLP). Перезапускать после правки `.modinfo`. Cooker при сборке пишет свой `.dep` из `.Art.xml` (без списков пакетов — в игре пропадают портрет, иконка, фон и 3D-лидер), поэтому проект после сборки копирует поверх наш `mod/RemselysAlexanderII.dep` (цель `RestoreDep`). Сборка в ModBuddy кладёт мод и свежие BLP в `Mods\RemselysAlexanderII` (ту же папку, что `install.py`); BLP оттуда нужно скопировать в `Platforms/` репозитория.
- `.venv\Scripts\python.exe tools\make_leader3d.py` (`--off` — назад к 2D) — подключает 3D-ассет `mod/Assets/AlexanderII.ast`: XLP `Leader_AlexanderII.xlp`, `Leader_BLP_Entry` в `Leaders.artdef`, пакет в `.dep`, файлы в `.modinfo`. Запускать после `make_art.py` (тот перезаписывает artdef и .dep), потом `make_modbuddy.py`. Исходники 3D (FBX, скрипты экспорта) — `art/3d/`.
- Готовый лидер в игру: `blender -b art/3d/alexander_leader.blend --python art/3d/export_leader.py -- geometry` и `-- animation` (FBX в `art/build/export/`: геометрия в позе покоя, триангулированная, ≤4 костей на вершину, группа треугольников = материал `LEAD_REMSELY_ALEXANDER_II_<часть>`; петля `idle`, пересчитанная в 30 к/с, как у ванильных лидеров, кадр 1 повторён после последнего), потом `.venv\Scripts\python.exe art\3d\make_leader_asset.py` (`.fgx` через `fbx_to_fgx.ps1`, `.geo`, `AlexanderII_Idle.anm`, материалы класса `Leader` в `mod/Materials`, текстуры BaseColor/Normal/Metalness/Gloss/AO в `mod/Textures` из `art/3d/textures/*.png` — DDS не в git, `.ast`), потом `tools\build.py`. Задний план за 3D-лидером в дипломатии — не ассет, а интерфейс: `LeaderScene.lua` кладёт под модель текстуры `<LeaderType без LEADER_>_1..Leaders.SceneLayers` (у нас один слой `REMSELY_ALEXANDER_II_1` — тёмный зал из `art/source/diplomacy.png`, `slice_art.py` → `make_art.py`); без них за моделью чёрный экран.
- Проверка и работа с 3D: `tools/blend.py audit|render|clash|stress` и `art/3d/build_all.py`; перед правкой модели прочитай `docs/3d-model-operations.md` и подходящие скиллы `civ6-3d-review`, `civ6-3d-head`, `civ6-3d-animation`, `civ6-asset-pipeline`. Проверяй позу и пересечения, одноразовые операции не запускай повторно вслепую.
- `powershell -STA -ExecutionPolicy Bypass -File tools\fbx_to_fgx.ps1 -Fbx <fbx> -Mode Animation|Geometry|List -Out mod\Animations -Name <имя> [-Node <корень>]` — FBX → `.fgx` (+ `.wig`) FBX-импортёром Asset Editor, но без него (импорт FBX-анимации в самом Asset Editor пишет файл и падает). `.geo` и `.ast` создаёт `make_leader_asset.py` по фактическому `.fgx` через `tools/fgx_info.ps1`; последние настройки импортёра описаны в `docs/3d-game-import.md`. Сцена лидера (по камере Петра): сантиметры, Z вверх, лидер смотрит на +X, `LeaderCamera` в (320, 0, 137.7) смотрит вдоль своей −Z; читать `.fgx` — `tools\dump_fgx.ps1`. Камера в ассете — ванильная `LEAD_RUSS_Peter_Camera`: наша из FBX даёт чёрный экран. `-Node` у анимации — корневой узел, не имя дубля (иначе в `.fgx` нет дорожек и модель неподвижна).
- Asset Editor падает при старте (`ThemeServiceCommands`, `FormatException`), если в Windows десятичный разделитель — запятая: нужна точка (`intl.cpl` → Дополнительные параметры → Числа). Ещё ему нужна папка `Documents\My Games\Sid Meier's Civilization VI\Logs`.
- Русские термины: `docs/ru/terms.md`. Эталон структуры лидера-мода: `reference/samples/JFD-Russia-Elisabeth` (workshop-мод). Опыт перевода и формат падежей: репозиторий `..\civ6-leaders-mods-ru-localization` (`docs/TRANSLATION_GUIDE.md`).
- Пути в junction `reference/vanilla/Base` идут без `Assets`: `Base/Gameplay/Data`, `Base/Text`, `Base/UI`.
- Данные дополнений и локализации по умолчанию в базах игры соответствуют последнему загруженному набору правил: чтобы в `reference/game-db` были Rise and Fall/Gathering Storm, перед копированием нужно загрузить сохранение с ними. Базы лежат в `%LOCALAPPDATA%\Firaxis Games\Sid Meier's Civilization VI\Cache`.

## Скиллы Codex (`.agents/skills/`)

- `civ6-3d-review` — сравнение 3D-модели с портретом и проверка со всех сторон и в движении.
- `civ6-3d-head` — точечные правки головы, кожи и глаз без потери сходства и деталей.
- `civ6-3d-import` — проверенный и экспериментальный путь FBX → FGX → игровой лидер, диагностика импорта и крашей.
- `civ6-3d-animation` — движение лидера в Blender и диагностика рассинхронизации после экспорта.

- `civ6-mod-build` — сборка BLP и мода без ModBuddy (`build.py`), `.dep`/Art.xml, проверка установленного мода.
- `civ6-asset-pipeline` — 3D без Asset Editor: FBX → `.fgx`, `.geo/.anm/.ast`, сцена и камера лидера, падения Asset Editor.
- `local-3d-generation` — Hunyuan3D 2.1 в `C:\AI\HY3D2` (вне репозитория): вход, запуск через WMI по одному seed, превью, проекция референса.

- `civ6-leader-art` — арт и его грабли (BLP, размеры, имена текстур, Portrait/PortraitBackground).
- `civ6-mod-verify` — validate/install, логи игры, что валидатор не ловит.
- `civ6-leader-texts` — полный набор текстов лидера, падежи, цитаты.
- `civ6-leader-data` — SQL/Lua: города, цвета, способность, повестка.
- `civ6-mod-release` — релиз, описание, Workshop.

## Правила

- Коммиты выпусков в основной ветке (`main`/`master`): заголовок `v<версия>: <описание на английском> (#<PR>)`, например `v1.5.0-alpha: Add an animated 3D model of Alexander II to the diplomacy screen (#1)`; номер PR — при наличии. В рабочих ветках заголовок `тип(область): что изменено`, подробности и проверки — в теле при необходимости; подробная конвенция — `docs/commit-conventions.md`. Для существенного вклада Codex добавляй `Co-authored-by: Codex <codex@openai.com>`; не приписывай себе чужую работу.
- Названия таблиц, колонок, типов модификаторов, эффектов и требований брать только из `reference/game-db/DebugGameplay.sqlite` или `reference/vanilla/`, не придумывать. Перед реализацией механики найти ванильный аналог и сослаться на него.
- Русские игровые термины — только из `DebugLocalization.sqlite`.
- Префикс `REMSELY_`; ключи текста вида `LOC_..._REMSELY_...`.
- Любая правка текста — сразу в оба языка (`en_US` и `ru_RU`).
- После любой правки запускать `python tools/validate.py`.
- Новая картинка арта: `slice_art.py`, `make_art.py`, `make_leader3d.py` (если 3D-лидер включён), `build.py`.
- Ошибки данных ищи в `Database.log` / `Modding.log` (например, `[ColorManager] ERROR`): валидатор ловит не всё.
- 3D: не рисовать в текстурах тени, которые физически отбросит сама модель: от головы и бороды на шею, под челюстью, от век в уголках глаз, от объёмных кантов и т. п. Их даёт освещение и отдельная карта AO (`build_bake.py`). Затенение допустимо только для мелкого рельефа, которого нет в геометрии (например, между волокнами плетёного шнура, если шнур — гладкая трубка). Неверный цвет (например, белая рубашка портрета, спроецированная на горло) перекрашивать в собственный цвет поверхности той же яркости, не темнее. Если что-то выглядит слишком светлым, править геометрию, шероховатость или цвет материала, а не затемнять текстуру.
- 3D: не останавливаться и не отчитываться «готово», пока сам видишь дефекты. После каждой итерации осматривать модель со всех сторон (портретный вид, бока, спина, снизу, крупные планы) против `art/source/alexander_ii_full.png` и присланных примеров; всё, что не так, сразу исправлять в той же работе. Закончить можно только тогда, когда при свежем осмотре не осталось ни одного известного дефекта; список «что ещё не так» в отчёте — признак, что работа не закончена.

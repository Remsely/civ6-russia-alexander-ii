# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Состояние проекта

Репозиторий — мод «Remsely's Alexander II» (альтернативный лидер России для Civilization VI). Реализовано: лидер, способность «Великие реформы», повестка «Освободитель», города и столица, 31 реплика дипломатии, арт (портреты, иконки, фоны). Идут проверка в игре, вычитка текстов, полировка (см. `ROADMAP.md`).

Источники истины:
- `ROADMAP.md` — план по фазам, инструменты, ручные и автоматизируемые шаги (на русском).
- `docs/remselys-alexander-ii.md` — дизайн-документ (механики, повестка, реплики, композиции фонов, чек-лист проверки).
- `docs/art-pipeline.md` — как собирается арт; `docs/terms.md` — русские термины.

Один репозиторий = один мод. Сам мод (то, что уходит в `Mods`) лежит в `mod/` — это проект ModBuddy (решение `RemselysAlexanderII.civ6sln` в корне). Пути файлов мода в документах (`Data/...`, `Text/...`, `.modinfo`) — относительно `mod/`. Мод вынесен из корня, потому что Asset Editor и cooker сканируют всю папку проекта, а в корне лежат `reference/` (junction на игру и SDK) и `.venv`: с ними Asset Editor падает.

## Архитектура мода

Мод лидера — это база данных, тексты и 2D-арт:
- `RemselysAlexanderII.modinfo` (пишется руками) описывает файлы и действия: во FrontEnd `Data/Config.sql` (экран выбора лидера), во InGame `Data/GameDefines.sql` (всё остальное); `Data/Icons.sql` (иконка лидера), `Data/Colors.sql` (цвета), `Text/{en_US,ru_RU}.xml`, `UpdateArt` с `RemselysAlexanderII.dep`.
- `Lua/RemselysAlexanderII_Farms.lua` — смежность ферм (считает соседей, ставит свойства клетки, которые читают XML-модификаторы).
- `art/source/` — исходные картинки; `tools/slice_art.py` режет их в `art/build/` (не в git), `tools/make_art.py` генерирует `Textures/*.dds|.tex`, `XLPs/`, `ArtDefs/`, `.dep`, `Data/Icons.sql`. BLP (`Platforms/{Windows,MacOS}/BLPs/`) собирает `tools/build.py` (cooker SDK); после изменения картинок их нужно пересобрать.
- `tools/validate.py`, `tools/install.py` — проверка и установка. `art/prompts.md` — промпты для нейросетей.
- `reference/` — в `.gitignore`: ванильные файлы игры, образцы модов, копии баз.

Игру из Claude Code запустить нельзя: на этом шаге остановись, напиши, что сделать вручную и какой лог прислать (`Database.log`, `Modding.log`, `Lua.log` из `%LOCALAPPDATA%\Firaxis Games\Sid Meier's Civilization VI\Logs\`).

## Окружение (Windows)

- Python-зависимости в `.venv`: `.venv\Scripts\python.exe -m pip install -r tools\requirements.txt`; запуск — `.venv\Scripts\python.exe tools\validate.py`. `sqlite3` CLI не установлен — для SQLite использовать модуль `sqlite3` из Python. `gh` стоит в `C:\Program Files\GitHub CLI\gh.exe` (вход через `gh auth login`); `git push` по SSH из Claude Code не проходит (нет ключа), после `gh auth login` пушить по HTTPS.
- Игра: `C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization VI`; SDK (ModBuddy, Asset Editor, FireTuner) — рядом, в `... Civilization VI SDK`.
- `reference/` в `.gitignore` и состоит из junction-ссылок на установку игры: `vanilla/{Base,Expansion1,Expansion2}` (данные и тексты), `samples/DLC` (официальные DLC-лидеры как образцы), `samples/SDK-{Examples,Documentation}`. `reference/game-db/` — копии `DebugGameplay.sqlite`, `DebugLocalization.sqlite`, `DebugConfiguration.sqlite` из `%LOCALAPPDATA%\Firaxis Games\Sid Meier's Civilization VI\Cache` (перезаписываются при каждой загрузке набора правил игрой; в них могут быть следы сторонних модов).
- Моды ставятся в `Documents\My Games\Sid Meier's Civilization VI\Mods`.

## Команды

- `.venv\Scripts\python.exe tools\validate.py` — проверка: файлы из `.modinfo`, SQL прогоняется по копиям `DebugGameplay.sqlite` / `DebugConfiguration.sqlite` (ловит несуществующие таблицы и колонки, нарушения внешних ключей), парность `en_US`/`ru_RU`, префикс `REMSELY`, шесть падежей у имён, существование `LOC_`-ссылок; цвета (`UpdateColors`) проверяются по ванильным XML из `reference/vanilla/Base/UI/Colors` (в игре у таблицы `PlayerColors` нет `TextColor`, зато есть `Alt1..3`). Lua не проверяется.
- `.venv\Scripts\python.exe tools\build.py` (`--no-install`) — сборка без ModBuddy: cooker SDK собирает все `mod/XLPs/*.xlp` в `mod/Platforms/{Windows,MacOS}/BLPs` (те же аргументы, что у ModBuddy; результат совпадает байт в байт), затем `install.py`.
- `.venv\Scripts\python.exe tools\install.py` — validate + копирование файлов из `<Files>` в `Documents\My Games\...\Mods\RemselysAlexanderII` (`--remove` удаляет). После установки игру нужно перезапустить.
- `.venv\Scripts\python.exe tools\package.py` — validate + `dist/release/RemselysAlexanderII-v<версия>.zip` (+ `.sha256`) для GitHub Releases; `tools\make_preview.py` — `workshop/preview.png`. Порядок выпуска: `docs/RELEASING.md`, проверка в игре: `docs/TESTING.md`.
- Новый файл мода нужно внести в `<Files>` и в действие `.modinfo` вручную (`.modinfo` пишется руками).
- `.venv\Scripts\python.exe tools\make_modbuddy.py` — генерирует из `.modinfo` проект ModBuddy (`RemselysAlexanderII.civ6sln` в корне, `mod/RemselysAlexanderII.civ6proj` и `.Art.xml`; настройки арта как в первом проекте EmptyMod1, где пеклись BLP). Перезапускать после правки `.modinfo`. Cooker при сборке пишет свой `.dep` из `.Art.xml` (без списков пакетов — в игре пропадают портрет, иконка, фон и 3D-лидер), поэтому проект после сборки копирует поверх наш `mod/RemselysAlexanderII.dep` (цель `RestoreDep`). Сборка в ModBuddy кладёт мод и свежие BLP в `Mods\RemselysAlexanderII` (ту же папку, что `install.py`); BLP оттуда нужно скопировать в `Platforms/` репозитория.
- `.venv\Scripts\python.exe tools\make_leader3d.py` (`--off` — назад к 2D) — подключает 3D-ассет `mod/Assets/AlexanderII.ast`: XLP `Leader_AlexanderII.xlp`, `Leader_BLP_Entry` в `Leaders.artdef`, пакет в `.dep`, файлы в `.modinfo`. Запускать после `make_art.py` (тот перезаписывает artdef и .dep), потом `make_modbuddy.py`. Исходники 3D (FBX, скрипты экспорта) — `art/3d/`.
- `.venv\Scripts\python.exe tools\blend.py audit|render <файл.blend> --scene Human` — проверка 3D-сцены в фоновом Blender 4.5: `audit` — числа по сеткам, весам, материалам и текстурам (ошибки импортёра Firaxis), `render` — кадр с камеры лидера, как на экране дипломатии (`--views full0,full90,head0,...` — ракурсы со всех сторон и общий лист). Прогонять после каждого шага сборки 3D (скилл `civ6-asset-pipeline`). Сама сборка лидера из исходников — `.venv\Scripts\python.exe art\3d\build_all.py`.
- `powershell -STA -ExecutionPolicy Bypass -File tools\fbx_to_fgx.ps1 -Fbx <fbx> -Mode Animation|Geometry|List -Out mod\Animations -Name <имя> [-Node <корень>]` — FBX → `.fgx` (+ `.wig`) FBX-импортёром Asset Editor, но без него (импорт FBX-анимации в самом Asset Editor пишет файл и падает). Asset Editor нужен только чтобы один раз создать `.geo`/`.anm`/`.ast`; дальше обновления — этим скриптом. Сцена лидера (по камере Петра): сантиметры, Z вверх, лидер смотрит на +X, `LeaderCamera` в (320, 0, 137.7) смотрит вдоль своей −Z; читать `.fgx` — `tools\dump_fgx.ps1`. Камера в ассете — ванильная `LEAD_RUSS_Peter_Camera`: наша из FBX даёт чёрный экран. `-Node` у анимации — корневой узел, не имя дубля (иначе в `.fgx` нет дорожек и модель неподвижна).
- Asset Editor падает при старте (`ThemeServiceCommands`, `FormatException`), если в Windows десятичный разделитель — запятая: нужна точка (`intl.cpl` → Дополнительные параметры → Числа). Ещё ему нужна папка `Documents\My Games\Sid Meier's Civilization VI\Logs`.
- Русские термины: `docs/terms.md`. Эталон структуры лидера-мода: `reference/samples/JFD-Russia-Elisabeth` (workshop-мод). Опыт перевода и формат падежей: репозиторий `..\civ6-leaders-mods-ru-localization` (`docs/TRANSLATION_GUIDE.md`).
- Пути в junction `reference/vanilla/Base` идут без `Assets`: `Base/Gameplay/Data`, `Base/Text`, `Base/UI`.
- Данные дополнений и локализации по умолчанию в базах игры соответствуют последнему загруженному набору правил: чтобы в `reference/game-db` были Rise and Fall/Gathering Storm, перед копированием нужно загрузить сохранение с ними. Базы лежат в `%LOCALAPPDATA%\Firaxis Games\Sid Meier's Civilization VI\Cache`.

## Скиллы проекта (`.claude/skills/`)

- `civ6-mod-build` — сборка BLP и мода без ModBuddy (`build.py`), `.dep`/Art.xml, проверка установленного мода.
- `civ6-asset-pipeline` — 3D без Asset Editor: FBX → `.fgx`, `.geo/.anm/.ast`, сцена и камера лидера, падения Asset Editor.
- `local-3d-generation` — Hunyuan3D 2.1 в `C:\AI\HY3D2` (вне репозитория): вход, запуск через WMI по одному seed, превью, проекция референса.

- `civ6-leader-art` — арт и его грабли (BLP, размеры, имена текстур, Portrait/PortraitBackground).
- `civ6-mod-verify` — validate/install, логи игры, что валидатор не ловит.
- `civ6-leader-texts` — полный набор текстов лидера, падежи, цитаты.
- `civ6-leader-data` — SQL/Lua: города, цвета, способность, повестка.
- `civ6-mod-release` — релиз, описание, Workshop.

## Правила

- Названия таблиц, колонок, типов модификаторов, эффектов и требований брать только из `reference/game-db/DebugGameplay.sqlite` или `reference/vanilla/`, не придумывать. Перед реализацией механики найти ванильный аналог и сослаться на него.
- Русские игровые термины — только из `DebugLocalization.sqlite`.
- Префикс `REMSELY_`; ключи текста вида `LOC_..._REMSELY_...`.
- Любая правка текста — сразу в оба языка (`en_US` и `ru_RU`).
- После любой правки запускать `python tools/validate.py`.
- Новая картинка арта: `slice_art.py`, `make_art.py`, `make_leader3d.py` (если 3D-лидер включён), `build.py`.
- Ошибки данных ищи в `Database.log` / `Modding.log` (например, `[ColorManager] ERROR`): валидатор ловит не всё.

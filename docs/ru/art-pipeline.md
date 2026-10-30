# Арт: сборка (2D и 3D)

Английское зеркало: [`../en/art-pipeline.md`](../en/art-pipeline.md). Промпты и сервисы генерации картинок — `art/prompts.md`. Грабли экранов и имена текстур — скилл `civ6-leader-art`; детали 3D-конвейера — скилл `civ6-asset-pipeline`.

## 2D-арт лидера

Исходники: `art/source/alexander_ii_full.png` (в полный рост, прозрачный фон) и `alexander_ii_short.png` (по пояс, прозрачный фон).

1. `tools/slice_art.py` — из исходников в `art/build/`: портрет 827x1024 (из полного роста, кадр до бёдер) и круглые иконки 256/80/64/55/50/48/45/32 (из версии по пояс).
2. `tools/make_art.py` — из `art/build/` в `mod/`:
   - `Textures/*.dds` + `*.tex` (несжатый RGBA, формат как у JFD Elisabeth; у fallback 11 mip-уровней);
   - `XLPs/Icons.xlp` (иконки и портрет), `XLPs/LeaderFallbacks.xlp`;
   - `ArtDefs/{FallbackLeaders,Leaders,UserInterface}.artdef`;
   - `RemselysAlexanderII.dep`;
   - `Data/Icons.sql` (атлас `ICON_ATLAS_REMSELY_ALEXANDER_II`, иконка `ICON_LEADER_REMSELY_ALEXANDER_II`).

Имена: портрет `LEADER_REMSELY_ALEXANDER_II_NEUTRAL`, fallback `FALLBACK_NEUTRAL_REMSELY_ALEXANDER_II`, иконки `RemselysAlexanderII_Icon<размер>`.

`.blp` собирает cooker SDK: `tools/build.py` (то же, что cooking в ModBuddy, без ModBuddy). Без BLP не работают портрет (экран выбора и загрузки) и fallback (дипломатия). Иконки лидера грузятся прямо из `.dds` через `Data/Icons.sql` и работают без BLP. Нужные результаты: `Platforms/{Windows,MacOS}/BLPs/UI/Icons.blp` и `LeaderFallbacks.blp`.

Ориентир по структуре — `reference/samples/JFD-Russia-Elisabeth`.

## 3D-лидер

Фон дипломатии за 3D-моделью — не ассет, а интерфейс (`LeaderScene.lua` кладёт под модель текстуру фона; без неё чёрный экран). Текстура фона идёт через общий 2D-конвейер (`slice_art.py` → `make_art.py`).

Конвейер (все команды — в `CLAUDE.md`, раздел «Команды»):

1. **Сборка модели** — исторический конвейер `art/3d/build_all.py` из исходников-скриптов (не запускать вслепую на принятой модели): поза портрета, ткань, регалии, ордена, кости висящих деталей, веса для движения; итог — `art/3d/alexander_leader.blend`. Правки текстур без пересборки геометрии — отдельные скрипты `build_<regalia|orders|details>.py`, `build_orders.py -- orders`, `uniform_paint.py`, `head_touchup.py` и др. (там же).
2. **Проверка** — `tools/blend.py audit|render|clash|stress` (фоновый Blender 4.5): числа по сеткам и весам, кадры с камеры лидера, проходы объектов друг сквозь друга, стресс-тесты движения. Прогонять после каждого шага.
3. **Экспорт FBX** — `art/3d/export_leader.py -- geometry` и `-- animation` (геометрия в позе покоя, триангулированная, ≤4 костей на вершину, группа треугольников = материал `LEAD_REMSELY_ALEXANDER_II_<часть>`; петля `idle` в 30 к/с).
4. **Сборка ассета** — `art/3d/make_leader_asset.py`: `.fgx` через `tools/fbx_to_fgx.ps1`, `.geo`, `AlexanderII_Idle.anm`, материалы класса `Leader`, текстуры BaseColor/Normal/Metalness/Gloss/AO в `mod/Textures`, `.ast`.
5. **Подключение** — `tools/make_leader3d.py` (XLP, `Leader_BLP_Entry`, пакет в `.dep`, файлы в `.modinfo`; запускать после `make_art.py`, затем `make_modbuddy.py`), затем `tools/build.py` (BLP лидера).

Скрипты создают `.geo`, `.anm` и `.ast` без Asset Editor; `tools/build.py` проверяет палитры костей перед установкой. В ассете используется ванильная камера Петра. Подробности — в [истории импорта](../3d-game-import.md). Не пересобирайте готовую голову вслепую: `build_head.py` неповторяем.

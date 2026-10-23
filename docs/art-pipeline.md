# Арт лидера: сборка

Исходники: `art/source/alexander_ii_full.png` (в полный рост, прозрачный фон) и `alexander_ii_short.png` (по пояс, прозрачный фон).

## Что генерируется скриптами

1. `.venv\Scripts\python.exe tools\slice_art.py` - из исходников в `art/build/`: портрет 827x1024 (из полного роста, кадр до бёдер) и круглые иконки 256/80/64/55/50/48/45/32 (из версии по пояс).
2. `.venv\Scripts\python.exe tools\make_art.py` - из `art/build/` в мод (`mod/`):
   - `Textures/*.dds` + `*.tex` (несжатый RGBA, формат как у JFD Elisabeth; у fallback 11 mip-уровней);
   - `XLPs/Icons.xlp` (иконки и портрет), `XLPs/LeaderFallbacks.xlp`;
   - `ArtDefs/{FallbackLeaders,Leaders,UserInterface}.artdef`;
   - `RemselysAlexanderII.dep`;
   - `Data/Icons.sql` (атлас `ICON_ATLAS_REMSELY_ALEXANDER_II`, иконка `ICON_LEADER_REMSELY_ALEXANDER_II`).

Имена: портрет `LEADER_REMSELY_ALEXANDER_II_NEUTRAL`, fallback `FALLBACK_NEUTRAL_REMSELY_ALEXANDER_II`, иконки `RemselysAlexanderII_Icon<размер>`.

## Что нельзя сгенерировать

`.blp` собирает cooker SDK: `tools/build.py` (то же, что cooking в ModBuddy). Без них не работают портрет (экран выбора лидера и загрузки) и fallback (дипломатия). Иконки лидера грузятся прямо из `.dds` через `Data/Icons.sql` и работают без BLP.

Нужные результаты:
- `Platforms/{Windows,MacOS}/BLPs/UI/Icons.blp` (из `XLPs/Icons.xlp`)
- `Platforms/{Windows,MacOS}/BLPs/LeaderFallbacks.blp` (из `XLPs/LeaderFallbacks.xlp`)

Ориентир по структуре - `reference/samples/JFD-Russia-Elisabeth`.

## Подключение арта (для Александра II уже сделано)

1. `.modinfo`: действия `UpdateArt` (файл `RemselysAlexanderII.dep`) во FrontEnd и InGame; в `<Files>` - `ArtDefs/*`, `.dep`, `XLPs/*`, `Textures/*.tex`, BLP (Windows и MacOS).
2. `Data/Config.sql`: `Players.Portrait` и `PortraitBackground`; `Data/GameDefines.sql`: `LoadingInfo`.
3. `validate.py`, `install.py`, перезапуск игры, проверка: выбор лидера, загрузка, дипломатия.

Размеры кадров, имена текстур и грабли экранов - в скилле `civ6-leader-art`.

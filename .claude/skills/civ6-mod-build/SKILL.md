---
name: civ6-mod-build
description: Сборка мода Civilization VI без ModBuddy - cooker SDK собирает XLP в BLP, установка в Mods, проект ModBuddy из .modinfo, .dep и Art.xml, проверка собранного мода и логов загрузки арта. Обязательно используй, когда нужно собрать или пересобрать мод, BLP, «сбилдить», после правок картинок, XLP, artdef, 3D-лидера, когда пользователь говорит про ModBuddy (build, проект не открывается, после сборки пропали портрет/иконка/фон загрузки) или просит проверить, всё ли на месте в Mods.
---

# Сборка без ModBuddy

Собираю сам, пользователю остаётся только запустить игру.

```
.venv\Scripts\python.exe tools\build.py              # cook + install.py (validate, копирование в Mods)
.venv\Scripts\python.exe tools\build.py --no-install # только cook
```
`build.py` вызывает `...\Civilization VI SDK\AssetModTools\Cooker\Civ6AssetCooker_FinalRelease.exe --mode XLP` для каждого `mod/XLPs/*.xlp` и платформ Windows/MacOS, `--pantry` = `mod/` + пантри SDK Assets по `RequiredGameArtIDs` из `.dep`. Результат в `mod/Platforms/*/BLPs/` совпадает с ModBuddy байт в байт. Потом `install.py` копирует наш `.modinfo` и всё из `<Files>`.

## Что когда запускать
- Правка картинок: `slice_art.py` → `make_art.py` → `make_leader3d.py` (если включён 3D-лидер: `make_art.py` перезаписывает `Leaders.artdef` и `.dep`) → `build.py`.
- Правка `.fgx`/`.ast` 3D-лидера → `build.py` (пакет `leaders/leader_remsely_alexander_ii`).
- Правка `.modinfo` → `make_modbuddy.py` (если пользователь работает в ModBuddy) → `build.py`.
- Новый файл BLP появляется только после cook: `make_leader3d.py` вносит его в `<Files>`, когда он есть на диске.

## Проверка результата (вместо «вроде собралось»)
- Вывод `build.py`: `ok` по каждому XLP; при `FAIL` печатается лог cooker. Предупреждение «99 percent solid color» безвредно.
- В `Mods\RemselysAlexanderII\RemselysAlexanderII.dep` наш id `9c1f5b0e-…` и `PackageDependencies` у `Leader`, `LeaderFallback`, `UITexture`; в `<ArtDefDependencies>` три artdef.
- Есть `Platforms/Windows/BLPs/{UI/Icons,LeaderFallbacks,leaders/leader_remsely_alexander_ii}.blp`.
- После запуска игры: `ArtDef.log` — `Loading Package: C:/.../Mods/RemselysAlexanderII/...blp` для каждого пакета; `Modding.log` — `ModArtLoader - Loading RemselysAlexanderII.dep`. Логи в `%LOCALAPPDATA%\Firaxis Games\Sid Meier's Civilization VI\Logs\` читаю сам.
- Что в игре не проверено — так и говорю.

## ModBuddy (если пользователь всё же собирает в нём)
- Решение `RemselysAlexanderII.civ6sln` в корне, проект `mod/RemselysAlexanderII.civ6proj` — генерирует `tools/make_modbuddy.py` из `.modinfo` (руками не править). Мод в `mod/`, а не в корне: Asset Editor и cooker сканируют всю папку проекта и ломаются о `reference/` (junction на игру и SDK).
- ModBuddy при сборке пишет **свой** `.dep` из `.Art.xml`. Пустые списки пакетов в Art.xml = в игре пропадают портрет, иконка, фон загрузки, а вместо 3D-лидера Клеопатра. Поэтому `make_modbuddy.py` строит Art.xml из нашего `.dep`, а проект после сборки копирует наш `.dep` (цель `RestoreDep`). После смены проекта ModBuddy нужно закрыть и заново открыть решение — иначе он собирает старую версию из памяти.
- Сборка ModBuddy кладёт мод в ту же папку, что `install.py` (`Mods\RemselysAlexanderII`): последняя сборка перезаписывает предыдущую.

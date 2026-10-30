# Выпуск релиза

Английское зеркало: [`../en/RELEASING.md`](../en/RELEASING.md). Проверка перед релизом — [`TESTING.md`](TESTING.md).

Версия релиза (например, `1.0.0-alpha`) лежит в файле `VERSION` и попадает в имя архива и тег. Атрибут `version` в `.modinfo` остаётся целым числом: другого игра не принимает; повышайте его вместе с `VERSION`.

## Перед релизом

1. `.venv\Scripts\python.exe tools\validate.py` — 0 ошибок.
2. `.venv\Scripts\python.exe tools\install.py`, новая партия, проход по [`TESTING.md`](TESTING.md); в логах нет ошибок.
3. Если менялись картинки: `slice_art.py`, `make_art.py`, `make_leader3d.py` (если 3D-лидер включён), пересборка BLP (`tools\build.py`), затем `make_preview.py`.
4. Обновите `VERSION` и `version` в `.modinfo`, допишите `CHANGELOG.md` и `CHANGELOG.ru.md`, закоммитьте.

## GitHub Releases

```powershell
.\.venv\Scripts\python.exe tools\package.py
```

В `dist/release/` появятся `RemselysAlexanderII-v<версия>.zip` (внутри папка `RemselysAlexanderII`, её нужно распаковать в `Mods`) и `.sha256`. Подготовьте единый файл описания релиза: полный английский текст сверху, соответствующий русский текст ниже. Используйте этот файл для релиза; оба файла истории изменений обновляйте отдельно. Затем:

```powershell
git tag v<версия>
git push origin v1.5.0 v<версия>   # ветка релиза + тег
gh release create v<версия> dist/release/* --title "v<версия>" --notes-file <release-notes-file>
```

Репозиторий: `https://github.com/Remsely/civ6-russia-alexander-ii` (старый адрес `civ6-alexander-ii` редиректит). Пуш из Z Code — по HTTPS с gh credential helper.

В архив попадают только файлы из `<Files>` в `.modinfo`: `art/`, `tools/`, `reference/` и документы в него не входят.

## Steam Workshop

Текст страницы лежит в `workshop/description.bbcode`, превью — `workshop/preview.png` (512x512, генерируется `tools/make_preview.py`), настройки — `workshop/workshop.json` (`visibility` 2 = скрытый до проверки). Загрузка через ModBuddy или steamcmd с аккаунта, на котором есть Civilization VI; после первой публикации впишите `PublishFileID` в `workshop.json`. В мод входят BLP для Windows и macOS (`tools\build.py` собирает оба набора); на macOS мод в игре не проверялся.

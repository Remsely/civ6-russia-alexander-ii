[![English](https://img.shields.io/badge/lang-English-blue)](README.md) [![Русский](https://img.shields.io/badge/lang-Русский-red)](README.ru.md)

# Remsely's Russian Empire: Alexander II

Мод для Civilization VI: **Александр II, Император-Освободитель**, как альтернативный лидер России.

![Превью](workshop/preview.png)

## Что в моде

**Способность «Великие реформы»** (с Промышленной эры)
- *Освобождение крестьян:* строители получают +1 заряд, фермы дают +1 пищи за каждые 2 соседние фермы.
- *Земская реформа:* империя получает дополнительный титул губернатора, а города с назначенным губернатором получают +10% к скорости роста.
- *Железнодорожная сеть:* города, соединённые рельсами со столицей, получают +1 производства и +1 золота за каждый соединённый рельсами город другой цивилизации.

**Повестка ИИ «Освободитель».** Ему нравятся цивилизации, давно не объявлявшие войн; не нравятся те, что объявили войну недавно.

**3D-лидер на экране дипломатии** — Александр стоит в собственном зале в позе портрета; в петле idle он смотрит в камеру, дышит, моргает и переступает.

**Остальное:** выверенный список из 45 названий городов во главе с Санкт-Петербургом (Москва, Одесса, Харьков, Севастополь, Владивосток, Ташкент, Баку, Рига…), чёрно-золотые цвета границ, фон экрана загрузки, фон дипломатии, 31 реплика дипломатии и страница в Цивилопедии. Языки: русский и английский.

Требуется Gathering Storm. Платформы: Windows и macOS (BLP собраны для обеих; на macOS мод в игре не проверялся).

## Установка

**Из GitHub Releases:**

1. Скачайте `RemselysAlexanderII-vX.zip` из раздела [Releases](https://github.com/Remsely/civ6-russia-alexander-ii/releases) (рядом лежит `.sha256`).
2. Распакуйте папку `RemselysAlexanderII` в `Документы\My Games\Sid Meier's Civilization VI\Mods\`.
3. В игре: «Дополнительно» → «Моды», включите **Remsely's Russian Empire: Alexander II**. Лидер появится среди лидеров России в новой партии.

Цвета и списки городов записываются в сохранение при создании партии; для проверки их изменений начните новую партию.

## Разработка

Только Windows (SDK Civilization VI). Правила для агентов-разработчиков: [CLAUDE.md](CLAUDE.md) / [AGENTS.md](AGENTS.md).

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r tools\requirements.txt
.\.venv\Scripts\python.exe tools\validate.py       # проверка мода
.\.venv\Scripts\python.exe tools\install.py        # проверка и установка в папку модов игры
.\.venv\Scripts\python.exe tools\build.py          # сборка BLP (cooker SDK, без ModBuddy)
```

Документация:
- [ROADMAP.ru.md](ROADMAP.ru.md) — статус и план;
- [docs/ru/design.md](docs/ru/design.md) — дизайн мода ([English](docs/en/design.md));
- [docs/ru/ideas.md](docs/ru/ideas.md) — банк идей;
- [docs/ru/art-pipeline.md](docs/ru/art-pipeline.md) — как собирается арт;
- [docs/ru/TESTING.md](docs/ru/TESTING.md) — проверка в игре;
- [docs/ru/RELEASING.md](docs/ru/RELEASING.md) — выпуск релиза;
- [docs/ru/terms.md](docs/ru/terms.md) — глоссарий игровых терминов;
- [CHANGELOG.md](CHANGELOG.ru.md) — история версий.

Текущая ветка содержит изменения v1.5.0; опубликованные релизы могут отличаться.

Папка `reference/` (в `.gitignore`) состоит из ссылок на файлы игры и выгрузок баз данных — см. раздел «Окружение» в [CLAUDE.md](CLAUDE.md).

Исходники картинок созданы нейросетями по промптам из [art/prompts.md](art/prompts.md).

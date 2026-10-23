# Claude Code, 3D и лидеры для Civilization VI: инструменты, пределы и пайплайн (октябрь 2026)

Главный вывод: полноценную 3D-сцену лидера уровня Firaxis Claude Code в 2026 году сам не соберёт. Ему не мешает отсутствие MCP: официальный Blender MCP уже есть. Узкие места в другом: лицевая анимация и художественный риггинг пока не автоматизируются, а импорт в Civ VI идёт через устаревшую цепочку CivNexus6 → .fgx → Asset Editor, которую Claude не может «нажать». Поэтому для Dmitry Donskoy и Alexander II я рекомендую два этапа. Сейчас — 2D-лидер с набором «настроенческих» портретов. Механизм FallbackLeaders официально поддерживается игрой, и Claude Code автоматизирует этот этап почти полностью. 3D-сцену стоит делать позже: базовую модель получить через image-to-3D, а риг, лицо и анимацию поручить фрилансеру.

## TL;DR

- **Интеграции:** официальный Blender MCP существует. Его сделал Blender Lab (v1.0.0 вышла 27 апреля 2026, нужен Blender 5.1+).\[1\]\[2\] Anthropic объявила его коннектором Claude 28 апреля 2026, но сам сервер написали разработчики Blender, а не Anthropic.\[3\]\[4\] Самый популярный community-сервер — ahujasid/blender-mcp, в сентябре 2026 переименованный в MCP for Blender. Он умеет вызывать Rodin, Hunyuan3D и Tripo.\[2\] Для Claude Code есть community-скилы (blender-kiln, ra100/blender-skills, using-blender). Официальных скилов от Anthropic для 3D нет.
- **Пределы:** Claude Code хорошо пишет bpy-скрипты, гоняет Blender в headless-режиме, чистит меши, делает экспорт и пакетные операции. Он не способен художественно смоделировать лицо, правильно развесовать сложный риг, поставить лицевую анимацию и lip-sync. Image-to-3D (Meshy, Tripo, Rodin, TRELLIS.2) даёт приемлемую стилизованную «болванку», но не готового лидера. Модер FurionHuang, автор анимированных лидеров, писал на CivFanatics, что оставил своим моделям только idle-анимацию: «each clip took me 2 days and still doesn't look natural».
- **Что делать:** концепт и вариации — Nano Banana Pro / GPT Image через API, либо Scenario с обучением на собственном стиле. Затем 2D-пакет: иконки 256/80/64/55/50/45/32, фон загрузки, портрет выбора и около 22 «настроенческих» портретов дипломатии. Его Claude Code генерирует, ресайзит и прописывает в XML/SQL/artdef. 3D-сцену (CivNexus6 + Blender-скрипты Deliverator) имеет смысл делать вторым этапом и заказывать риг с анимацией у человека.

## Key Findings

### 1. Что официально, а что community

| Компонент | Статус | Кто делает | Что даёт |
|---|---|---|---|
| Blender Lab MCP Server | **Официально (Blender)**, используется в коннекторе Claude | Blender Lab | 26 инструментов (на странице Configure коннектора, по гайду top3d.ai, это 19 инструментов чтения и 7 записи/удаления): выполнение Python, сводки по .blend, скриншоты, поиск по встроенной копии API-справки и мануала, `_for_cli`-варианты для фоновой обработки .blend. 3D-генерации нет. GPL-3.0, Blender 5.1+ |
| Коннектор Blender в Claude | **Официально (Anthropic, анонс 28.04.2026)** | Сервер — Blender, листинг — Anthropic | Анализ и отладка сцен, скрипты для пакетных изменений, новые инструменты в UI Blender\[4\] |
| MCP for Blender (бывш. blender-mcp, ahujasid) | Community, MIT | Siddharth Ahuja | 36 инструментов, интеграции Poly Haven, Sketchfab, Hyper3D Rodin, Hunyuan3D, Tripo. Blender 3.0+. Опциональный safe mode\[2\] |
| StraySpark Blender MCP Server, Blender MCP Pro | Коммерческие, community | StraySpark; Youichi Uda | $79.99 разово / $5 в мес. или $15 разово. Права доступа, проверки экспорта\[2\] |
| Unity MCP (com.unity.ai.assistant) и официальный плагин Unity для Claude Code | **Официально (Unity)** | Unity | Управление редактором Unity 6+\[5\]\[6\] |
| Unreal Engine 5.8 MCP | **Официально (Epic), экспериментальный** | Epic | Управление редактором UE\[6\]\[7\] |
| Godot, Maya, 3ds Max, Houdini, ZBrush MCP | Community (godot-ai, @coding-solo/godot-mcp, экосистема dcc-mcp и др.) | Разные авторы | Разная зрелость, официальных серверов не нашёл\[7\]\[8\]\[9\] |
| Autodesk Fusion, Adobe Creative Cloud | **Официальные коннекторы Claude** (тот же анонс) | Autodesk / Adobe | Fusion — CAD, к персонажам не относится.\[10\]\[11\] Есть ли там Substance, я не подтвердил |
| Mixamo, Cascadeur, AccuRIG, Civ VI SDK | MCP-серверов от вендоров не нашёл | — | Работа только через GUI, файлы или скрипты |

Важный контекст. Официальный сервер Blender подаётся как инструмент для «анализа, отладки и скриптинга», а не для генерации арта.\[2\] После критики сообщества патронаж Anthropic в Blender Development Fund превратили в разовое пожертвование: пост Anthropic обновлён 1 мая 2026.\[2\]\[4\] Документация сервера прямо предупреждает, что он выполняет сгенерированный LLM код «без каких-либо защит», и советует работать в виртуальной машине.\[12\]\[13\] У MCP for Blender в 2026 году было опубликовано 4 CVE. Сравнительную таблицу серверов составила StraySpark, которая продаёт конкурирующий продукт, поэтому её оценки стоит читать с поправкой.\[2\] Факты о версиях и датах там при этом ссылаются на первоисточники.

### 2. Скилы и плагины для Claude Code (все community)

- **blender-kiln (elithril)** — скил и плагин «от брифа или фото до production GLB». Работает с обоими MCP (официальным и mcp-for-blender), включает генерацию через Hunyuan3D, текстурирование, риггинг и batch-режим. Установка: `/plugin marketplace add elithril/blender-kiln`.\[14\]
- **ra100/blender-claude-plugin (blender-skills)** — набор скилов: bpy-скриптинг, композитинг, физика и др. С версии 1.3.0 ориентирован на официальный Blender MCP. Без MCP генерирует готовые к запуску bpy-скрипты и описывает headless-режим.\[1\]
- **using-blender (ellmos-ai)** — маршрутизация между GUI, headless (`blender --background --python script.py`) и MCP, проверка экспорта и повторного импорта.\[15\]
- В реестре skills.sh, по данным агрегатора Skillselion, есть `blender-motion-state-inspection` (диагностика рига и анимации), `blender-web-pipeline` и `cli-anything-blender`.\[16\] Цифры установок взяты у агрегатора, я их не проверял.

**Практический вывод:** причина того, что «Claude Code через MCP не справляется», обычно в двух вещах. Во-первых, модель путает версии bpy API (5.x сильно отличается от 2.8–4.x). Во-вторых, ей нечем проверить результат.\[2\] Лечится это так: (а) официальный сервер или MCP for Blender с поиском по API; (б) скил с методикой и проверками; (в) headless-скрипты, которые возвращают числа (полигоны, кости, веса, ошибки экспорта), а не скриншоты.

### 3. Что Claude Code реально может в Blender

| Задача | Может сам | Комментарий |
|---|---|---|
| bpy-скрипты, пакетные операции, переименование, аудит сцены | Да, хорошо | Сильная сторона |
| Headless-конвейер: импорт GLB → decimate/remesh → триангуляция → UV → bake → экспорт | Да | Лучший сценарий для автоматизации |
| Процедурное моделирование (реквизит, рамки, простые формы) | Частично | Для меча или шапки Мономаха годится как блокинг, но не как финал |
| Вызов image-to-3D через MCP for Blender или API | Да | Результат надо отбирать глазами |
| Rigify или Mixamo-подобный базовый риг по скрипту | Частично | Кости поставит, веса выйдут «автоматические», с артефактами на одежде |
| Привязка к скелету ванильного лидера Civ VI | Скорее нет | Нужно ручное совмещение костей, проверка в Asset Previewer |
| Лицевые блендшейпы или кости, эмоции, lip-sync | Нет (только помогает) | Генераторы ARKit-шейпкеев — полуавтомат, качество зависит от топологии |
| Работа в Civ VI Asset Editor / ModBuddy | Нет (GUI) | Может генерировать XML (.ast/.geo/.artdef), но запуск и «приготовление» делает человек |

## Details

### 4. Image-to-3D, риггинг и анимация: сравнение

**Генерация 3D**

| Сервис | Качество для персонажа | Цена (2026) | Лицензия / Workshop | Автоматизация |
|---|---|---|---|---|
| Meshy (6/7) | Хорошее, PBR, авториг + 600+ пресетов движений | Free 100 кредитов в мес.; Pro $20 в мес. ($240 в год), 1 000 кредитов в мес. и приватная лицензия (страница тарифов meshy.ai) | Free — CC BY 4.0 (с атрибуцией Meshy), платные — полные права | REST API, плагины\[17\]\[18\]\[19\] |
| Tripo (3.1 / P2.0) | Хорошее, авториг, Smart Mesh | Free 200 кредитов в мес. («public and non-commercial»); Pro $19.90 в мес. (около $20 при годовой оплате), 3 000 кредитов; API $1 за 100 кредитов (обзор The Rundown AI, тарифы проверены 29.08.2026) | Free некоммерческий → для Workshop нужен платный план | REST API, интеграция в MCP for Blender\[17\]\[19\]\[20\]\[21\]\[22\] |
| Rodin / Hyper3D Gen-2.5 | Высокая детализация, quad-топология | Creator $30 в мес. ($24 при годовой оплате); API только на Business, $120 в мес. ($96 при годовой) с «Full API access, 4K textures, high poly quads» (The Rundown AI, 3dtoolwiki) | Коммерческая на платных\[23\]\[24\] | API, интеграция в MCP for Blender |
| Hunyuan3D 2.1 (Tencent, open weights) | Хорошее, PBR | Бесплатно; по README Tencent на GitHub нужно 10 ГБ VRAM на форму, 21 ГБ на текстуры и 29 ГБ на полный пайплайн | **Лицензия исключает ЕС, Великобританию и Южную Корею**, включая использование и показ outputs вне «Territory» | Локально, MCP for Blender\[25\]\[26\] |
| TRELLIS.2 (Microsoft) | Хорошее | Бесплатно (self-host) | MIT (у пары зависимостей NVIDIA свои лицензии) | Локально |
| Luma Genie, CSM | Актуальных данных 2026 не нашёл | — | Не проверено | — |

Для мода в Steam Workshop опасен Hunyuan3D. Workshop распространяет файлы по всему миру, включая ЕС, а лицензия запрещает «distribute or display» outputs вне Territory.\[18\]\[27\] Даже если вы сами находитесь вне исключённых стран, я бы не использовал его для публикуемых ассетов. Безопаснее платный Meshy или Tripo, либо TRELLIS.2 (MIT).

**Риггинг, лицо и анимация**

| Инструмент | Что делает | Цена | Лицензия | Применимость к лидеру Civ VI |
|---|---|---|---|---|
| Mixamo | Авториг гуманоида + библиотека движений | Бесплатно (Adobe ID) | Royalty-free для коммерческих проектов, нельзя перепродавать как ассеты | Тело — да, лица нет. Скелет потом переносить на скелет Civ\[28\]\[29\]\[30\] |
| AccuRIG 2.0 (Reallusion) | Авториг тела и пальцев, экспорт FBX/USD | Бесплатно | Бесплатно, ActorCore-движения отдельно | Аналогично Mixamo\[31\]\[32\] |
| Rigify (встроен в Blender) / Auto-Rig Pro (платный) | Полный риг, включая лицевой | Бесплатно / на Superhive (бывший Blender Market) $50 за полную версию (Auto-Rig Pro + Smart + Remap + Fbx Export) или $25 за Lite, 12 месяцев обновлений включены | — | Лучший вариант для ручной доводки, управляется bpy |
| ARKit Blendshape Helper / ShapeKeyGen | Генерация 52 ARKit-шейпкеев из лицевого рига | Бесплатно / платно | Проверять у автора | Для эмоций и lip-sync. Как лицо работает в Civ VI (кости или морфы) — не подтверждено\[33\]\[34\] |
| Cascadeur | Физически корректная ключевая анимация | Free — некоммерч. и только .casc; Indie $8 в мес. (FBX, доход до $100k); Pro $33 | Для мода нужен минимум Indie | Удобен для поз тела\[32\] |
| Move.ai / видео-в-анимацию | Захват движений по видео | Не проверял актуальные цены | — | Можно для жестов тела |

### 5. Концепт-арт: какой это может быть сервис и что выбрать

Сервис, который вы вспоминаете («персонаж со всех сторон, предметы, детали, вариации одежды»), по описанию больше всего похож на **Scenario**. Это игровая платформа с обучением собственных моделей на 5–15 изображениях персонажа или 10–30 изображениях стиля, с API и MCP.\[35\]\[36\]\[37\] Вторым кандидатом остаются **Leonardo** и многочисленные «character sheet generator» поверх Nano Banana / GPT Image. Точно установить конкретный сервис я не могу: это гипотеза.

| Сервис | Консистентность между ракурсами | Обучение на своём стиле | API для Claude Code | Цена | Лицензия |
|---|---|---|---|---|---|
| Scenario | Высокая с кастомной моделью | Да (Pro+), веса не скачиваются | REST API + MCP | Starter $15, Pro $45 (обучение), Max $75 в мес. | Коммерческая на всех платных\[37\]\[38\] |
| Nano Banana Pro (Gemini 3 Pro Image) | Сильная, до 5 персонажей | Нет (только референсы) | Да, официальный | $0.134 за 1K/2K, $0.24 за 4K | По условиям Google API\[23\]\[39\]\[40\] |
| GPT Image 2 / 2.5 (OpenAI) | Сильная, лидер в редактировании | Нет | Да | Токены; около $0.006–0.21 за 1024² | По условиям OpenAI\[41\] |
| FLUX.2 (BFL) + ComfyUI / LoRA | Хорошая, до 10 референсов | Да (LoRA, локально) | API BFL / локально | $0.014–0.07 за изображение; klein 4B — Apache 2.0 | Зависит от варианта модели\[41\]\[42\] |
| Midjourney V8.x (Omni Reference) | Хорошая, но менее надёжная | Частично (style refs) | **Нет официального API** | $10–120 в мес. | Коммерческая на платных |
| Leonardo, Krea, Recraft, Layer.ai, Ideogram, Seedream, Astria | Не проверял детально в этом исследовании | — | — | — | Проверять отдельно |

**Рекомендация:** для автоматизации из Claude Code берите **Nano Banana Pro или GPT Image через API** (одна референс-картинка → turnaround, эмоции, вариации). Если нужен устойчивый «стиль Civ VI», подойдёт Scenario Pro с собственной моделью. Оговорка по стилю: обучение LoRA или кастомной модели на скриншотах ванильных лидеров Firaxis юридически серое (это чужой арт). Безопаснее обучать на собственных концептах «в духе» Civ VI и использовать стиль как описание.

### 6. Пайплайн Civilization VI: что нужно лидеру

**2D-ассеты (подтверждено туториалами сообщества):**
- **Иконка лидера** (круглая): 256, 80, 64, 55, 50, 45, 32 px. Для 256 оставьте около 10 px поля (рисуйте в 235×235 и расширяйте холст).\[43\]\[44\] Записи — в Icons.xml (IconTextureAtlases, IconDefinitions), действие UpdateIcons во FrontEnd и InGame.\[43\]
- **Экран загрузки:** таблица `LoadingInfo` (BackgroundImage, ForegroundImage). Фон можно взять у существующего лидера, например `LEADER_GORGO_BACKGROUND`.\[43\]
- **Экран выбора:** таблица `Players` в Config (Portrait, PortraitBackground, LeaderIcon, LeaderAbilityIcon).\[43\]
- **Портрет лидера:** выравнивание по левому краю, около 40% изображения пустые.\[43\] Высота в практике модеров около 1080 px.\[45\]
- **Статичный портрет дипломатии:** `LeaderFallbacks.artdef` + XLP класса LeaderFallback. **Можно задать разные портреты для около 22 состояний:** DECLARE_WAR_FROM_AI, DECLARE_WAR_FROM_HUMAN, DEFAULT, DEFEAT, ENRAGED, FIRST_MEET, HAPPY, HAPPY_IDLE, HAPPY_NEGATIVE, HAPPY_POSITIVE, KUDOS, NEUTRAL, NEUTRAL_GREETING, NEUTRAL_POSITIVE, NEUTRAL_TO_HAPPY, NEUTRAL_TO_UNHAPPY, UNHAPPY, UNHAPPY_IDLE, UNHAPPY_NEGATIVE, UNHAPPY_POSITIVE, UNHAPPY_TO_NEUTRAL, WARNING.\[43\] Это и есть «статичный портрет с несколькими настроениями», поддерживаемый движком.
- Важно: в той же схеме нужно убрать вставки в DiplomacyInfo, иначе возможны конфликты.\[43\] Также модеры отмечают, что `.dds` вручную сохранять больше не обязательно: Asset Editor импортирует PNG.\[43\]

**3D-сцена лидера (подтверждено частично):**
- Статичный и 3D-лидер описываются в разных artdef: **FallbackLeaders** для 2D и **Leaders** для 3D.\[44\] 3D-лидер — это Asset (.ast) класса «Leader», который ссылается на Geometries, Materials и Animations.\[46\]\[47\]\[48\]
- Формат моделей и анимаций — **.fgx** (Granny, эквивалент .gr2 из Civ V). Скелеты и анимации совместимы с Civ V.\[48\]\[49\] Модели «готовятся» (cook) в .blp при сборке мода.\[48\]\[50\]
- Инструменты: официальные **ModBuddy + Asset Editor + Asset Previewer** (Civ VI SDK и SDK Assets) и community **CivNexus6 + Blender Scripts for Civ V/VI 16.4** (Deliverator; скрипты для Blender 2.8+/3.x обновлены при участии Sukritact).\[48\]\[51\]\[52\] Цепочка: .fgx → .cn6 → Blender → .cn6 → CivNexus6 → .fgx/.geo → .ast в Asset Editor.\[51\]\[53\]\[54\]\[55\]\[56\]
- Требования, известные по форуму: у leader-.geo обязателен **.wig** (волосы и ткань). Обходной путь — скопировать .wig существующего лидера; Deliverator советует делать волосы обычными мешами, как у Zara Yaqob.\[50\] Каждая вершина может иметь веса максимум к **8 костям**.\[57\] В Granny-формате на вершину приходится одна пара UV на слой.\[50\] В материале должны быть все текстуры: AO, Normal, Metalness, Gloss.\[50\]
- Анимации: клипы экспортируются из Blender или Maya в FBX (только кости), импортируются в CivNexus6 или Asset Editor, генерируется .anm и привязывается в `m_animationBindings` .ast.\[48\]\[58\] При экспорте надо отключить simplify, иначе появляется дрожание.\[57\]
- Голос — через **Wwise 2015.1.9** (поле Audio в .ast).\[59\]\[60\] По сообщениям модеров, настройка речи у лидеров нестабильна, музыка лидера «buggy».\[59\]\[61\]
- **Не подтверждено:** точные имена анимационных слотов 3D-лидера, полигональный бюджет, число костей, размеры текстур ванильных лидеров, лицо на костях или на морфах, реализация lip-sync, ссылки на свет и камеру сцены. Единственная точка данных — 2048×2048 текстуры у кастомного лидера одного модера.\[47\]
- **Asset Editor нестабилен.** Он не открывается, если в проекте есть кастомные .ast, поэтому модеры держат две копии ModBuddy. Previewer часто падает.\[48\]\[62\]

**Примеры модов с 3D-лидерами:** Sukritact (Zara Yaqob, Siam, Bayinnaung — ZBrush и Substance Painter),\[47\]\[63\] FurionHuang («Rise and Fall of Usurper»; на CivFanatics он писал: «Now I'm using 3D model with only idle animation… each clip took me 2 days and still doesn't look natural»), CIVITAS (Darius I, Gajah Mada),\[64\] **V Leaders Reborn** (Deliverator и Steffalon): это портирование готовых анимированных и озвученных лидеров Firaxis из Civ V, а не создание с нуля.\[49\]\[65\]\[66\] Коллекции «3D Animated Leaders» в Workshop показывают, что за 9 лет таких лидеров с нуля сделали считанные авторы.\[67\]\[68\]

**Промежуточные варианты вместо полной 3D-сцены:**

| Вариант | Поддержка движком | Трудозатраты | Оценка |
|---|---|---|---|
| Статичный портрет (текущий план) | Да, FallbackLeaders | Низкие | База |
| **Портреты по 22 настроениям** | **Да, штатно** | Средние, автоматизируемы | **Лучшее соотношение** |
| 2.5D / параллакс / «Live2D»-подобный | Нет штатного 2D-аниматора. Возможно как 3D-asset из плоскостей с костями (.fgx) | Высокие, всё равно нужен 3D-пайплайн | Эксперимент, не подтверждён рабочими модами\[69\] |
| Видео-цикл | Не нашёл подтверждений, что дипломатия Civ VI проигрывает видео для лидера | — | Не рекомендую без проверки |
| Полная 3D-сцена | Да | Очень высокие | Отложить |

Идею «2D-анимированных лидеров» на CivFanatics обсуждали ещё до релиза (Sukritact считал её менее трудоёмкой),\[70\] но готового подтверждённого решения я не нашёл.\[70\]

## Recommendations

### 7. Пошаговый пайплайн

| Шаг | Инструменты | Что делает Claude Code | Что вручную / фрилансер | Время / деньги (моя оценка) |
|---|---|---|---|---|
| 0. Подготовка агента | Claude Code + скилы (blender-kiln или ra100/blender-skills), официальный Blender MCP (Blender 5.1+) или MCP for Blender с `BLENDER_MCP_SAFE_MODE=1`; MCP или скрипты для image API | Пишет CLAUDE.md с размерами иконок, именами таблиц и состояний; скрипты валидации | Установка, VM для Blender MCP | 1 день, $0 |
| 1. Концепт | Nano Banana Pro / GPT Image API; опционально Scenario Pro | Генерирует серии по брифу (исторические референсы, Донской — XIV в., Александр II — мундир), turnaround, эмоции, вариации | Отбор, исторический контроль, правки | 2–4 дня; $10–50 |
| 2. 2D-пакет | Image API + Pillow/ImageMagick + ModBuddy | Генерирует около 22 настроенческих портретов из одного утверждённого, режет и масштабирует иконки 7 размеров, пишет Icons.xml, LoadingInfo, Config, artdef/XLP-XML | Сборка и «cook» в Asset Editor, проверка в игре | 3–7 дней; $10–30 |
| 3. (Этап 2) 3D-база | Meshy/Tripo (платно) или TRELLIS.2 → Blender | Вызывает генерацию, headless-чистка, decimate, триангуляция, UV, bake, отчёт по метрикам | Отбор, доводка лица и рук (скульпт) — лучше фрилансер | 1–2 недели; $20–60 сервисы + $300–1500 доводка |
| 4. Риг и привязка к скелету Civ | Rigify / Auto-Rig Pro, CivNexus6 + Blender-скрипты | Скрипты переименования костей, проверки весов (≤8 костей на вершину), экспорт .cn6 | Совмещение со скелетом ванильного лидера, веса одежды — человек | 1–3 недели; $300–1000 фриланс |
| 5. Анимация и лицо | Mixamo/AccuRIG для тела (с ретаргетом), Cascadeur Indie, ARKit-шейпкеи | Ретаргет-скрипты, пакетный экспорт FBX | Idle, приветствие, гнев, поражение, лицевые эмоции — аниматор | 2–6 недель; $500–3000+ |
| 6. Голос и lip-sync | TTS или актёр; Wwise 2015.1.9 | Нарезка реплик, генерация Wwise-проекта по шаблону (частично) | Запись, настройка Wwise | 1–2 недели; $0–500 |
| 7. Интеграция | ModBuddy, Asset Editor, Previewer, FireTuner | Генерирует .ast/.geo/.artdef, проверяет логи (Modding.log, Lua.log) | Работа в GUI Asset Editor, тесты | 1–2 недели |

**Итого:** 2D-вариант с настроениями — примерно 1–2 недели вечерами и до $100. Полный 3D-лидер с несколькими анимациями — 2–4 месяца и, по моей грубой оценке, $1500–5000+ на фриланс. Цифры фриланса — ориентир, рыночные ставки я не проверял.

### 8. Что подключить к Claude Code прямо сейчас

1. Официальный Blender Lab MCP (если Blender 5.1+) в VM или на отдельной учётке. Либо `claude mcp add blender uvx mcp-for-blender` с safe mode для экспериментов с генерацией.\[2\]\[71\]
2. Один скил-«методику» (blender-kiln или ra100/blender-skills) и свой скил «civ6-leader-art» с размерами, именами состояний и шаблонами XML из этого отчёта.
3. Headless-скрипты, которые возвращают JSON-метрики (полигоны, кости, веса на вершину, UV-слои), — чтобы Claude проверял себя числами.
4. API одного генератора изображений (Gemini или OpenAI) для 2D-пакета.

## Caveats

- **Риски и узкие места:** (1) Asset Editor и CivNexus6 — GUI-инструменты Windows с багами; это главный «ручной» этап, Claude его не обойдёт. (2) Схема .ast лидера, слоты анимаций и лицевая система публично не задокументированы; рабочие примеры есть только в чужих модах. (3) Лицевая анимация и lip-sync — самый дорогой и наименее автоматизируемый этап. (4) Лицензии: Hunyuan3D исключает ЕС, Великобританию и Южную Корею; бесплатный Tripo некоммерческий; бесплатный Meshy — CC BY (нужна атрибуция); бесплатный Cascadeur не экспортирует FBX.\[19\]\[25\]\[32\] (5) Безопасность MCP: выполнение произвольного Python; у community-сервера в 2026 году были CVE.\[2\] (6) Стиль Firaxis: обучение на их арте — правовой риск. (7) Голос: TTS с голосом реального человека или актёра требует прав.
- **Источники:** многие сравнения 3D- и image-сервисов написаны вендорами (Meshy, StraySpark, PicoBerry) или SEO-агрегаторами. Цены меняются помесячно, перепроверяйте на страницах тарифов. Сведения о Civ VI в основном из форума CivFanatics 2017–2020 годов (Deliverator, Sukritact, FurionHuang) и гайда Sailor Cat в Steam: они старые, но формат игры с тех пор не менялся.
- **Не подтверждено:** какой именно сервис концептов вы вспоминаете; реальные полигональные и текстурные бюджеты ванильных лидеров; возможность видео или 2D-анимации на экране дипломатии; актуальные данные по Luma Genie, CSM, Move.ai, Leonardo, Krea, Recraft, Layer.ai.

## Источники

1. [GitHub - ra100/blender-claude-plugin: Plugin for blender to be used in coding agents as claude, opencode, kilocode, ... · GitHub](https://github.com/ra100/blender-claude-plugin)
2. [Is There an Official Blender MCP? Blender Lab vs MCP for Blender vs Paid Servers (2026)](https://www.strayspark.studio/blog/official-blender-mcp-server-comparison-2026)
3. [Anthropic releases 9 Claude connectors for creative tools, including Blender and Adobe - 9to5Mac](https://9to5mac.com/2026/04/28/anthropic-releases-9-new-claude-connectors-for-creative-tools-including-blender-and-adobe/)
4. [Claude for Creative Work \\ Anthropic](https://www.anthropic.com/news/claude-for-creative-work)
5. [Unity's Official MCP Server vs Unreal, Godot, and Blender: The 2026 Comparison](https://www.strayspark.studio/blog/unity-mcp-server-vs-unreal-godot-blender-2026)
6. [UE 5.8 AI: Claude, Codex, MCP Editor Guide 2026](https://explainx.ai/blog/unreal-engine-5-8-claude-codex-mcp-ai-integration-2026)
7. [DCC-MCP · GitHub](https://github.com/dcc-mcp)
8. [MCP Server for Game Development: The Complete 2026 Guide](https://www.strayspark.studio/blog/mcp-server-game-development-complete-guide-2026)
9. [Blender vs Unity vs Godot vs Unreal Engine MCP servers for Claude — HeyClaude](https://heyclau.de/compare/game-3d-dev-mcp-servers)
10. [Anthropic releases Claude connectors for creative tools](https://letsdatascience.com/news/anthropic-releases-claude-connectors-for-creative-tools-1fc56d59)
11. [Claude on X: "Claude now connects to the tools creative professionals already use. With the new Blender connector, you can debug a scene, build new tools, or batch-apply changes across every object, directly from Claude." / X](https://x.com/claudeai/status/2049143438281445811)
12. [Official Blender MCP Server](https://mcpservers.org/servers/blender-mcp)
13. [MCP Server — Blender](https://www.blender.org/lab/mcp-server/)
14. [GitHub - elithril/blender-kiln: Blender skill and plugin for Claude Code — 3D asset pipeline from text brief to production GLB: Blender MCP, Hunyuan3D generation, texturing, rigging, batch mode · GitHub](https://github.com/elithril/blender-kiln)
15. [Using Blender (Grade A) - Claude Skill](https://www.skillsdirectory.com/skills/ellmos-ai-using-blender)
16. [What Are the Best Blender Skills for Claude Code? - Skillselion](https://skillselion.com/guides/best-blender-skills-for-claude-code)
17. [Best AI Asset Generators for Games (2026)](https://app.cinevva.com/guides/ai-asset-generators-games)
18. [Meshy vs Hunyuan3D: Best AI 3D Model Generator in 2026](https://www.meshy.ai/compare/meshy-vs-hunyuan3d)
19. [Best AI 3D Model Generators in 2026: Text-to-3D and Image-to-3D Compared](https://app.cinevva.com/guides/ai-3d-model-generators)
20. [Best AI 3D Model Generators in 2026: TRELLIS vs Meshy vs Tripo vs Hitem3D](https://trellis2.app/blog/best-ai-3d-model-generator)
21. [Best AI 3D Model Generator: Tripo vs Meshy vs Rodin (2026) - DEV Community](https://dev.to/trify3dhq/best-ai-3d-model-generator-tripo-vs-meshy-vs-rodin-2026-34cl)
22. [Best 3D Model Generation APIs in 2026 - Complete Comparison](https://www.3daistudio.com/blog/best-3d-model-generation-apis-2026)
23. [Midjourney vs Nano Banana Pro (2026) — Honest Verdict](https://rangy.ai/blog/midjourney-vs-nano-banana-pro/)
24. [Best AI Image Generators in 2026: GPT Image 2, Nano Banana, Midjourney, FLUX](https://www.frankx.ai/blog/best-ai-image-generators-2026)
25. [Hunyuan3D 2.1 vs TRELLIS.2 vs TripoSR (2026): Which Open Image-to-3D Model Wins?](https://triposr.org/blog/hunyuan3d-vs-trellis)
26. [Hunyuan3D licence: restrictions in the EU](https://www.contrast3d.com/blog/hunyuan3d-licencia-union-europea/)
27. [LICENSE · tencent/Hunyuan3D-2 at main](https://huggingface.co/tencent/Hunyuan3D-2/blob/main/LICENSE)
28. [Free Character Animations and Auto-Rigging: Mixamo and Its Alternatives (2026)](https://app.cinevva.com/guides/free-character-animations-rigging)
29. [Mixamo Guide 2026: Free 3D Rigging & Animation Tool](https://www.gojo.blog/mixamo-guide/)
30. [Mixamo License Guide - What You Can & Can't Do](https://www.licenseorg.com/guide/3d-assets/mixamo)
31. [Rig and animate 3D characters for free with AccuRig 2.0](https://www.cgchannel.com/2025/07/rig-and-animate-3d-characters-for-free-with-accurig-2-0/)
32. [Mixamo Retargeting in Blender and When to Skip Mixamo](https://tools.belchamber.us/articles/blender/mixamo-retargeting-and-alternatives)
33. [github.com](https://github.com/elijah-atkins/ARKitBlendshapeHelper)
34. [pymarket.gumroad.com](https://pymarket.gumroad.com/l/yrfsq)
35. [Pricing](https://www.scenario.com/pricing)
36. [Scenario Pricing, Reviews, Alternatives - AI Gaming](https://aitools.fyi/scenario)
37. [Scenario: AI game asset generator](https://www.mrtechking.com/scenario/)
38. [Scenario AI: Pricing, Custom Models & Alternatives](https://www.therundown.ai/tools/scenario)
39. [Best AI Image Generators September 2026: GPT Image 2.5, Nano Banana Pro & MAI-Image](https://www.buildmvpfast.com/articles/best-llms-2026-guide/image-generation-ai)
40. [Nano Banana Pro vs Midjourney: Current Options and 2025 Test Archive](https://spectrumailab.com/blog/nano-banana-pro-vs-midjourney-vs-dalle-3-comparison-2025)
41. [The 7 Best AI Image Generators in 2026, Honestly Compared](https://pixo.video/blog/best-ai-image-generators)
42. [Nano Banana Pro vs Midjourney vs FLUX.2 Compared 2026](https://tech-insider.org/ca/nano-banana-pro-vs-midjourney-vs-flux-2-2026/)
43. [Steam Community :: Guide :: Modding Tutorial: Icons and Leader Images](https://steamcommunity.com/sharedfiles/filedetails/?id=2420858843)
44. [Civ 6 Modding Tools & Basics](https://forums.civfanatics.com/threads/civ-6-modding-tools-basics.634429/)
45. [How to add loading screens, icons & kill Cleopatra in the dip screen & make .blp files.](https://forums.civfanatics.com/threads/how-to-add-loading-screens-icons-kill-cleopatra-in-the-dip-screen-make-blp-files.611608/page-2)
46. [Example mods that only change leader art?](https://forums.civfanatics.com/threads/example-mods-that-only-change-leader-art.682017/)
47. [Art Assets in Civilization 6: A Modding Guide](https://forums.civfanatics.com/threads/art-assets-in-civilization-6-a-modding-guide.612050/page-16)
48. [Art Assets in Civilization 6: A Modding Guide](https://forums.civfanatics.com/threads/art-assets-in-civilization-6-a-modding-guide.612050/)
49. [Import civ 5 leaders and their animations?](https://forums.civfanatics.com/threads/import-civ-5-leaders-and-their-animations.612337/)
50. [Art Assets in Civilization 6: A Modding Guide](https://forums.civfanatics.com/threads/art-assets-in-civilization-6-a-modding-guide.612050/page-6)
51. [Blender Scripts for Civilization V and Civilization VI](https://forums.civfanatics.com/resources/blender-scripts-for-civilization-v-and-civilization-vi.25925/)
52. [Nexus Buddy 2 - Granny Editor for Civ 5](https://forums.civfanatics.com/threads/nexus-buddy-2-granny-editor-for-civ-5.496855/page-28)
53. [Blender Scripts for Civilization V and Civilization VI - Updates](https://forums.civfanatics.com/resources/blender-scripts-for-civilization-v-and-civilization-vi.25925/updates)
54. [Attempting to Mod Leaders with Blender](https://forums.civfanatics.com/threads/attempting-to-mod-leaders-with-blender.653316/)
55. [Extract 3D Models](https://forums.civfanatics.com/threads/extract-3d-models.650835/)
56. [Art Assets in Civilization 6: A Modding Guide](https://forums.civfanatics.com/threads/art-assets-in-civilization-6-a-modding-guide.612050/page-13)
57. [CivNexus6](https://forums.civfanatics.com/threads/civnexus6.611544/page-6)
58. [Are their any custom animated leaders?](https://forums.civfanatics.com/threads/are-their-any-custom-animated-leaders.641612/)
59. [Leader Speech setting in Wwise](https://forums.civfanatics.com/threads/leader-speech-setting-in-wwise.657306/)
60. [Tutorial: Adding Music to Your MOD Civilization](https://forums.civfanatics.com/threads/tutorial-adding-music-to-your-mod-civilization.621830/)
61. [Steam Workshop::V Leaders Reborn - Askiya](https://steamcommunity.com/sharedfiles/filedetails/?id=2111584476)
62. [Tutorial: Using the Asset Previewer](https://forums.civfanatics.com/threads/tutorial-using-the-asset-previewer.616629/)
63. [Leaders - Civilization VI Customization Wiki - Fandom](https://civ6customization-archive.fandom.com/wiki/Leaders)
64. [Steam Workshop::Animated Leaders and Civs For Civilization VI](https://steamcommunity.com/sharedfiles/filedetails/?id=2095375028)
65. [Steam Workshop::V Leaders Reborn](https://steamcommunity.com/workshop/filedetails/?id=2101769654)
66. [V Leaders Reborn - Otto von Bismarck - Skymods](https://catalogue.smods.ru/archives/60442)
67. [Steam Workshop::3D Animated Leaders](https://steamcommunity.com/sharedfiles/filedetails/?id=2121403485)
68. [Animated leaders - Steam Workshop](https://steamcommunity.com/sharedfiles/filedetails/?id=2149791987)
69. [2-D Animated Leaders?](https://forums.civfanatics.com/threads/2-d-animated-leaders.637519/)
70. [Leaderhead creation](https://forums.civfanatics.com/threads/leaderhead-creation.568196/)
71. [GitHub - ahujasid/mcp-for-blender: Community plugin to control Blender 3D with any LLM of your choice. Not affiliated with the official Blender Foundation. · GitHub](https://github.com/ahujasid/mcp-for-blender)

# Промпты для фонов

Общее для всех: без людей (лидера мы вставляем сами), без текста и водяных знаков, живописный стиль Civilization VI (немного утрированные формы, мазки, насыщенный тёплый свет), палитра мода: чёрный, золотой, слоновая кость, зимний голубой. Генерировать в максимальном разрешении, я обрежу под нужный размер. Если нейросеть принимает референс, приложить `art/source/alexander_ii_full.png`, чтобы цвета совпали с мундиром (но просить не рисовать человека).

Общий хвост для каждого промпта (добавлять в конец):
```
No people, no characters, no text, no watermark, no frame. Painterly digital illustration
in the style of Civilization VI loading screens, rich warm lighting, slightly stylized.
```

## 1. Фон карточки на экране выбора лидера (вертикальный, 9:16, лидер встанет поверх нижней части)

Ванильные фоны там: карта мира в цвете империи, спокойная, без ярких деталей в центре. Нужно то же самое в нашей палитре.

**1a. Карта мира (ближе всего к ванили)**
```
Vertical 9:16 background. An antique stylized map of the world in black, gold and ivory tones,
engraved continents and thin gold coastlines, subtle compass rose and faint grid lines,
deep black vignette at the edges, soft golden glow in the upper center, calm empty composition.
```

**1b. Карта Российской империи 1860-х**
```
Vertical 9:16 background. A 19th-century map of the Russian Empire from the Baltic to Alaska,
ivory parchment with gold ink borders and thin black coastlines, imperial double-headed eagle
as a faint watermark, dark vignette, soft light from above, nothing in the center.
```

## 2. Фон экрана загрузки (горизонтальный, ~1920x955)

Реальный макет (по скриншотам из игры): слева узкая полоса (~23% ширины) остаётся видимой, посередине полупрозрачная панель с текстом (23-54%), справа стоит лидер (60-93%). Самое интересное (окно, свечи, стол) держать в левой полосе, а правую часть делать тёмной и спокойной: на ней стоит портрет. Готовая картинка из `cabinet.png` отзеркалена скриптом для этого.

**2a. Кабинет в Зимнем дворце (композиция A)**
```
16:9 wide. Interior of the emperor's study in the Winter Palace, Saint Petersburg, 1861.
A large desk with a sealed manifesto and a quill, bookshelves, a tall window showing a frozen Neva river
and the golden spire of the Peter and Paul Cathedral in cold winter light, warm candle glow inside,
black, gold and ivory colors. Right half of the image calm and dark (a figure will stand there).
```

**2b. Дворцовая площадь зимой (композиция B)**
```
16:9 wide. Palace Square in Saint Petersburg in winter, 1860s. The Alexander Column and the curved
General Staff Building, light snowfall, low golden sun, long soft shadows, cold blue sky,
empty square without people. Right half of the image calm and dark (a figure will stand there).
```

**2c. Русская Америка (композиция C)**
```
16:9 wide. A study table seen from a three-quarter angle with a large 1860s map of Russian America (Alaska)
and a signed treaty with a quill and a wax seal, brass globe, rolled maps, warm lamp light,
a snowy mountain coast visible through a window. Black, gold and ivory colors.
```

## 3. Фон для экрана дипломатии (горизонтальный, 16:9, тёмный)

Лидер стоит по центру на 3/4 ширины экрана, слева лежит белый текст описания, поэтому левая часть должна быть тёмной и спокойной. Скрипт растягивает картинку на всю ширину экрана и дополнительно затемняет левый край.
```
16:9 wide. Dark palace interior, a blurred out-of-focus background: tall windows with winter light,
gold-trimmed columns and heavy curtains, deep black vignette fading to pure black at all edges,
warm golden glow behind the center-right, shallow depth of field, no objects in the foreground.
```

Варианты настроения (при желании, для будущих сцен):
- **Дружелюбный:** `bright clear winter morning, open window, warm light`
- **Злой/война:** `dusk, red and dark blue sky, a map of the Balkans on the desk, cold harsh light`
- **Поражение:** `dark study lit by a few candles, a lone letter on the desk, heavy shadows`

## Журнал результатов

Сюда записывать, какой сервис и промпт дал хороший результат, и имя файла в `art/source/`.

## Материалы 3D-лидера (`art/3d/textures/gen/`)

Сделаны GPT по портрету (картинка-референс прикреплена к каждому промпту), 2026-10-16. Общее правило: плоский ровный свет без теней и бликов, ортогонально — свет даёт игра; полосы и ткани бесшовные. Обрезка и выбор — в истории коммита; используются в `build_uniform.py` (сукно), `build_details.py` (воротник, обшлага, пояс, пряжка), `build_regalia.py` (лента, шнур, поле эполеты).

| Файл | Промпт (суть) | Примечание |
|---|---|---|
| `wool.png` | seamless black-navy wool broadcloth, flat, orthographic | бесшовная; фактура поверх цвета мундира |
| `collar_oak.png` | tileable strip of gold oak-leaf embroidery on red wool (collar) | не бесшовная — кладётся зеркальными повторами |
| `cuff_oak.png` | gold oak-leaf embroidery panel on red wool with a gold border (cuffs) | зеркальные повторы |
| `belt_galloon.png` | tileable gold galloon belt with red edges | из двух вариантов выбран более богатый |
| `buckle.png` | front view of a gold buckle plate with a double-headed eagle | серый фон в срезанных углах заменяется золотом |
| `sash_damask.png` | tileable light-blue watered silk moire with faint damask | узор усилен в скрипте (`SASH_CONTRAST`) |
| `epaulette_field.png` | top view of a round gold epaulette field with an emblem | |
| `gold_cord.png` | tileable twisted gold 3-ply cord | обрезана по 8 виткам, стык сведён — бесшовная по длине |
| `boot_leather.png` | seamless polished black boot leather | пока не используется: у сапог нет развёртки, в кадр игры не попадают |

Не пригодились: второй вариант пояса (беднее), два бледных варианта ленты, уменьшенная копия шнура.

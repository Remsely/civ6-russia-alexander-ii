"""Режет исходные картинки Александра II на нужные игре размеры.

Вход:  art/source/alexander_ii_full.png  (в полный рост, прозрачный фон) -> портрет
       art/source/alexander_ii_short.png (по пояс, прозрачный фон)       -> иконка
       art/source/cabinet.png (кабинет, 16:9)                            -> фон экрана загрузки
       art/source/diplomacy.png (тёмный зал, 16:9)                       -> фон fallback-картинки и задний план 3D-лидера в дипломатии
Выход: art/build/portrait_827x1024.png, fallback_827x1024.png, background_loading_1920x955.png, scene_1920x1010.png,
       art/build/icon_<размер>.png (круглая иконка лидера, 8 размеров)

Запуск: .venv\\Scripts\\python.exe tools\\slice_art.py
"""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
SOURCE_FULL = ROOT / "art" / "source" / "alexander_ii_full.png"
SOURCE_SHORT = ROOT / "art" / "source" / "alexander_ii_short.png"
SOURCE_CABINET = ROOT / "art" / "source" / "cabinet.png"
SOURCE_DIPLOMACY = ROOT / "art" / "source" / "diplomacy.png"
BUILD = ROOT / "art" / "build"

PORTRAIT_SIZE = (827, 1024)
# Вырезка из исходника в полный рост (px, верх выходит за край - там прозрачность). Подобрана по портрету Елизаветы JFD:
# сверху ~100 px пустого места, голова примерно того же размера. Голова на x~375 (как у Елизаветы): карточка на экране
# выбора лидера показывает окно ~501 px по центру с поправкой 30 px, поэтому "по центру" фигура выглядит смещённой вправо.
PORTRAIT_CROP = (206, -73, 901, 787)
# Карточка на экране выбора лидера показывает окно ~517 px текстуры от левого края (по скриншоту), поэтому её портрет
# сдвинут так, чтобы голова стояла на x~290 (у основного на x~385; по скриншоту 258 было чуть левее центра).
SELECT_CROP = (289, -73, 984, 787)  # left, top, right, bottom; пропорции 695x860 = 827x1024
LOADING_SIZE = (1920, 955)  # LoadScreen: StretchMode="Auto" - родной размер по центру; рамка экрана ~1920x955 (по скриншоту)
LOADING_CROP_TOP = 60  # из кабинета 1672x941 берётся полоса 1672x832 (пропорции 1920x955), отзеркаленная: свет и свечи слева, тёмная часть под портретом
FALLBACK_SIZE = (2731, 1024)
# Задний план 3D-лидера (LeaderScene.lua: слои <лидер без LEADER_>_1..SceneLayers, растянуты на весь экран, StretchMode="Fill").
# Размер ванильного последнего слоя (CLEOPATRA_4: 1920x1010); зал 16:9 сжат в него целиком, на экране 16:9 пропорции свои.
SCENE_SIZE = (1920, 1010)
FALLBACK_SHADE_WIDTH = 700  # px слева, где фон затемнён под текст
FALLBACK_SHADE_MAX = 0.6  # затемнение у самого левого края
ICON_SIZES = (256, 80, 64, 55, 50, 48, 45, 32)
ICON_BOX = (385, 0, 905, 520)  # квадрат вокруг головы и плеч в версии по пояс


def portrait(src: Image.Image) -> Image.Image:
    return src.crop(PORTRAIT_CROP).resize(PORTRAIT_SIZE, Image.LANCZOS)


def fallback(portrait_image: Image.Image, background: Image.Image) -> Image.Image:
    """Широкая текстура: тёмный зал на весь экран, лидер по центру. Экран дипломатии масштабирует картинку по высоте и ставит её
    центром на 3/4 ширины экрана, поэтому для 16:9 нужна ширина ~2731 px (3 * 1024 * 16/9 / 2), чтобы левый край дошёл до края экрана.
    Левая часть затемнена: там белый текст описания."""
    width, height = FALLBACK_SIZE
    scale = width / background.width
    scaled = background.convert("RGBA").resize((width, round(background.height * scale)), Image.LANCZOS)
    top = (scaled.height - height) // 2
    canvas = scaled.crop((0, top, width, top + height))
    shade = Image.new("L", canvas.size, 0)
    pixels = shade.load()
    for x in range(min(FALLBACK_SHADE_WIDTH, width)):
        value = round(255 * FALLBACK_SHADE_MAX * (1 - x / FALLBACK_SHADE_WIDTH))
        for y in range(height):
            pixels[x, y] = value
    canvas.alpha_composite(Image.merge("RGBA", (Image.new("L", canvas.size, 0),) * 3 + (shade,)))
    canvas.alpha_composite(portrait_image, ((width - portrait_image.width) // 2, 0))
    return canvas


def icon(src: Image.Image, size: int) -> Image.Image:
    """Квадрат вокруг головы, круглая маска (с тёмным фоном под прозрачностью)."""
    big = size * 4
    square = Image.new("RGBA", (ICON_BOX[2] - ICON_BOX[0], ICON_BOX[3] - ICON_BOX[1]), (28, 28, 28, 255))
    square.alpha_composite(src.crop(ICON_BOX))
    square = square.resize((big, big), Image.LANCZOS)
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, big - 1, big - 1), fill=255)
    square.putalpha(mask)
    return square.resize((size, size), Image.LANCZOS)


def main() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    leader = portrait(Image.open(SOURCE_FULL).convert("RGBA"))
    leader.save(BUILD / "portrait_827x1024.png")
    Image.open(SOURCE_FULL).convert("RGBA").crop(SELECT_CROP).resize(PORTRAIT_SIZE, Image.LANCZOS).save(BUILD / "portrait_select_827x1024.png")
    fallback(leader, Image.open(SOURCE_DIPLOMACY)).save(BUILD / "fallback_827x1024.png")
    Image.open(SOURCE_DIPLOMACY).convert("RGBA").resize(SCENE_SIZE, Image.LANCZOS).save(BUILD / "scene_1920x1010.png")
    cabinet = Image.open(SOURCE_CABINET).convert("RGBA")
    strip = cabinet.crop((0, LOADING_CROP_TOP, cabinet.width, LOADING_CROP_TOP + round(cabinet.width * LOADING_SIZE[1] / LOADING_SIZE[0])))
    strip.transpose(Image.FLIP_LEFT_RIGHT).resize(LOADING_SIZE, Image.LANCZOS).save(BUILD / "background_loading_1920x955.png")
    short = Image.open(SOURCE_SHORT).convert("RGBA")
    for size in ICON_SIZES:
        icon(short, size).save(BUILD / f"icon_{size}.png")
    print(f"Готово: {BUILD}")


if __name__ == "__main__":
    main()

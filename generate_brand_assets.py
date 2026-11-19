"""Generate branded icons and high-resolution theme backgrounds for YVZTools."""
from pathlib import Path
from io import BytesIO
import time
import urllib.request
from PIL import Image, ImageOps, ImageEnhance, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parent
ASSET_DIR = ROOT / "assets"
LOGO_URL = "https://i.ibb.co/KcmZG1kW/36c0cea0-e0b8-4605-958a-fd248ac0f727.webp"
ASTROWORLD_URLS = [
    "https://i.ibb.co/vrsT7Qg/travis-scott-astroworld-cover-art-full.webp",
    "https://upload.wikimedia.org/wikipedia/commons/7/73/Astroworldcover.jpg",
]
SIZE = 1024


def download_image(url, label, attempts=3):
    last_error = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "YVZTools-Brand-Assets/7.5",
                         "Accept": "image/avif,image/webp,image/*,*/*;q=0.8"},
            )
            with urllib.request.urlopen(request, timeout=35) as response:
                payload = response.read()
            if not payload:
                raise RuntimeError("empty response")
            return Image.open(BytesIO(payload)).convert("RGBA")
        except Exception as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Could not download {label}: {last_error}")


def make_fallback_astroworld():
    """A polished gold-on-black fallback so a temporary CDN outage never breaks CI."""
    image = Image.new("RGB", (1600, 1600), "#090704")
    draw = ImageDraw.Draw(image)
    for y in range(1600):
        blend = y / 1599
        color = (int(10 + 25 * blend), int(7 + 17 * blend), int(3 + 5 * blend))
        draw.line((0, y, 1600, y), fill=color)
    for radius, color, width in [(590, "#6D4B13", 12), (520, "#B88B32", 5), (440, "#4B3511", 3)]:
        draw.ellipse((800-radius, 650-radius, 800+radius, 650+radius), outline=color, width=width)
    try:
        font = ImageFont.truetype("arialbd.ttf", 132)
    except OSError:
        font = ImageFont.load_default()
    title = "ASTROWORLD"
    box = draw.textbbox((0, 0), title, font=font)
    draw.text(((1600-(box[2]-box[0]))/2, 1190), title, fill="#E8C66A", font=font)
    return image.convert("RGBA")


def make_ken_carson_background():
    """Upscale the supplied theme GIF once using high-quality resampling."""
    source_path = ASSET_DIR / "yvl_theme_art.gif"
    with Image.open(source_path) as original:
        original.seek(0)
        source = original.convert("RGB")
    # Fill a 16:9 desktop canvas without stretching the source artwork.
    background = ImageOps.fit(source, (2560, 1440), method=Image.Resampling.LANCZOS,
                              centering=(0.5, 0.5))
    background = background.filter(ImageFilter.UnsharpMask(radius=1.5, percent=120, threshold=3))
    background = ImageEnhance.Contrast(background).enhance(1.06)
    background.save(ASSET_DIR / "ken_carson_background.png", optimize=True)


def main():
    ASSET_DIR.mkdir(parents=True, exist_ok=True)

    # Keep the Eve/YVZTools image as the Windows executable and taskbar icon.
    try:
        logo_source = download_image(LOGO_URL, "Eve/YVZTools logo")
    except RuntimeError:
        # The app still gets a deterministic brand mark if the image host is offline.
        logo_source = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
        draw = ImageDraw.Draw(logo_source)
        try:
            font = ImageFont.truetype("arialbd.ttf", 220)
        except OSError:
            font = ImageFont.load_default()
        draw.text((75, 110), "YVZ", fill="#FFFFFF", font=font)
    logo_source.thumbnail((SIZE - 80, SIZE - 80), Image.Resampling.LANCZOS)
    logo_canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    logo_canvas.alpha_composite(
        logo_source, ((SIZE - logo_source.width) // 2, (SIZE - logo_source.height) // 2)
    )
    logo = logo_canvas.resize((512, 512), Image.Resampling.LANCZOS)
    logo.save(ROOT / "yvztools_logo.png", optimize=True)
    logo.save(ROOT / "yvztools.ico", format="ICO",
              sizes=[(16, 16), (20, 20), (24, 24), (32, 32), (40, 40),
                     (48, 48), (64, 64), (128, 128), (256, 256)])

    # Use the supplied cover first, then a stable Wikimedia-hosted original.
    astro_source = None
    for url in ASTROWORLD_URLS:
        try:
            astro_source = download_image(url, "ASTROWORLD cover")
            break
        except RuntimeError as exc:
            print(f"ASTROWORLD source unavailable ({url}): {exc}")
    if astro_source is None:
        print("Using generated ASTROWORLD fallback artwork; continuing build.")
        astro_source = make_fallback_astroworld()

    cover = ImageOps.fit(astro_source, (512, 512), method=Image.Resampling.LANCZOS)
    cover.save(ASSET_DIR / "astroworld_cover.png", optimize=True)
    background = ImageOps.fit(astro_source, (1600, 1000), method=Image.Resampling.LANCZOS)
    background = ImageEnhance.Brightness(background).enhance(0.43)
    background.save(ASSET_DIR / "astroworld_background.png", optimize=True)

    make_ken_carson_background()
    print("Generated Eve/YVZTools icon, ASTROWORLD theme art and smooth Ken Carson wallpaper.")


if __name__ == "__main__":
    main()

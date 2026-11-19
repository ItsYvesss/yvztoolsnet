"""Generate the permanent Eve/YVZTools Windows icon and ASTROWORLD-only theme art."""
from pathlib import Path
from io import BytesIO
import urllib.request
from PIL import Image, ImageOps, ImageEnhance

ROOT = Path(__file__).resolve().parent
ASSET_DIR = ROOT / "assets"
LOGO_URL = "https://i.ibb.co/KcmZG1kW/36c0cea0-e0b8-4605-958a-fd248ac0f727.webp"
ASTROWORLD_URL = "https://i.ibb.co/vrsT7Qg/travis-scott-astroworld-cover-art-full.webp"
SIZE = 1024


def download_image(url, label):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "YVZTools-Brand-Assets/7.5",
                 "Accept": "image/avif,image/webp,image/*,*/*;q=0.8"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = response.read()
    if not payload:
        raise RuntimeError(f"The supplied {label} URL returned an empty file.")
    return Image.open(BytesIO(payload)).convert("RGBA")


def main():
    ASSET_DIR.mkdir(parents=True, exist_ok=True)

    # Always use the Eve/YVZTools logo for the Windows executable and taskbar.
    logo_source = download_image(LOGO_URL, "Eve/YVZTools logo")
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

    # ASTROWORLD art is a separate theme asset, never the Windows app icon.
    astro_source = download_image(ASTROWORLD_URL, "ASTROWORLD cover")
    cover = ImageOps.fit(astro_source, (512, 512), method=Image.Resampling.LANCZOS)
    cover.save(ASSET_DIR / "astroworld_cover.png", optimize=True)
    background = ImageOps.fit(astro_source, (1600, 1000), method=Image.Resampling.LANCZOS)
    background = ImageEnhance.Brightness(background).enhance(0.43)
    background.save(ASSET_DIR / "astroworld_background.png", optimize=True)
    print("Generated Eve/YVZTools Windows icon plus ASTROWORLD-only header and background art.")


if __name__ == "__main__":
    main()

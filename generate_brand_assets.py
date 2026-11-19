"""Generate the ASTROWORLD app icon and darkened background from the supplied cover art."""
from pathlib import Path
from io import BytesIO
import urllib.request
from PIL import Image, ImageOps, ImageEnhance

ROOT = Path(__file__).resolve().parent
ASSET_DIR = ROOT / "assets"
ASTROWORLD_URL = "https://i.ibb.co/vrsT7Qg/travis-scott-astroworld-cover-art-full.webp"


def download_cover():
    request = urllib.request.Request(
        ASTROWORLD_URL,
        headers={"User-Agent": "YVZTools-Brand-Assets/7.4", "Accept": "image/webp,image/*,*/*;q=0.8"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = response.read()
    if not payload:
        raise RuntimeError("The ASTROWORLD cover URL returned an empty file.")
    return Image.open(BytesIO(payload)).convert("RGB")


def main():
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    source = download_cover()
    icon_image = ImageOps.fit(source, (1024, 1024), method=Image.Resampling.LANCZOS).convert("RGBA")
    logo = icon_image.resize((512, 512), Image.Resampling.LANCZOS)
    logo.save(ROOT / "yvztools_logo.png", optimize=True)
    logo.save(ROOT / "yvztools.ico", format="ICO",
              sizes=[(16, 16), (20, 20), (24, 24), (32, 32), (40, 40),
                     (48, 48), (64, 64), (128, 128), (256, 256)])

    background = ImageOps.fit(source, (1600, 1000), method=Image.Resampling.LANCZOS)
    background = ImageEnhance.Brightness(background).enhance(0.52)
    background.save(ASSET_DIR / "astroworld_background.png", optimize=True)
    print("Generated ASTROWORLD app icon, header logo, and theme background.")


if __name__ == "__main__":
    main()

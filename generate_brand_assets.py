"""Build YVZTools PNG and multi-resolution Windows icon from the supplied logo."""
from pathlib import Path
from io import BytesIO
import urllib.request
from PIL import Image

ROOT = Path(__file__).resolve().parent
LOGO_URL = "https://i.ibb.co/KcmZG1kW/36c0cea0-e0b8-4605-958a-fd248ac0f727.webp"
SIZE = 1024


def download_logo():
    request = urllib.request.Request(
        LOGO_URL,
        headers={"User-Agent": "YVZTools-Brand-Assets/6.8", "Accept": "image/avif,image/webp,image/*,*/*;q=0.8"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = response.read()
    if not payload:
        raise RuntimeError("The supplied YVZTools logo URL returned an empty file.")
    return Image.open(BytesIO(payload)).convert("RGBA")


def main():
    source = download_logo()
    # Keep the full logo intact, fitting it inside a transparent square without stretching.
    source.thumbnail((SIZE - 80, SIZE - 80), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    x = (SIZE - source.width) // 2
    y = (SIZE - source.height) // 2
    canvas.alpha_composite(source, (x, y))

    logo = canvas.resize((512, 512), Image.Resampling.LANCZOS)
    logo.save(ROOT / "yvztools_logo.png", optimize=True)
    logo.save(
        ROOT / "yvztools.ico",
        format="ICO",
        sizes=[(16, 16), (20, 20), (24, 24), (32, 32), (40, 40),
               (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print("Generated YVZTools logo PNG and multi-resolution Windows icon from the supplied logo.")


if __name__ == "__main__":
    main()

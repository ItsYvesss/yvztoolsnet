"""Generate the official YVZTools logo and multi-resolution Windows icon."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent
SIZE = 1024
image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
pad, radius = 38, 210

for y in range(pad, SIZE - pad):
    for x in range(pad, SIZE - pad):
        cx = pad + radius if x < pad + radius else (SIZE - pad - radius if x >= SIZE - pad - radius else x)
        cy = pad + radius if y < pad + radius else (SIZE - pad - radius if y >= SIZE - pad - radius else y)
        if (x - cx) ** 2 + (y - cy) ** 2 > radius ** 2:
            continue
        t = max(0.0, min(1.0, (x + y * 0.42) / (SIZE * 1.42)))
        start, end = (8, 20, 54), (29, 111, 235)
        image.putpixel((x, y), tuple(round(start[i] * (1 - t) + end[i] * t) for i in range(3)) + (255,))

mask = image.getchannel("A")
glow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
ImageDraw.Draw(glow).ellipse((205, 185, 820, 800), fill=(66, 191, 255, 70))
image = Image.alpha_composite(image, glow.filter(ImageFilter.GaussianBlur(72)))
image.putalpha(mask)

mark = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(mark)
draw.line([(300, 285), (512, 500), (724, 285)], fill=(250, 253, 255, 255), width=104, joint="curve")
draw.line([(512, 500), (512, 748)], fill=(130, 224, 255, 255), width=104)
draw.line([(333, 310), (512, 492)], fill=(255, 255, 255, 110), width=13)
image = Image.alpha_composite(image, mark)
ImageDraw.Draw(image).rounded_rectangle((pad, pad, SIZE - pad, SIZE - pad), radius=radius,
                                         outline=(142, 220, 255, 235), width=12)

logo = image.resize((512, 512), Image.Resampling.LANCZOS)
logo.save(ROOT / "yvztools_logo.png", optimize=True)
logo.save(ROOT / "yvztools.ico", format="ICO",
          sizes=[(16, 16), (20, 20), (24, 24), (32, 32), (40, 40),
                 (48, 48), (64, 64), (128, 128), (256, 256)])
print("Generated YVZTools logo PNG and multi-resolution Windows icon.")

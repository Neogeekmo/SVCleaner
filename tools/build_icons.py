"""Original, font-independent WoW UI glyphs in one power-of-two RGBA atlas."""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
image = Image.new("RGBA", (256, 32))
d = ImageDraw.Draw(image)
for i in range(8):
    x = i * 32
    def line(points):
        d.line([(x + a, b) for a, b in points], fill="white", width=3)
    if i == 0: line([(12, 8), (20, 16), (12, 24)])
    elif i == 1: line([(8, 12), (16, 20), (24, 12)])
    elif i == 2: line([(8, 20), (16, 12), (24, 20)])
    elif i == 3:
        line([(9, 9), (23, 23)]); line([(23, 9), (9, 23)])
    elif i == 4:
        for k in (0, 7, 14): line([(29-k, 12), (12, 29-k)])
    elif i == 5: d.rectangle((x+7, 7, x+25, 25), outline="white", width=2)
    elif i == 6:
        d.rectangle((x+7, 7, x+25, 25), outline="white", width=2); line([(10, 16), (14, 21), (23, 11)])
    elif i == 7:
        line([(7, 10), (25, 10)]); line([(20, 5), (25, 10), (20, 15)])
        line([(25, 22), (7, 22)]); line([(12, 17), (7, 22), (12, 27)])
image.save(ROOT / "Assets" / "icons.tga")

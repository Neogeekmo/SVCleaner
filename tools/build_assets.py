"""Export the supplied logo for the browser and WoW without redrawing it."""
import base64
from pathlib import Path

from PIL import Image, ImageOps


root = Path(__file__).resolve().parent.parent
source = root / "Assets" / "logo.png"
with Image.open(source) as original:
    width, height = original.size
    scaled = ImageOps.contain(original.convert("RGBA"), (512, 512), Image.Resampling.LANCZOS)
    texture = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    texture.paste(scaled, ((512 - scaled.width) // 2, (512 - scaled.height) // 2))
    texture.save(root / "Assets" / "logo.tga")

# Keep the existing browser asset URL so running companions need no restart.
# Preserve the edited PNG's transparency in the browser export.
encoded = base64.b64encode(source.read_bytes()).decode("ascii")
svg = (
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">\n'
    ' <title>Logo SV Cleaner</title>\n'
    f' <image width="{width}" height="{height}" href="data:image/png;base64,{encoded}"/>\n'
    '</svg>\n'
)
(root / "companion" / "web" / "logo.svg").write_text(svg, encoding="utf-8")
print("Transparent browser logo and 512x512 RGBA WoW TGA exported.")

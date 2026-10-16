"""Original SVG README artwork, using the existing transparent SV logo."""
import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "assets"


def svg(name, width, height, title, content):
    (OUT / name).write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title">\n'
        f'<title id="title">{title}</title>\n{content}\n</svg>\n', encoding="utf-8")


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    logo = base64.b64encode((ROOT / "artwork" / "logo.png").read_bytes()).decode()
    svg("banner.svg", 1000, 280, "SV Cleaner — SavedVariables and WoW maintenance", f'''
<defs>
  <linearGradient id="bg" x2="1" y2="1"><stop stop-color="#171c29"/><stop offset="1" stop-color="#0c1019"/></linearGradient>
  <radialGradient id="glow"><stop stop-color="#eb3934" stop-opacity=".23"/><stop offset="1" stop-color="#eb3934" stop-opacity="0"/></radialGradient>
</defs>
<rect x="1" y="1" width="998" height="278" rx="24" fill="url(#bg)" stroke="#303748"/>
<circle cx="825" cy="110" r="230" fill="url(#glow)"/>
<g fill="none" stroke="#455069" stroke-opacity=".25"><path d="M742 62h180M742 100h180M742 138h180M742 176h180M742 214h180"/><path d="M742 62v152M822 62v152M922 62v152"/></g>
<image x="28" y="25" width="230" height="230" href="data:image/png;base64,{logo}"/>
<g font-family="Segoe UI,Arial,sans-serif">
  <text x="287" y="75" fill="#ed7771" font-size="13" font-weight="600" letter-spacing="2">SAVEDVARIABLES · WORLD OF WARCRAFT</text>
  <text x="282" y="143" fill="#f4f5fa" font-size="58" font-weight="700">SV Cleaner</text>
  <text x="287" y="185" fill="#b9c1d3" font-size="20">Explore. Compare. Clean.</text>
  <rect x="286" y="211" width="108" height="30" rx="15" fill="#272e40"/>
  <rect x="404" y="211" width="177" height="30" rx="15" fill="#272e40"/>
  <text x="340" y="231" fill="#d7dceb" font-size="12" text-anchor="middle">In-game addon</text>
  <text x="492" y="231" fill="#d7dceb" font-size="12" text-anchor="middle">Local companion</text>
</g>''')
    for filename, title, subtitle, icon in (
        ("install-button.svg", "Install the addon", "OPEN IN WOW", '<path d="M28 21v18m-7-7 7 7 7-7M17 42h22"/>'),
        ("companion-button.svg", "Local companion", "MANAGE YOUR FILES", '<rect x="17" y="20" width="25" height="19" rx="3"/><path d="M29 39v6m-7 0h14"/>'),
    ):
        svg(filename, 260, 64, title, f'''<rect x="1" y="1" width="258" height="62" rx="12" fill="#171c29" stroke="#3b455b"/>
<g fill="none" stroke="#ed7771" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{icon}</g>
<g font-family="Segoe UI,Arial,sans-serif"><text x="58" y="28" fill="#f4f5fa" font-size="15" font-weight="600">{title}</text><text x="58" y="45" fill="#aab5cb" font-size="9" letter-spacing=".8">{subtitle}</text></g>''')
    for filename, title, subtitle in (
        ("features.svg", "Your data, under control", "Inventory · editing · comparison · cleanup"),
        ("workflow.svg", "Prepare in game. Apply on disk.", "Review your changes, then back up your files."),
        ("commands.svg", "A simple starting point", "/svc in WoW · SVCleaner.exe on your PC"),
    ):
        svg(filename, 1000, 100, title, f'''<rect x="1" y="1" width="998" height="98" rx="16" fill="#171c29" stroke="#303748"/>
<rect x="28" y="26" width="4" height="48" rx="2" fill="#ed7771"/>
<g font-family="Segoe UI,Arial,sans-serif"><text x="52" y="45" fill="#f4f5fa" font-size="23" font-weight="600">{title}</text><text x="52" y="72" fill="#b9c1d3" font-size="14">{subtitle}</text></g>''')
    print(f"README assets generated in {OUT}")


if __name__ == "__main__":
    build()

"""Build a minimal multi-client WoW archive with license notices."""
import re
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parent.parent
FLAVORS = {"Retail": "Mainline", "Classic": "Vanilla", "BCC": "TBC", "Wrath": "Wrath", "Cata": "Cata", "Mists": "Mists", "Camelot": "Camelot"}


def runtime_files():
    toc = ROOT / "SVCleaner.toc"
    modules = [line.strip() for line in toc.read_text(encoding="utf-8").splitlines() if line.strip() and not line.lstrip().startswith("#")]
    paths = [toc] + [ROOT / module for module in modules] + [ROOT / "Assets" / "logo.tga", ROOT / "Assets" / "icons.tga", ROOT / "LICENSE", ROOT / "NOTICE"]
    for path in paths:
        if not path.is_file() or not path.resolve().is_relative_to(ROOT):
            raise ValueError("Invalid runtime file: " + str(path))
    return paths


def flavor_tocs():
    source = (ROOT / "SVCleaner.toc").read_text(encoding="utf-8")
    result = {}
    for field, suffix in FLAVORS.items():
        match = re.search(r"^## Interface-" + field + r":\s*(.+)$", source, re.MULTILINE)
        if not match:
            continue
        interfaces = match[1].strip()
        if suffix == "Wrath":
            titan = re.search(r"^## X-Interface-Titan:\s*(.+)$", source, re.MULTILINE)
            if titan:
                interfaces += ", " + titan[1].strip()
        lines = [f"## Interface: {interfaces}"]
        lines.extend(line for line in source.splitlines() if not re.match(r"^## Interface(?:-[^:]+)?:", line))
        result[f"SVCleaner_{suffix}.toc"] = "\n".join(lines) + "\n"
    return result


def build(output=None):
    output = Path(output or ROOT / "output" / "SVCleaner-0.1.0.zip")
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for path in runtime_files():
            archive.write(path, "SVCleaner/" + path.relative_to(ROOT).as_posix())
        for filename, content in flavor_tocs().items():
            archive.writestr("SVCleaner/" + filename, content)
    return output


if __name__ == "__main__":
    # Commit these explicit variants alongside the base TOC for .pkgmeta users.
    for filename, content in flavor_tocs().items():
        (ROOT / filename).write_text(content, encoding="utf-8")
    print(build())

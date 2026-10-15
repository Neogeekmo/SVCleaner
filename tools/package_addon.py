"""Build a minimal multi-client WoW archive with license notices."""
import argparse
import re
import subprocess
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


def package_version(version=None):
    if version is None:
        try:
            version = subprocess.check_output(["git", "describe", "--tags", "--always"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
        except (OSError, subprocess.CalledProcessError):
            version = "dev"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", version):
        raise ValueError("Invalid package version: " + str(version))
    return version


def build(output=None, version=None):
    version = package_version(version)
    output = Path(output or ROOT / "output" / f"SVCleaner-{version}.zip")
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for path in runtime_files():
            name = "SVCleaner/" + path.relative_to(ROOT).as_posix()
            if path.suffix == ".toc":
                archive.writestr(name, path.read_text(encoding="utf-8").replace("@project-version@", version))
            else:
                archive.write(path, name)
        for filename, content in flavor_tocs().items():
            archive.writestr("SVCleaner/" + filename, content.replace("@project-version@", version))
    return output


def build_companion(output=None, version=None):
    """Bundle the Python companion and everything its addon installer needs."""
    version = package_version(version)
    output = Path(output or ROOT / "output" / f"SVCleaner-Companion-{version}.zip")
    paths = runtime_files() + [ROOT / "companion" / name for name in ("app.py", "demo.py", "flavors.py", "lua_data.py", "runtime.py", "service.py")]
    paths += [ROOT / "companion" / "web" / name for name in ("index.html", "app.js", "style.css", "logo.svg")]
    paths += [ROOT / "tools" / "package_addon.py", ROOT / "Lancer-SVCleaner.cmd", ROOT / "README.md"]
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for path in paths:
            content = path.read_bytes()
            if path.suffix == ".toc":
                content = content.replace(b"@project-version@", version.encode("ascii"))
            archive.writestr("SVCleaner-Companion/" + path.relative_to(ROOT).as_posix(), content)
        for filename, content in flavor_tocs().items():
            archive.writestr("SVCleaner-Companion/" + filename, content.replace("@project-version@", version))
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version")
    parser.add_argument("--companion", action="store_true", help="Build the separate Python companion archive")
    args = parser.parse_args()
    for filename, content in flavor_tocs().items():
        (ROOT / filename).write_text(content, encoding="utf-8", newline="\n")
    print((build_companion if args.companion else build)(version=args.version))

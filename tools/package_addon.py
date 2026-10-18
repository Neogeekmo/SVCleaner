"""Build a minimal multi-client WoW archive with license notices."""
import argparse
import re
import subprocess
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parent.parent
ADDON = ROOT / "addon"
# Only used to retire files from older installations; new packages use one TOC.
LEGACY_TOC_NAMES = tuple(f"SVCleaner_{suffix}.toc" for suffix in ("Mainline", "Vanilla", "TBC", "Wrath", "Cata", "Mists", "Camelot"))


def runtime_files():
    toc = ADDON / "SVCleaner.toc"
    modules = [line.strip() for line in toc.read_text(encoding="utf-8").splitlines() if line.strip() and not line.lstrip().startswith("#")]
    paths = [toc] + [ADDON / module for module in modules] + [ADDON / "Assets" / "logo.tga", ADDON / "Assets" / "icons.tga"]
    for path in paths:
        if not path.is_file() or not path.resolve().is_relative_to(ADDON):
            raise ValueError("Invalid runtime file: " + str(path))
    paths += [ROOT / "LICENSE", ROOT / "NOTICE"]
    return paths


def runtime_name(path):
    """Installed addon paths are independent of the repository layout."""
    path = Path(path)
    if path in (ROOT / "LICENSE", ROOT / "NOTICE"):
        return path.name
    return path.relative_to(ADDON).as_posix()


def package_version(version=None):
    if version is None:
        try:
            version = subprocess.check_output(["git", "describe", "--tags", "--always"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
        except (OSError, subprocess.CalledProcessError):
            version = "dev"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", version):
        raise ValueError("Invalid package version: " + str(version))
    return version


def runtime_payload(version=None):
    """Shared installed bytes for local archives, sync and source installation.

    BigWigs consumes the same TOC and runtime sources; verify_archive validates
    that its output follows this contract before publication.
    """
    version = package_version(version)
    return {
        runtime_name(path): path.read_text(encoding="utf-8").replace("@project-version@", version).encode("utf-8")
        if path.suffix == ".toc" else path.read_bytes()
        for path in runtime_files()
    }


def build(output=None, version=None):
    version = package_version(version)
    output = Path(output or ROOT / "output" / f"SVCleaner-{version}.zip")
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for name, content in runtime_payload(version).items():
            archive.writestr("SVCleaner/" + name, content)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version")
    args = parser.parse_args()
    print(build(version=args.version))

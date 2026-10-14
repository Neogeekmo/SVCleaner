"""Generate runtime assets and build archives, or check them without modifying sources."""
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from package_addon import ROOT, build, build_companion, flavor_tocs

GENERATED = ["Locale.lua", "Assets/logo.tga", "Assets/icons.tga", "companion/web/logo.svg"]


def generate():
    for script in ("build_locales.py", "build_assets.py", "build_icons.py"):
        subprocess.run([sys.executable, str(ROOT / "tools" / script)], check=True)
    for name, content in flavor_tocs().items():
        (ROOT / name).write_text(content, encoding="utf-8", newline="\n")


def check():
    with tempfile.TemporaryDirectory(prefix="svc-generated-") as temporary:
        staging = Path(temporary)
        shutil.copytree(ROOT / "tools", staging / "tools", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT / "Assets", staging / "Assets")
        shutil.copy2(ROOT / "SVCleaner.toc", staging / "SVCleaner.toc")
        (staging / "companion" / "web").mkdir(parents=True)
        subprocess.run([sys.executable, str(staging / "tools" / "build.py"), "--generate-only"], check=True)
        stale = []
        for name in GENERATED + list(flavor_tocs()):
            original = ROOT / name
            generated = staging / name
            if original.suffix in (".lua", ".toc", ".svg"):
                matches = original.is_file() and original.read_text(encoding="utf-8") == generated.read_text(encoding="utf-8")
            else:
                matches = original.is_file() and original.read_bytes() == generated.read_bytes()
            if not matches:
                stale.append(name)
        if stale:
            raise SystemExit("Generated files are stale: " + ", ".join(stale) + ". Run python tools/build.py --generate-only and commit the results.")
    print("Generated locales, TOCs and assets are up to date.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--generate-only", action="store_true")
    parser.add_argument("--version", help="Archive version, e.g. v0.1.0 (default: Git description)")
    args = parser.parse_args()
    if args.check:
        check()
        return
    generate()
    if not args.generate_only:
        print(build(version=args.version))
        print(build_companion(version=args.version))


if __name__ == "__main__":
    main()

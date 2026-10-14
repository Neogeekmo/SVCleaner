"""Run the actual BigWigs packager on an isolated synthetic Git checkout.

No upload, externals, credentials, WoW writes, or workspace Git initialization.
The vendor script must first be saved under output/compatibility/packager.
"""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from package_addon import ROOT, runtime_files, flavor_tocs


def main():
    output = (ROOT / "output" / "compatibility" / "packager").resolve()
    script = output / "release.sh"
    if not script.is_file():
        raise SystemExit("Download https://raw.githubusercontent.com/BigWigsMods/packager/master/release.sh first")
    output.mkdir(parents=True, exist_ok=True)
    checkout = Path(tempfile.mkdtemp(prefix="check-", dir=output)).resolve()
    # BigWigs can remove its own release directory; keep that target contained.
    if not checkout.is_relative_to(output):
        raise ValueError("Temporary checkout escaped packaging output")
    for path in runtime_files() + [ROOT / ".pkgmeta", ROOT / "docs" / "changelog.md"]:
        target = checkout / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    for filename, content in flavor_tocs().items():
        (checkout / filename).write_text(content, encoding="utf-8")
    # Tracked canaries ensure the pkgmeta rules, rather than Git's untracked-file
    # exclusion, actually keep the companion, private data and masters out.
    for filename in ("companion/private.py", "tools/build.py", "tests/check.py", "docs/notes.md", "readme/assets/banner.svg", "readme/assets/grid-preview.png", "data/private.original", "output/private.zip", "README.md", "Lancer-SVCleaner.cmd", "Assets/logo.png", "Assets/source.svg", "debug.pyc", "pyproject.toml", "requirements-dev.txt", ".gitattributes", ".github/workflows/ci.yml", ".coverage", "coverage.xml", "htmlcov/index.html", ".venv/pyvenv.cfg", ".ruff_cache/cache", "AGENTS.md"):
        target = checkout / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("PACKAGING CANARY - synthetic, no user data", encoding="utf-8")
    def run(args):
        return subprocess.run(args, cwd=checkout, check=True, capture_output=True, text=True)
    run(["git", "init", "--quiet"])
    run(["git", "add", "."])
    run(["git", "-c", "user.name=Packaging test", "-c", "user.email=packaging-test@localhost", "commit", "--quiet", "-m", "Synthetic packaging verification"])
    bash = Path(r"C:\Program Files\Git\bin\bash.exe")
    # -z avoids depending on a zip executable; validate BigWigs' real copied
    # output, while package_addon.py creates the ready-to-use archive.
    def bash_path(path):
        value = Path(path).as_posix()
        return "/" + value[0].lower() + value[2:] if len(value) > 1 and value[1] == ":" else value
    command = [str(bash) if bash.is_file() else "bash", bash_path(script), "-d", "-e", "-l", "-z", "-u", "-t", bash_path(checkout)]
    result = subprocess.run(command, cwd=checkout, capture_output=True, text=True, timeout=120)
    (output / "build.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode:
        raise SystemExit("Packager failed; inspect " + str(output / "build.log"))
    folder = checkout / ".release" / "SVCleaner"
    actual = {path.relative_to(folder).as_posix() for path in folder.rglob("*") if path.is_file()}
    expected = {path.relative_to(ROOT).as_posix() for path in runtime_files()} | set(flavor_tocs())
    report = {"checkout": str(checkout), "actual": sorted(actual), "expected": sorted(expected), "passed": actual == expected}
    (output / "result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if actual != expected:
        raise SystemExit(f"Unexpected package contents: extra={actual - expected}, missing={expected - actual}")
    for filename, content in flavor_tocs().items():
        actual_toc = (folder / filename).read_text(encoding="utf-8")
        # BigWigs may preserve flavor-specific directives; check the actual
        # active Interface and module order instead of whitespace.
        expected_interface = content.splitlines()[0]
        if expected_interface not in actual_toc:
            raise SystemExit("Incorrect client Interface in " + filename)
    print("BigWigs .pkgmeta verified: " + str(len(actual)) + " runtime files, no companion, private data or PNG masters.")


if __name__ == "__main__":
    main()

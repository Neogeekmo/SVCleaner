"""Build a Windows x64 portable companion with its own Python runtime."""
import argparse
import hashlib
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from package_addon import ROOT, build, package_version

GUIDE = """SV Cleaner Companion — Windows 10/11 (64-bit)

1. Extract the entire ZIP into a folder where you have write access.
2. Double-click SVCleaner.exe. No Python installation is required.
3. On first launch, choose your WoW client folder (_retail_, _classic_, etc.).
   The local interface opens in your browser. Keep the console window open.
4. Close all WoW clients before applying changes.

Press Ctrl+C in the console to stop the companion. Closing the browser tab does
not stop it. Backups and history are stored in data/ beside SVCleaner.exe.
Keep this folder when updating. Do not run the application from inside the ZIP.
Keep the _internal folder beside the executable. Administrator rights are not required.
Your WoW folder selection is saved in wow-path.txt. Delete this file to choose again.
Do not include data/ or wow-path.txt when sharing the application.
The interface initially follows your browser language. Use the language selector
to choose any of WoW's eleven languages. Your choice is saved in data/preferences.json.

Options (run from PowerShell in this folder):
  .\\SVCleaner.exe --wow "D:\\Games\\World of Warcraft\\_retail_"
  .\\SVCleaner.exe --demo
  .\\SVCleaner.exe --language enUS
  .\\SVCleaner.exe --help
For troubleshooting, open PowerShell in this folder and run .\\SVCleaner.exe
to keep startup errors visible.

Source code and documentation: https://github.com/Neogeekmo/SVCleaner
LICENSE and NOTICE cover SV Cleaner. Runtime license notices are in licenses/.
"""


def build_portable(output=None, version=None):
    if sys.platform != "win32" or platform.machine().lower() not in ("amd64", "x86_64") or sys.maxsize <= 2**32:
        raise SystemExit("Build the Windows x64 package on Windows with 64-bit x86 Python.")
    try:
        import tkinter
        import PyInstaller  # noqa: F401 - fail before starting a partial build
    except ImportError as error:
        raise SystemExit("Use Python with Tcl/Tk and install requirements-packaging.txt first.") from error
    version = package_version(version)
    output = Path(output or ROOT / "output" / f"SVCleaner-Companion-{version}-windows-x64.zip").resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    cache = ROOT / ".cache"
    cache.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="portable-", dir=cache) as temporary:
        staging = Path(temporary)
        # Reuse the addon allowlist, multi-client TOC and version stamping.
        with ZipFile(build(staging / "addon.zip", version)) as archive:
            archive.extractall(staging / "resources")
        addon = staging / "resources" / "SVCleaner"
        subprocess.run([
            sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
            "--onedir", "--console", "--noupx", "--name", "SVCleaner",
            "--distpath", str(staging / "dist"), "--workpath", str(staging / "build"),
            "--specpath", str(staging),
            "--paths", str(ROOT / "companion"),
            "--add-data", f"{ROOT / 'companion' / 'web'}:companion/web",
            "--add-data", f"{addon}:addon",
            str(ROOT / "companion" / "app.py"),
        ], cwd=ROOT, check=True)
        bundle = staging / "dist" / "SVCleaner"
        for name in ("LICENSE", "NOTICE"):
            shutil.copy2(ROOT / name, bundle / name)
        (bundle / "README.txt").write_text(GUIDE, encoding="utf-8")
        (bundle / "VERSION.txt").write_text(version + "\n", encoding="ascii")
        licenses = bundle / "licenses"
        licenses.mkdir()
        shutil.copy2(Path(sys.base_prefix) / "LICENSE.txt", licenses / "Python.txt")
        tcl = Path(tkinter.Tcl().eval("info library"))
        # The Windows Python distribution includes the shared Tcl/Tk notice here.
        shutil.copy2(tcl.parent / f"tk{tkinter.TkVersion}" / "license.terms", licenses / "Tcl-Tk.txt")
        # Package only the fresh build, never local settings or user backups.
        with ZipFile(output, "w", ZIP_DEFLATED) as archive:
            for path in sorted(bundle.rglob("*")):
                if path.is_file():
                    archive.write(path, "SVCleaner-Companion/" + path.relative_to(bundle).as_posix())
    checksum = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(".zip.sha256").write_text(f"{checksum}  {output.name}\n", encoding="ascii")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    print(build_portable(args.output, args.version))

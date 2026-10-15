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

GUIDE = """SV Cleaner Companion — Windows 10/11 64 bits

1. Extrayez tout le ZIP dans un dossier où vous pouvez écrire.
2. Double-cliquez sur SVCleaner.exe (aucune installation de Python nécessaire).
3. Au premier lancement, choisissez votre dossier WoW (_retail_, _classic_, etc.).
   Le navigateur ouvre l'interface locale ; gardez la console ouverte.
4. Fermez tous les clients WoW avant d'appliquer des changements.

Ctrl+C dans la console arrête le companion. Fermer l'onglet ne l'arrête pas.
Les sauvegardes et l'historique restent dans data/ à côté de SVCleaner.exe.
Conservez ce dossier lors d'une mise à jour. Ne lancez pas l'application dans le ZIP
et gardez le dossier _internal avec l'exécutable. Aucun droit administrateur requis.
Le dossier WoW choisi est mémorisé dans wow-path.txt ; supprimez ce fichier pour
le choisir à nouveau. Ne partagez pas data/ ou wow-path.txt avec votre archive.

Options (depuis PowerShell dans ce dossier) :
  .\\SVCleaner.exe --wow "D:\\Jeux\\World of Warcraft\\_retail_"
  .\\SVCleaner.exe --demo
  .\\SVCleaner.exe --help
Pour un diagnostic, Lancer-SVCleaner.cmd garde les erreurs visibles.

Code source et documentation : https://github.com/Neogeekmo/SVCleaner
LICENSE et NOTICE concernent SV Cleaner ; licenses/ contient les notices du runtime.
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
        # Reuse the addon allowlist, generated TOCs and version stamping.
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
        for name in ("LICENSE", "NOTICE", "Lancer-SVCleaner.cmd"):
            shutil.copy2(ROOT / name, bundle / name)
        (bundle / "LIRE-MOI.txt").write_text(GUIDE, encoding="utf-8")
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

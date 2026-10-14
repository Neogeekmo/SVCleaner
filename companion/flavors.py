"""Identify a client from its installed build, without guessing from project IDs."""
import csv
import os
import re
import subprocess
from pathlib import Path

PRODUCTS = {
    "_retail_": "wow", "_ptr_": "wowt", "_xptr_": "wowxptr", "_beta_": "wow_beta",
    "_classic_": "wow_classic", "_classic_ptr_": "wow_classic_ptr", "_classic_beta_": "wow_classic_beta",
    "_classic_era_": "wow_classic_era", "_classic_era_ptr_": "wow_classic_era_ptr", "_classic_era_beta_": "wow_classic_era_beta",
    "_classic_anniversary_": "wow_anniversary", "_classic_anniversary_ptr_": "wow_anniversary_ptr",
    "_classic_titan_": "wow_classic_titan", "_classic_titan_ptr_": "wow_classic_titan_ptr", "_forever_": "wow_forever",
}


def flavor_from_version(version):
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", version or "")
    if not match:
        return None
    major, minor, patch = map(int, match.groups())
    if major == 1:
        flavor = "Camelot" if minor >= 60 else "Vanilla"
    else:
        flavor = {2: "TBC", 3: "Wrath", 4: "Cata", 5: "Mists"}.get(major, "Mainline")
    return {"flavor": flavor, "interface": major * 10000 + minor * 100 + patch, "version": match[0]}


def detect_client(root):
    root = Path(root).resolve()
    info = root.parent / ".build.info"
    product = PRODUCTS.get(root.name)
    if product and info.is_file():
        with info.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="|")
            for raw in reader:
                row = {key.split("!", 1)[0]: value for key, value in raw.items() if key}
                if row.get("Product") == product and row.get("Active") == "1":
                    result = flavor_from_version(row.get("Version"))
                    if result:
                        return {**result, "source": ".build.info", "uncertain": False}
    # Inactive PTR installs may not have a row in .build.info. Read the signed
    # executable's version resource; never execute the client or interpolate paths.
    if os.name == "nt":
        executables = sorted(root.glob("Wow*.exe")) + sorted(root.glob("WoW*.exe"))
        for executable in dict.fromkeys(executables):
            environment = dict(os.environ, SVC_CLIENT_EXE=str(executable))
            try:
                result = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", "(Get-Item -LiteralPath $env:SVC_CLIENT_EXE).VersionInfo.FileVersion"], env=environment, capture_output=True, text=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
                detected = flavor_from_version(result.stdout.strip()) if result.returncode == 0 else None
                if detected:
                    return {**detected, "source": executable.name, "uncertain": False}
            except (OSError, subprocess.TimeoutExpired):
                pass
    # Ordinary Retail/Era folders are unambiguous families. A Classic PTR/beta
    # without a build remains ambiguous: inspect all TOCs and flag that result.
    flavor = "Vanilla" if root.name == "_classic_era_" else "Camelot" if root.name == "_forever_" else None if "classic" in root.name else "Mainline"
    return {"flavor": flavor, "interface": None, "version": None, "source": "folder", "uncertain": flavor is None}


def toc_candidates(folder, flavor):
    aliases = {"Mainline": ("Mainline",), "Vanilla": ("Vanilla", "Classic"), "TBC": ("TBC", "BCC"), "Wrath": ("Wrath", "WOTLKC"), "Cata": ("Cata",), "Mists": ("Mists",), "Camelot": ("Camelot",)}
    candidates = []
    for suffix in aliases.get(flavor, ()):
        candidates.extend(folder / f"{folder.name}{separator}{suffix}.toc" for separator in ("_", "-"))
    candidates.append(folder / f"{folder.name}.toc")
    return candidates

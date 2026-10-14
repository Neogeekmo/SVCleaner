"""Cache pinned Blizzard UI references for the compatibility audit (read-only)."""
import concurrent.futures
import json
import os
import re
import urllib.request
from urllib.parse import urlsplit
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / "compatibility"
BRANCHES = ("live", "ptr", "ptr2", "beta", "classic", "classic_ptr", "classic_era", "classic_era_ptr", "classic_anniversary", "classic_titan", "forever", "classic_beta")
HEADERS = {"User-Agent": "SVCleaner-compatibility-check", "Accept": "application/vnd.github+json"}


def fetch(url):
    headers = dict(HEADERS)
    # Authentication is restricted to GitHub's API host; raw downloads and
    # archive URLs must never receive the workflow token.
    if urlsplit(url).hostname == "api.github.com" and os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=25) as response:
        return response.read()


def inspect_branch(branch, sha):
    folder = OUT / "reference" / branch
    folder.mkdir(parents=True, exist_ok=True)
    commit = json.loads(fetch(f"https://api.github.com/repos/Gethe/wow-ui-source/commits/{sha}"))
    message = commit["commit"]["message"].splitlines()[0]
    version = re.search(r"\d+\.\d+\.\d+", message)
    files = json.loads(fetch(f"https://api.github.com/repos/Gethe/wow-ui-source/contents/Interface/AddOns/Blizzard_APIDocumentationGenerated?ref={sha}"))
    required = {"AddOnsDocumentation.lua", "FrameScriptDocumentation.lua", "UnitDocumentation.lua", "UiTimerDocumentation.lua", "SimpleFrameAPIDocumentation.lua", "SimpleRegionAPIDocumentation.lua", "SimpleTextureAPIDocumentation.lua", "SimpleFontStringAPIDocumentation.lua", "SimpleEditBoxAPIDocumentation.lua", "SimpleButtonAPIDocumentation.lua"}
    selected = [entry for entry in files if entry["name"] in required or any(part in entry["name"] for part in ("Unit", "Timer", "Simple", "Realm", "Restriction", "FrameFactory", "Combat"))]
    names = set()
    for entry in selected:
        source = fetch(entry["download_url"])
        (folder / entry["name"]).write_bytes(source)
        names.update(re.findall(r'Name\s*=\s*"([A-Za-z_0-9]+)"', source.decode("utf-8")))
    backdrop_path = None
    for candidate in ("Interface/AddOns/Blizzard_SharedXML/Backdrop.lua", "Interface/AddOns/Blizzard_SharedXMLBase/Backdrop.lua", "Interface/SharedXML/Backdrop.lua"):
        try:
            source = fetch(f"https://raw.githubusercontent.com/Gethe/wow-ui-source/{sha}/{candidate}")
            (folder / "Backdrop.lua").write_bytes(source)
            backdrop_path = candidate
            break
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
    functions = ("GetNumAddOns", "GetAddOnInfo", "GetAddOnMetadata", "IsAddOnLoaded", "CreateFrame", "UnitFullName", "UnitName", "UnitGUID", "GetRealmName", "InCombatLockdown", "After")
    methods = ("SetShown", "SetColorTexture", "SetTextColor", "SetPoint", "SetSize", "SetFrameLevel", "SetMaxLetters", "SetAutoFocus", "SetTextInsets", "SetClampedToScreen", "SetMovable", "RegisterForDrag", "SetHighlightTexture", "SetScale")
    row = {"branch": branch, "sha": sha, "commit": message, "version": version[0] if version else None, "functions": {name: name in names for name in functions}, "methods": {name: name in names for name in methods}, "backdrop": backdrop_path, "files": [entry["name"] for entry in selected], "source": f"https://github.com/Gethe/wow-ui-source/tree/{sha}"}
    print(json.dumps({key: value for key, value in row.items() if key != "files"}), flush=True)
    return row


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    branches = json.loads(fetch("https://api.github.com/repos/Gethe/wow-ui-source/branches?per_page=100"))
    shas = {branch["name"]: branch["commit"]["sha"] for branch in branches}
    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(inspect_branch, branch, shas[branch]): branch for branch in BRANCHES if branch in shas}
        for future in concurrent.futures.as_completed(futures):
            branch = futures[future]
            try:
                rows.append(future.result())
            except Exception as error:
                print(json.dumps({"branch": branch, "error": str(error)}), flush=True)
                rows.append({"branch": branch, "sha": shas[branch], "error": str(error)})
    (OUT / "reference-audit.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    if not rows or any("error" in row for row in rows):
        raise SystemExit("Incomplete reference download; inspect reference-audit.json")


if __name__ == "__main__":
    main()

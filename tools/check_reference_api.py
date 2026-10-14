"""Supplement generated API docs with actual Blizzard UI call sites, pinned to SHA."""
import concurrent.futures
import io
import json
import re
import urllib.error
from pathlib import Path
from zipfile import ZipFile

from fetch_wow_reference import fetch, OUT

PATHS = (
    "Interface/AddOns/Blizzard_UIParent/UIParent.lua",
    "Interface/AddOns/Blizzard_UIParent/Mainline/UIParentMainline.lua",
    "Interface/AddOns/Blizzard_UIParent/Shared/UIParentShared.lua",
    "Interface/AddOns/Blizzard_UIParent/Classic/UIParentClassic.lua",
    "Interface/AddOns/Blizzard_FrameXML/SecureTemplates.lua",
    "Interface/AddOns/Blizzard_FrameXMLBase/SecureTemplates.lua",
    "Interface/AddOns/Blizzard_ChatFrameBase/Shared/ChatFrameUtil.lua",
    "Interface/AddOns/Blizzard_ChatFrameBase/Shared/ChatFrameEditBox.lua",
    "Interface/AddOns/Blizzard_ObjectAPI/Mainline/PlayerLocation.lua",
    "Interface/AddOns/Blizzard_UIParent/Mainline/UIParent.lua",
    "Interface/AddOns/Blizzard_UIParent/Shared/UIParent.lua",
    "Interface/AddOns/Blizzard_UIParent/Classic/UIParent.lua",
    "Interface/AddOns/Blizzard_SharedXMLBase/FrameUtil.lua",
    "Interface/AddOns/Blizzard_SharedXML/FrameUtil.lua",
    "Interface/FrameXML/UIParent.lua",
    "Interface/SharedXML/FrameUtil.lua",
    "Interface/AddOns/Blizzard_ChatFrameBase/Shared/ChatFrame.lua",
    "Interface/AddOns/Blizzard_ChatFrame/Shared/ChatFrame.lua",
    "Interface/FrameXML/ChatFrame.lua",
)


def check(row):
    evidence = {}
    for path in PATHS:
        url = f"https://raw.githubusercontent.com/Gethe/wow-ui-source/{row['sha']}/{path}"
        try:
            source = fetch(url).decode("utf-8")
        except urllib.error.HTTPError as error:
            if error.code == 404:
                continue
            raise
        target = OUT / "reference" / row["branch"] / ("Callsites-" + path.replace("/", "-"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")
        for name in ("CreateFrame", "GetRealmName", "InCombatLockdown"):
            if re.search(r"\b" + name + r"\s*\(", source):
                evidence.setdefault(name, url)
    # Legacy globals are not all present in the generated docs. Search the
    # pinned full UI export for real call sites rather than interpreting an
    # absent documentation entry as an unavailable client function.
    unresolved = {name for name, present in row["functions"].items() if not present and name not in evidence}
    if unresolved:
        with ZipFile(io.BytesIO(fetch(f"https://codeload.github.com/Gethe/wow-ui-source/zip/{row['sha']}"))) as archive:
            for filename in archive.namelist():
                if not filename.endswith(".lua"):
                    continue
                source = archive.read(filename).decode("utf-8", errors="replace")
                for name in list(unresolved):
                    if re.search(r"\b" + name + r"\s*\(", source):
                        path = filename.split("/", 1)[1]
                        evidence[name] = f"https://github.com/Gethe/wow-ui-source/blob/{row['sha']}/{path}"
                        unresolved.remove(name)
                if not unresolved:
                    break
    row["callSites"] = evidence
    row["apiChecks"] = {name: present or name in evidence for name, present in row["functions"].items()}
    return row


def archived(branch, sha, version):
    names = set()
    for directory in ("Interface/AddOns/Blizzard_APIDocumentationGenerated", "Interface/AddOns/Blizzard_APIDocumentation", "Interface/SharedXML"):
        for filename in ("AddOnsDocumentation.lua", "UnitDocumentation.lua", "UnitSharedDocumentation.lua", "UITimerDocumentation.lua", "SimpleFrameAPIDocumentation.lua"):
            try:
                source = fetch(f"https://raw.githubusercontent.com/Gethe/wow-ui-source/{sha}/{directory}/{filename}")
            except urllib.error.HTTPError as error:
                if error.code == 404:
                    continue
                raise
            target = OUT / "reference" / branch / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source)
            names.update(re.findall(r'Name\s*=\s*"([A-Za-z_0-9]+)"', source.decode("utf-8")))
    return {"branch": branch, "sha": sha, "commit": "Archived tag " + version, "version": version,
            "functions": {name: name in names for name in ("GetNumAddOns", "GetAddOnInfo", "GetAddOnMetadata", "IsAddOnLoaded", "CreateFrame", "UnitFullName", "UnitName", "UnitGUID", "GetRealmName", "InCombatLockdown", "After")},
            "source": f"https://github.com/Gethe/wow-ui-source/tree/{sha}"}


if __name__ == "__main__":
    rows = json.loads((OUT / "reference-audit.json").read_text())
    if not rows or any("error" in row for row in rows):
        raise SystemExit("Reference download failed or produced an empty audit")
    rows = [row for row in rows if row["branch"] != "classic_beta"]
    rows.extend((archived("cata-4.4.2", "a1ca983a43a7aa73b5764d3245925ba40869fce3", "4.4.2"),
                 archived("wrath-3.4.3", "564ca565fd2de4d1bd4ca787d75d9f8c6d1ffcde", "3.4.3")))
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        result = list(executor.map(check, rows))
    (OUT / "api-audit.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    for row in result:
        print(row["branch"], row["version"], "unresolved:", [name for name, present in row["apiChecks"].items() if not present])
    # UnitFullName, UnitName and C_Timer.After have explicit runtime fallbacks.
    required = ("GetNumAddOns", "GetAddOnInfo", "GetAddOnMetadata", "IsAddOnLoaded", "CreateFrame", "UnitGUID", "GetRealmName", "InCombatLockdown")
    if any(not all(row["apiChecks"][name] for name in required) for row in result):
        raise SystemExit("Required WoW APIs could not be verified; inspect api-audit.json")

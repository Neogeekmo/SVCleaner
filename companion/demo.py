import tempfile
from pathlib import Path


def demo_root():
    root = Path(tempfile.mkdtemp(prefix="svcleaner-demo-")) / "_retail_"
    addons = root / "Interface" / "AddOns"
    account = root / "WTF" / "Account" / "DEMO"
    sv = account / "SavedVariables"
    sv.mkdir(parents=True)
    for name, declarations in {"APR": "APRData, APRSettings", "Vaultloom": "VaultloomDB", "Details": "DetailsData", "WeakAuras": "WeakAurasSaved", "Baganator": "BaganatorDB"}.items():
        folder = addons / name
        folder.mkdir(parents=True)
        (folder / f"{name}.toc").write_text(f"## Interface: 120100\n## Title: {name}\n## SavedVariables: {declarations}\n", encoding="utf-8")
    (sv / "APR.lua").write_text('''APRData = {
["Elowen-Player-1305-00000001"] = { ["GUID"] = "Player-1305-00000001", ["route"] = { ["step"] = 42, ["skipCutscenes"] = true, ["scale"] = 1.0 }, ["completed"] = { [2021] = true, [2022] = true } },
["Thalion-Player-1305-00000002"] = { ["GUID"] = "Player-1305-00000002", ["route"] = { ["step"] = 16, ["skipCutscenes"] = false, ["scale"] = 0.8 }, ["completed"] = { [2021] = true, [2022] = false } },
["Ancien-Player-1305-00000003"] = { ["GUID"] = "Player-1305-00000003", ["route"] = { ["step"] = 9 } },
}
APRSettings = { ["profileKeys"] = { ["Elowen - Kirin Tor"] = "Default", ["Thalion - Kirin Tor"] = "Default" }, ["profiles"] = { ["Default"] = { ["theme"] = "dark", ["scale"] = 1 } } }
''', encoding="utf-8")
    for name, variable, size in [("Vaultloom", "VaultloomDB", 150000), ("Details", "DetailsData", 920000), ("WeakAuras", "WeakAurasSaved", 1400000), ("Baganator", "BaganatorDB", 98000), ("OldQuestHelper", "OldQuestDB", 480000), ("LegacyMaps", "LegacyMapsDB", 195000)]:
        (sv / f"{name}.lua").write_text(f'{variable} = {{ ["settings"] = {{ ["enabled"] = true, ["scale"] = 1 }}, ["archive"] = "' + "x" * size + '" }\n', encoding="utf-8")
    (sv / "APR.lua.bak").write_bytes((sv / "APR.lua").read_bytes())
    (sv / "SVCleaner.lua").write_text('SVCleanerDB = { ["characters"] = { ["Player-1305-00000001"] = { ["name"] = "Elowen", ["realm"] = "Kirin Tor" }, ["Player-1305-00000002"] = { ["name"] = "Thalion", ["realm"] = "Kirin Tor" } } }', encoding="utf-8")
    (account / "Kirin Tor" / "Elowen" / "SavedVariables").mkdir(parents=True)
    (account / "Kirin Tor" / "Thalion" / "SavedVariables").mkdir(parents=True)
    cache = root / "Cache" / "WDB"
    cache.mkdir(parents=True)
    (cache / "demo.wdb").write_bytes(b"0" * 650000)
    classic = root.parent / "_classic_era_"
    (classic / "Interface" / "AddOns" / "APR").mkdir(parents=True)
    (classic / "Interface" / "AddOns" / "APR" / "APR.toc").write_text("## SavedVariables: APRData\n", encoding="utf-8")
    classic_sv = classic / "WTF" / "Account" / "CLASSIC_DEMO" / "SavedVariables"
    classic_sv.mkdir(parents=True)
    (classic_sv / "APR.lua").write_text('APRData = { ["Classic-Player-1-00001"] = { ["step"] = 5 } }\n', encoding="utf-8")
    ptr = root.parent / "_ptr_"
    (ptr / "Interface" / "AddOns").mkdir(parents=True)
    return root

"""Update this installed addon with a reversible source backup, preserving Manifest.

This never reads or writes WTF or SavedVariables. Restart WoW to load new TOCs.
"""
import argparse
import json
from datetime import datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from package_addon import ROOT, LEGACY_TOC_NAMES, runtime_payload


def sync(client):
    client=Path(client).resolve()
    target=(client/"Interface"/"AddOns"/"SVCleaner").resolve()
    if not target.is_relative_to(client) or not target.is_dir() or target.is_symlink():
        raise ValueError("Existing SVCleaner folder required inside this client")
    toc=(target/"SVCleaner.toc").read_text(encoding="utf-8-sig")
    if "## Title: SVCleaner" not in toc or "## SavedVariables: SVCleanerDB" not in toc:
        raise ValueError("This is not the expected SVCleaner installation")
    payload=runtime_payload()
    del payload["Manifest.lua"]
    relative=[Path(name) for name in payload]+[Path(name) for name in LEGACY_TOC_NAMES]
    for name in relative:
        if not (target/name).resolve().is_relative_to(target):
            raise ValueError("Runtime path escaped addon folder")
    backup=ROOT/"output"/("addon-before-ui-"+datetime.now().strftime("%Y%m%d-%H%M%S")+".zip")
    backup.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(backup,"x",ZIP_DEFLATED) as archive:
        for name in relative:
            source=target/name
            if source.is_file(): archive.write(source,"SVCleaner/"+name.as_posix())
    for name,content in payload.items():
        destination=target/name; destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes(content)
    removed=[]
    for name in LEGACY_TOC_NAMES:
        obsolete=target/name
        if obsolete.is_file():
            obsolete.unlink()
            removed.append(name)
    report={"target":str(target),"backup":str(backup),"manifestPreserved":True,"copied":list(payload),"removed":removed}
    (ROOT/"output"/"addon-sync.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=True))
    return report


if __name__=="__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("--wow",required=True); args=parser.parse_args(); sync(args.wow)

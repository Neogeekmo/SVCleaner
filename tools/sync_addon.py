"""Update this installed addon with a reversible source backup, preserving Manifest.

This never reads or writes WTF or SavedVariables. Restart WoW to load new TOCs.
"""
import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from package_addon import ROOT, runtime_files, flavor_tocs, package_version


def sync(client):
    client=Path(client).resolve()
    target=(client/"Interface"/"AddOns"/"SVCleaner").resolve()
    if not target.is_relative_to(client) or not target.is_dir() or target.is_symlink():
        raise ValueError("Existing SVCleaner folder required inside this client")
    toc=(target/"SVCleaner.toc").read_text(encoding="utf-8-sig")
    if "## Title: SVCleaner" not in toc or "## SavedVariables: SVCleanerDB" not in toc:
        raise ValueError("This is not the expected SVCleaner installation")
    paths=[path for path in runtime_files() if path.name!="Manifest.lua"]
    variants=flavor_tocs()
    version=package_version()
    relative=[path.relative_to(ROOT) for path in paths]+[Path(name) for name in variants]
    for name in relative:
        if not (target/name).resolve().is_relative_to(target):
            raise ValueError("Runtime path escaped addon folder")
    backup=ROOT/"output"/("addon-before-ui-"+datetime.now().strftime("%Y%m%d-%H%M%S")+".zip")
    backup.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(backup,"x",ZIP_DEFLATED) as archive:
        for name in relative:
            source=target/name
            if source.is_file(): archive.write(source,"SVCleaner/"+name.as_posix())
    for path in paths:
        destination=target/path.relative_to(ROOT); destination.parent.mkdir(parents=True,exist_ok=True)
        if path.suffix == ".toc":
            destination.write_text(path.read_text(encoding="utf-8").replace("@project-version@", version), encoding="utf-8")
        else:
            shutil.copy2(path,destination)
    for name,content in variants.items():
        (target/name).write_text(content.replace("@project-version@", version),encoding="utf-8")
    report={"target":str(target),"backup":str(backup),"manifestPreserved":True,"copied":[name.as_posix() for name in relative]}
    (ROOT/"output"/"addon-sync.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=True))
    return report


if __name__=="__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("--wow",required=True); args=parser.parse_args(); sync(args.wow)

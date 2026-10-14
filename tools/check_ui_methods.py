"""Verify native widget methods against the cached current Blizzard exports."""
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
METHODS=("SetEnabled","SetResizable","SetResizeBounds","StartSizing","GetStringHeight","SetThumbTexture","SetValueStep","SetVerticalScroll","SetScrollChild","SetJustifyV")

if __name__=="__main__":
    directory=ROOT/"output"/"compatibility"
    rows=json.loads((directory/"api-audit.json").read_text())
    results=[]
    for row in rows:
        if row["branch"].startswith(("cata-","wrath-")):
            continue
        names=set()
        for path in (directory/"reference"/row["branch"]).glob("Simple*Documentation.lua"):
            names.update(re.findall(r'Name\s*=\s*"([A-Za-z_0-9]+)"',path.read_text(encoding="utf-8")))
        checks={method:method in names for method in METHODS}
        results.append({"branch":row["branch"],"checks":checks})
        print(row["branch"],"missing:",[method for method,present in checks.items() if not present])
    (directory/"ui-methods.json").write_text(json.dumps(results,indent=2),encoding="utf-8")
    if any(not all(row["checks"].values()) for row in results):
        raise SystemExit(1)

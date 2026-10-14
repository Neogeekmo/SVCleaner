"""Read-only compatibility checks on this machine's SavedVariables."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "companion"))
from lua_data import dump, parse
from service import DEFAULT_WOW, Store


store = Store(DEFAULT_WOW)
records = [r for r in store.records.values() if not r["backup"] and r["scope"] != "system"]
selected = [r for r in records if r["addon"] in ("APR", "Vaultloom") and r["scope"] == "account" and r["bytes"] <= 2 * 1024 * 1024]
selected += sorted([r for r in records if r["scope"] == "account" and r not in selected and r["bytes"] <= 2 * 1024 * 1024], key=lambda r: -r["bytes"])[:10]
start = time.perf_counter()
for record in selected:
    roots = store.load(record["id"])
    restored = parse(dump(roots))
    if roots != restored:
        raise AssertionError("Round-trip mismatch: " + record["addon"])
    print(f'{record["addon"]}: {record["bytes"]} bytes, {len(roots.entries)} roots, round-trip OK', flush=True)
print(f'{len(selected)} files verified read-only in {time.perf_counter() - start:.2f}s')

"""Validate the actual release ZIP against the runtime allowlist before upload."""
import argparse
import re
from zipfile import ZipFile

from package_addon import ROOT, flavor_tocs, runtime_files


def verify(path, version=None):
    expected = {"SVCleaner/" + p.relative_to(ROOT).as_posix() for p in runtime_files()}
    expected.update("SVCleaner/" + name for name in flavor_tocs())
    with ZipFile(path) as archive:
        files = [info.filename for info in archive.infolist() if not info.is_dir()]
        if len(files) != len(set(files)) or set(files) != expected:
            raise ValueError(f"Unexpected archive contents: extra={set(files) - expected}, missing={expected - set(files)} (duplicates forbidden)")
        corrupt = archive.testzip()
        if corrupt:
            raise ValueError("Corrupt archive entry: " + corrupt)
        modules = [p.relative_to(ROOT).as_posix() for p in runtime_files() if p.suffix == ".lua"]
        for name in sorted(expected):
            data = archive.read(name)
            if not data:
                raise ValueError("Empty runtime file: " + name)
            if not name.endswith(".toc"):
                continue
            toc = data.decode("utf-8")
            loaded = [line.strip() for line in toc.splitlines() if line.strip() and not line.lstrip().startswith("#")]
            if loaded != modules:
                raise ValueError("Incorrect module loading order: " + name)
            if "@project-version@" in toc:
                raise ValueError("Unresolved version placeholder: " + name)
            for field, value in (("X-Curse-Project-ID", "1744570"), ("X-Wago-ID", "mNww8PNo"), ("SavedVariables", "SVCleanerDB")):
                if not re.search(r"^## " + field + ": " + re.escape(value) + r"$", toc, re.MULTILINE):
                    raise ValueError("Incorrect " + field + " in " + name)
            if version and not re.search(r"^## Version: " + re.escape(version) + r"$", toc, re.MULTILINE):
                raise ValueError("Incorrect release version in " + name)
            flavor = name.removeprefix("SVCleaner/")
            if flavor in flavor_tocs() and flavor_tocs()[flavor].splitlines()[0] not in toc.splitlines():
                raise ValueError("Incorrect client interface: " + name)
    print(f"Verified {path}: {len(expected)} runtime files, all client TOCs, no development or private files.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", nargs="+")
    parser.add_argument("--version")
    args = parser.parse_args()
    for path in args.archives:
        verify(path, args.version)

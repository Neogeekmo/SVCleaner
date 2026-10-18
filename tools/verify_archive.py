"""Validate the actual release ZIP against the runtime allowlist before upload."""
import argparse
import re
from zipfile import ZipFile

from package_addon import runtime_files, runtime_name, runtime_payload


def verify(path, version=None):
    expected = {"SVCleaner/" + runtime_name(p) for p in runtime_files()}
    payload = runtime_payload(version)
    with ZipFile(path) as archive:
        files = [info.filename for info in archive.infolist() if not info.is_dir()]
        # BigWigs adds this file when .pkgmeta has no manual changelog.
        if "SVCleaner/CHANGELOG.md" in files:
            expected.add("SVCleaner/CHANGELOG.md")
        if len(files) != len(set(files)) or set(files) != expected:
            raise ValueError(f"Unexpected archive contents: extra={set(files) - expected}, missing={expected - set(files)} (duplicates forbidden)")
        corrupt = archive.testzip()
        if corrupt:
            raise ValueError("Corrupt archive entry: " + corrupt)
        modules = [runtime_name(p) for p in runtime_files() if p.suffix == ".lua"]
        for name in sorted(expected):
            data = archive.read(name)
            if not data:
                raise ValueError("Empty runtime file: " + name)
            if not name.endswith(".toc"):
                source = payload.get(name.removeprefix("SVCleaner/"))
                # BigWigs normalizes line endings; binary assets must match exactly.
                if source is not None:
                    actual = data.replace(b"\r\n", b"\n") if name.endswith(".lua") else data
                    wanted = source.replace(b"\r\n", b"\n") if name.endswith(".lua") else source
                    if actual != wanted:
                        raise ValueError("Runtime content differs from source: " + name)
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
            def interfaces(content):
                values = re.findall(r"^## Interface:\s*([^\r\n]+)", content, re.MULTILINE)
                if len(values) != 1:
                    raise ValueError("Expected one Interface directive: " + name)
                result = {value.strip() for value in values[0].split(",")}
                if not all(value.isdecimal() for value in result):
                    raise ValueError("Invalid interface number: " + name)
                return result
            if interfaces(toc) != interfaces(payload["SVCleaner.toc"].decode("utf-8")):
                raise ValueError("Incorrect client interfaces: " + name)
    print(f"Verified {path}: {len(expected)} runtime files, one multi-client TOC, no development or private files.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", nargs="+")
    parser.add_argument("--version")
    args = parser.parse_args()
    for path in args.archives:
        verify(path, args.version)

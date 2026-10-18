"""Exercise the extracted Windows executable without Python on PATH or real WoW data."""
import argparse
import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener
from zipfile import ZipFile


def verify(archive_path, read_only=False):
    with tempfile.TemporaryDirectory(prefix="svc portable é ") as temporary:
        directory = Path(temporary)
        with ZipFile(archive_path) as archive:
            names = archive.namelist()
            assert not any("/data/" in name or name.endswith(("wow-path.txt", ".original", ".pyc")) for name in names), "Private files in package"
            archive.extractall(directory)
        bundle = directory / "SVCleaner-Companion"
        executable = bundle / "SVCleaner.exe"
        assert executable.read_bytes()[:2] == b"MZ", "Expected a Windows executable"
        for name in ("README.txt", "_internal/companion/web/index.html", "_internal/companion/web/i18n.js", "_internal/companion/web/locales.json", "_internal/_tcl_data/init.tcl", "_internal/_tk_data/tk.tcl", "licenses/Python.txt", "licenses/Tcl-Tk.txt"):
            assert (bundle / name).is_file(), f"Missing resource: {name}"
        root = directory / "WoW fictif" / "_retail_"
        (root / "Interface" / "AddOns").mkdir(parents=True)
        sv = root / "WTF" / "Account" / "TEST" / "SavedVariables" / "Removed.lua"
        sv.parent.mkdir(parents=True)
        original = b'OldDB = { value = 42 }\n'
        sv.write_bytes(original)
        env = dict(os.environ)
        for key in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV", "TCL_LIBRARY", "TK_LIBRARY"):
            env.pop(key, None)
        env["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
        env["PYTHONUTF8"] = "1"
        command = [str(executable), "--wow", str(root)]
        options = dict(cwd=directory, env=env, creationflags=subprocess.CREATE_NO_WINDOW)

        def run(args):
            return subprocess.run([str(executable)] + args, capture_output=True, text=True, encoding="utf-8", check=True, timeout=60, **options)

        run(["--help"])
        assert json.loads(run(["--demo", "--scan"]).stdout)["files"] > 0
        assert json.loads(run(["--wow", str(root), "--scan"]).stdout)["files"] == 1
        if not read_only:
            run(["--wow", str(root), "--install-addon"])
            installed = root / "Interface" / "AddOns" / "SVCleaner"
            version = (bundle / "VERSION.txt").read_text().strip()
            for toc in installed.glob("*.toc"):
                assert f"## Version: {version}" in toc.read_text(encoding="utf-8")
            assert [path.name for path in installed.glob("*.toc")] == ["SVCleaner.toc"]
            toc = (installed / "SVCleaner.toc").read_text(encoding="utf-8")
            for module in (line.strip() for line in toc.splitlines() if line.strip() and not line.startswith("#")):
                assert (installed / module).is_file(), f"Missing addon module: {module}"
            assert "SVC.Manifest" in (installed / "Manifest.lua").read_text()
        opener = build_opener(ProxyHandler({}))

        def session(action):
            with (directory / "server.log").open("w", encoding="utf-8") as log:
                process = subprocess.Popen(command + ["--no-browser"], stdout=log, stderr=log, **options)
                try:
                    deadline = time.monotonic() + 60
                    while True:
                        output = (directory / "server.log").read_text(encoding="utf-8")
                        match = re.search(r"http://127\.0\.0\.1:\d+/", output)
                        if match:
                            break
                        assert process.poll() is None, output
                        assert time.monotonic() < deadline, "Server startup timed out: " + output
                        time.sleep(0.1)
                    url = match[0]

                    def get(path):
                        with opener.open(url + path, timeout=15) as response:
                            return response.read()

                    state = json.loads(get("api/state"))

                    def post(path, body):
                        request = Request(url + "api/" + path, json.dumps(body).encode(), headers={"Content-Type": "application/json", "X-SVC-Token": state["csrf"]})
                        with opener.open(request, timeout=30) as response:
                            return json.load(response)

                    for path, marker in (("", b"<html"), ("app.js", b"function"), ("i18n.js", b"I18n"), ("style.css", b"{"), ("logo.svg", b"<svg")):
                        assert marker in get(path), "Missing web asset: " + path
                    catalogs = json.loads(get("locales.json"))
                    assert len(catalogs) == 11
                    for language, catalog in catalogs.items():
                        request = Request(url + "api/stage", json.dumps({"id": "missing", "operation": "delete-file"}).encode(), headers={"X-SVC-Token": state["csrf"], "X-SVC-Language": language})
                        try:
                            opener.open(request, timeout=15)
                            raise AssertionError("Unknown record was accepted")
                        except HTTPError as error:
                            with error:
                                assert error.code == 400
                                assert json.load(error)["error"] == catalog["Fichier inconnu ; rescannez"]
                    action(state, post)
                finally:
                    process.terminate()
                    try:
                        process.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=15)

        def apply(state, post):
            record = next(item for item in state["records"] if item["addon"] == "Removed")
            post("delete-files", {"ids": [record["id"]]})
            result = post("apply", {})
            assert result["transaction"]["status"] == "applied"
            assert not sv.exists()

        if read_only:
            session(lambda state, post: None)
            print(f"Verified {Path(archive_path).name}: standalone CLI, demo and HTTP assets (read-only; write checks not run).")
            return
        session(apply)
        backups = list((bundle / "data").glob("*/*/*.original"))
        assert len(backups) == 1 and backups[0].read_bytes() == original
        assert not (directory / "data").exists(), "Data must not depend on the working directory"
        assert not (bundle / "_internal" / "data").exists(), "Data must survive runtime replacement"

        def restore(state, post):
            transaction = next(item for item in state["history"] if item["status"] == "applied")
            post("restore", {"id": transaction["id"]})
            assert sv.read_bytes() == original

        session(restore)
        print(f"Verified {Path(archive_path).name}: standalone CLI, demo, HTTP assets, addon install, backup and restore after restart.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--read-only", action="store_true", help="Check startup and HTTP assets without write tests (WoW may stay open)")
    args = parser.parse_args()
    verify(args.archive.resolve(), args.read_only)

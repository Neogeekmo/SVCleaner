"""Exercise client selection and the real archive contract without touching WoW."""
import sys
import runpy
import shutil
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "companion"))
sys.path.insert(0, str(ROOT / "tools"))
from flavors import detect_client, toc_candidates
from package_addon import ADDON, LEGACY_TOC_NAMES, build, runtime_files, runtime_name
from verify_archive import verify
from service import Store


class ClientTests(unittest.TestCase):
    def test_installed_build_overrides_ambiguous_folder_names(self):
        with tempfile.TemporaryDirectory(prefix="svc-flavor-") as temporary:
            parent = Path(temporary)
            (parent / ".build.info").write_text(
                "Product!STRING:0|Active!DEC:1|Version!STRING:0\n"
                "wow_classic|1|5.5.4.70268\n"
                "wow_classic_beta|1|1.60.1.70338\n"
                "wow_classic_era_ptr|1|2.5.6.70006\n", encoding="utf-8")
            for folder, flavor, interface in (("_classic_", "Mists", 50504), ("_classic_beta_", "Camelot", 16001), ("_classic_era_ptr_", "TBC", 20506)):
                with self.subTest(folder=folder):
                    client = detect_client(parent / folder)
                    self.assertEqual((client["flavor"], client["interface"], client["uncertain"]), (flavor, interface, False))

    def test_scan_uses_selected_family_and_keeps_unknown_client_uncertain(self):
        with tempfile.TemporaryDirectory(prefix="svc-tocs-") as temporary:
            parent = Path(temporary)
            root = parent / "_classic_"
            addon = root / "Interface" / "AddOns" / "Example"
            addon.mkdir(parents=True)
            (addon / "Example.toc").write_text("## SavedVariables: FallbackDB\n")
            (addon / "Example_Mainline.toc").write_text("## SavedVariables: RetailDB\n")
            (addon / "Example_Mists.toc").write_text("## SavedVariables: MistsDB\n")
            (parent / ".build.info").write_text("Product|Active|Version\nwow_classic|1|5.5.4.70268\n")
            store = Store(root, parent / "backups")
            self.assertEqual(store.addons["Example"]["variables"]["account"], ["MistsDB"])
            self.assertFalse(store.addons["Example"]["uncertain"])
            (parent / ".build.info").unlink()
            store = Store(root, parent / "backups")
            self.assertTrue(store.addons["Example"]["uncertain"])
            self.assertEqual(store.addons["Example"]["variables"]["account"], ["FallbackDB", "MistsDB", "RetailDB"])

    def test_legacy_toc_aliases_are_fallbacks_after_canonical_names(self):
        paths = [p.name for p in toc_candidates(Path("Example"), "TBC")]
        self.assertEqual(paths, ["Example_TBC.toc", "Example-TBC.toc", "Example_BCC.toc", "Example-BCC.toc", "Example.toc"])


class PackageTests(unittest.TestCase):
    def test_validator_rejects_missing_interfaces_and_altered_runtime(self):
        with tempfile.TemporaryDirectory(prefix="svc-contract-") as temporary:
            directory = Path(temporary)
            original = build(directory / "original.zip", version="v1.2.3")
            for filename in ("SVCleaner/SVCleaner.toc", "SVCleaner/Requests.lua"):
                with self.subTest(filename=filename):
                    altered = directory / "altered.zip"
                    with ZipFile(original) as source, ZipFile(altered, "w") as target:
                        for name in source.namelist():
                            content = source.read(name)
                            if name == filename:
                                content = content.replace(b", 38001, 38002", b"") if name.endswith(".toc") else content + b"\n-- unexpected change\n"
                            target.writestr(name, content)
                    with self.assertRaises(ValueError):
                        verify(altered, version="v1.2.3")

    def test_sync_backs_up_and_retires_legacy_tocs_preserving_manifest(self):
        from sync_addon import sync
        with tempfile.TemporaryDirectory(prefix="svc-sync-") as temporary:
            directory = Path(temporary)
            client = directory / "_retail_"
            addons = client / "Interface" / "AddOns"
            with ZipFile(build(directory / "addon.zip")) as archive:
                archive.extractall(addons)
            target = addons / "SVCleaner"
            manifest = b"-- installation-specific manifest\n"
            (target / "Manifest.lua").write_bytes(manifest)
            for name in LEGACY_TOC_NAMES:
                (target / name).write_text("old client module order", encoding="utf-8")
            with patch("sync_addon.ROOT", directory):
                report = sync(client)
            self.assertEqual(set(report["removed"]), set(LEGACY_TOC_NAMES))
            self.assertEqual([p.name for p in target.glob("*.toc")], ["SVCleaner.toc"])
            self.assertEqual((target / "Manifest.lua").read_bytes(), manifest)
            with ZipFile(report["backup"]) as backup:
                for name in LEGACY_TOC_NAMES:
                    self.assertEqual(backup.read("SVCleaner/" + name), b"old client module order")
            self.assertEqual({p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file()}, {runtime_name(p) for p in runtime_files()})

    def test_release_version_and_distribution_ids_in_every_toc(self):
        with tempfile.TemporaryDirectory(prefix="svc-release-") as temporary:
            archive_path = build(Path(temporary) / "addon.zip", version="v1.2.3-beta.1")
            verify(archive_path, version="v1.2.3-beta.1")
            with self.assertRaises(ValueError):
                verify(archive_path, version="v1.2.4")

    def test_validator_rejects_private_files_and_missing_runtime_files(self):
        with tempfile.TemporaryDirectory(prefix="svc-reject-") as temporary:
            archive_path = build(Path(temporary) / "addon.zip")
            with ZipFile(archive_path, "a") as archive:
                archive.writestr("SVCleaner/data/private.original", "must not ship")
            with self.assertRaises(ValueError):
                verify(archive_path)
            missing = Path(temporary) / "missing.zip"
            with ZipFile(missing, "w") as archive:
                archive.writestr("SVCleaner/SVCleaner.toc", "incomplete")
            with self.assertRaises(ValueError):
                verify(missing)
            empty = Path(temporary) / "empty.zip"
            with ZipFile(empty, "w") as archive:
                archive.writestr("SVCleaner/", "")
            with self.assertRaises(ValueError):
                verify(empty)

    def test_validator_accepts_generated_changelog(self):
        with tempfile.TemporaryDirectory(prefix="svc-changelog-") as temporary:
            archive_path = build(Path(temporary) / "addon.zip", version="v1.2.3")
            with ZipFile(archive_path, "a") as archive:
                archive.writestr("SVCleaner/CHANGELOG.md", "# v1.2.3\n\nRelease fixes.\n")
            verify(archive_path, version="v1.2.3")

    def test_companion_source_runs_and_installs_from_another_working_directory(self):
        with tempfile.TemporaryDirectory(prefix="svc-companion-") as temporary:
            directory = Path(temporary)
            project = directory / "source"
            shutil.copytree(ADDON, project / "addon")
            shutil.copytree(ROOT / "companion", project / "companion", ignore=shutil.ignore_patterns("__pycache__"))
            (project / "tools").mkdir()
            shutil.copy2(ROOT / "tools" / "package_addon.py", project / "tools" / "package_addon.py")
            for name in ("LICENSE", "NOTICE"):
                shutil.copy2(ROOT / name, project / name)
            # A fresh process must resolve every import inside the source tree,
            # rather than borrowing modules from this test suite's sys.path.
            root = directory / "wow" / "_retail_"
            (root / "Interface" / "AddOns").mkdir(parents=True)
            command = [sys.executable, str(project / "companion" / "app.py"), "--wow", str(root)]
            subprocess.run(command + ["--scan"], cwd=directory, capture_output=True, text=True, check=True, timeout=30)
            manifest = subprocess.run(command + ["--manifest"], cwd=directory, capture_output=True, text=True, check=True, timeout=30)
            self.assertEqual(Path(json.loads(manifest.stdout)["path"]).resolve(), (project / "addon" / "Manifest.lua").resolve())
            self.assertFalse((project / "Manifest.lua").exists())
            # Isolate the synthetic install from game clients on the developer's PC.
            # Production process guards are exercised separately in test_service.
            driver = "import sys, runpy; from pathlib import Path; from unittest.mock import patch; app = sys.argv[1]; sys.path.insert(0, str(Path(app).parent)); sys.argv = sys.argv[1:]; guard = patch('service.check_game_closed'); guard.start(); runpy.run_path(app, run_name='__main__')"
            subprocess.run([sys.executable, "-c", driver] + command[1:] + ["--install-addon"], cwd=directory, capture_output=True, text=True, check=True, timeout=30)
            installed = root / "Interface" / "AddOns" / "SVCleaner"
            self.assertIn("## Version: dev", (installed / "SVCleaner.toc").read_text(encoding="utf-8"))
            self.assertEqual({p.relative_to(installed).as_posix() for p in installed.rglob("*") if p.is_file()}, {runtime_name(p) for p in runtime_files()})

    def test_frozen_paths_keep_resources_and_persistent_data_separate(self):
        with tempfile.TemporaryDirectory(prefix="svc-paths-") as temporary:
            home = Path(temporary)
            resources = home / "_internal"
            with patch.object(sys, "frozen", True, create=True), patch.object(sys, "_MEIPASS", str(resources), create=True), patch.object(sys, "executable", str(home / "SVCleaner.exe")):
                runtime = runpy.run_path(str(ROOT / "companion" / "runtime.py"))
            self.assertEqual(runtime["PROJECT"], resources)
            # Windows runners may expose TEMP through an 8.3 alias (RUNNER~1).
            # The executable's resolved location uses the full directory name.
            self.assertEqual(runtime["HOME"], home.resolve())
            self.assertEqual(runtime["DATA"], home.resolve() / "data")

    def test_portable_remembers_valid_wow_path_and_ignores_corrupt_settings(self):
        from app import preferred_wow
        with tempfile.TemporaryDirectory(prefix="svc-settings-") as temporary:
            home = Path(temporary)
            root = home / "_classic_era_"
            (root / "Interface" / "AddOns").mkdir(parents=True)
            settings = home / "wow-path.txt"
            with patch("app.FROZEN", True), patch("app.HOME", home), patch("app.DEFAULT_WOW", home / "default"):
                settings.write_text(str(root), encoding="utf-8")
                self.assertEqual(preferred_wow(), root)
                settings.write_bytes(b"\xff")
                self.assertIsNone(preferred_wow())

    def test_portable_first_launch_saves_picker_choice_and_starts_server(self):
        from app import main
        with tempfile.TemporaryDirectory(prefix="svc-first-run-") as temporary:
            home = Path(temporary)
            root = home / "_retail_"
            (root / "Interface" / "AddOns").mkdir(parents=True)
            server = MagicMock(server_port=12345)
            server.serve_forever.side_effect = KeyboardInterrupt
            with patch("app.FROZEN", True), patch("app.HOME", home), patch("app.preferred_wow", return_value=home / "missing"), patch("app.choose_wow", return_value=root) as picker, patch("app.Store") as store, patch("app.create_server", return_value=server), patch("app.threading.Timer"), patch.object(sys, "argv", ["SVCleaner.exe"]):
                main()
            picker.assert_called_once()
            store.assert_called_once_with(root)
            self.assertEqual((home / "wow-path.txt").read_text(encoding="utf-8"), str(root))
            server.server_close.assert_called_once()

    def test_portable_first_launch_cancellation_exits_without_server(self):
        from app import main
        with tempfile.TemporaryDirectory(prefix="svc-cancel-") as temporary:
            home = Path(temporary)
            with patch("app.FROZEN", True), patch("app.HOME", home), patch("app.preferred_wow", return_value=home / "missing"), patch("app.choose_wow", return_value=None), patch("app.Store") as store, patch.object(sys, "argv", ["SVCleaner.exe"]):
                main()
            store.assert_not_called()
            self.assertFalse((home / "wow-path.txt").exists())

    def test_frozen_installer_uses_versioned_bundled_files(self):
        from app import install
        with tempfile.TemporaryDirectory(prefix="svc-frozen-install-") as temporary:
            directory = Path(temporary)
            resources = directory / "_internal"
            with ZipFile(build(directory / "addon.zip", version="v1.2.3")) as archive:
                archive.extractall(resources)
            (resources / "SVCleaner").rename(resources / "addon")
            root = directory / "_retail_"
            (root / "Interface" / "AddOns").mkdir(parents=True)
            store = Store(root, directory / "data")
            with patch("app.FROZEN", True), patch("app.PROJECT", resources), patch("app.check_game_closed"):
                install(store)
            installed = root / "Interface" / "AddOns" / "SVCleaner"
            for toc in installed.glob("*.toc"):
                self.assertIn("## Version: v1.2.3", toc.read_text(encoding="utf-8"))
            self.assertIn("SVC.Manifest", (installed / "Manifest.lua").read_text())
            self.assertEqual({p.relative_to(installed).as_posix() for p in installed.rglob("*") if p.is_file()}, {runtime_name(p) for p in runtime_files()})

    def test_archive_contains_only_runtime_and_one_multi_client_toc(self):
        with tempfile.TemporaryDirectory(prefix="svc-package-") as temporary:
            with ZipFile(build(Path(temporary) / "addon.zip")) as archive:
                expected = {"SVCleaner/" + runtime_name(path) for path in runtime_files()}
                self.assertEqual(set(archive.namelist()), expected)
                for name in archive.namelist():
                    if name.endswith(".toc"):
                        toc = archive.read(name).decode("utf-8")
                        modules = [line for line in toc.splitlines() if line and not line.startswith("#")]
                        locales = ["locales/" + language + ".lua" for language in ("enUS", "frFR", "deDE", "esES", "itIT", "ptBR", "ruRU", "koKR", "zhCN", "zhTW", "esMX")]
                        self.assertEqual(modules, ["Compat.lua"] + locales + ["Locale.lua", "Manifest.lua", "Data.lua", "Database.lua", "Discovery.lua", "CVars.lua", "Requests.lua", "Minimap.lua", "Core.lua", "Widgets.lua", "Compare.lua", "UI.lua"])
                        for module in modules:
                            self.assertIn("SVCleaner/" + module, expected)
                        self.assertIn("## SavedVariables: SVCleanerDB", toc)
                        self.assertIn("Assets\\logo.tga", toc)
                self.assertEqual([name for name in archive.namelist() if name.endswith(".toc")], ["SVCleaner/SVCleaner.toc"])

    def test_install_copies_only_runtime_and_generates_client_manifest(self):
        from app import install
        with tempfile.TemporaryDirectory(prefix="svc-install-") as temporary:
            root = Path(temporary) / "_retail_"
            (root / "Interface" / "AddOns").mkdir(parents=True)
            store = Store(root, Path(temporary) / "backups")
            with patch("app.check_game_closed"):
                install(store)
            target = root / "Interface" / "AddOns" / "SVCleaner"
            expected = {runtime_name(path) for path in runtime_files()}
            self.assertEqual({p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file()}, expected)
            self.assertIn("SVC.Manifest", (target / "Manifest.lua").read_text())
            for toc in target.glob("*.toc"):
                self.assertNotIn("@project-version@", toc.read_text(encoding="utf-8"))

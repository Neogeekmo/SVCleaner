"""Exercise client selection and the real archive contract without touching WoW."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "companion"))
sys.path.insert(0, str(ROOT / "tools"))
from flavors import detect_client, toc_candidates
from package_addon import build, flavor_tocs, runtime_files
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
    def test_archive_contains_only_runtime_and_all_flavor_tocs(self):
        with tempfile.TemporaryDirectory(prefix="svc-package-") as temporary:
            with ZipFile(build(Path(temporary) / "addon.zip")) as archive:
                expected = {"SVCleaner/" + path.relative_to(ROOT).as_posix() for path in runtime_files()}
                expected.update("SVCleaner/" + name for name in flavor_tocs())
                self.assertEqual(set(archive.namelist()), expected)
                for name in archive.namelist():
                    if name.endswith(".toc"):
                        toc = archive.read(name).decode("utf-8")
                        modules = [line for line in toc.splitlines() if line and not line.startswith("#")]
                        self.assertEqual(modules, ["Compat.lua", "Locale.lua", "Manifest.lua", "Core.lua", "Widgets.lua", "Compare.lua", "UI.lua"])
                        for module in modules:
                            self.assertIn("SVCleaner/" + module, expected)
                        self.assertIn("## SavedVariables: SVCleanerDB", toc)
                        self.assertIn("Assets\\logo.tga", toc)
                self.assertEqual(len(flavor_tocs()), 7)

    def test_install_copies_only_runtime_and_generates_client_manifest(self):
        from app import install
        with tempfile.TemporaryDirectory(prefix="svc-install-") as temporary:
            root = Path(temporary) / "_retail_"
            (root / "Interface" / "AddOns").mkdir(parents=True)
            store = Store(root, Path(temporary) / "backups")
            with patch("app.check_game_closed"):
                install(store)
            target = root / "Interface" / "AddOns" / "SVCleaner"
            expected = {path.relative_to(ROOT).as_posix() for path in runtime_files()} | set(flavor_tocs())
            self.assertEqual({p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file()}, expected)
            self.assertIn("SVC.Manifest", (target / "Manifest.lua").read_text())

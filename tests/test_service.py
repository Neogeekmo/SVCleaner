import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "companion"))
from app import create_server
from lua_data import DataError, at, parse, token
from service import Store, check_game_closed


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="svc-tests-")
        self.root = Path(self.temp.name) / "_retail_"
        self.sv = self.root / "WTF" / "Account" / "TEST" / "SavedVariables"
        self.sv.mkdir(parents=True)
        folder = self.root / "Interface" / "AddOns" / "APR"
        folder.mkdir(parents=True)
        (folder / "APR.toc").write_text('## Title: APR\n## SavedVariables: APRData\n## SavedVariablesPerCharacter: APRChar\n')
        self.original = b'APRData = { ["A-Player-1-AAA"] = { GUID = "Player-1-AAA", route = { step = 42, enabled = false }, onlyA = 7 }, ["B-Player-1-BBB"] = { GUID = "Player-1-BBB", route = { step = 16, enabled = true }, onlyB = 8 } }\n'
        (self.sv / "APR.lua").write_bytes(self.original)
        (self.sv / "Removed.lua").write_text('OldDB = { a = 3 }')
        (self.sv / "Removed.lua.bak").write_text('OldDB = { a = 2 }')
        (self.sv / "Renamed.lua").write_text('APRData = { a = 4 }')
        char = self.root / "WTF" / "Account" / "TEST" / "Realm" / "A" / "SavedVariables"
        char.mkdir(parents=True)
        (char / "APR.lua").write_text('APRChar = { scale = 1 }')
        self.store = Store(self.root, Path(self.temp.name) / "backups")
        self.record_id = next(r["id"] for r in self.store.records.values() if r["addon"] == "APR" and r["scope"] == "account")
        self.left = [token("APRData"), token("A-Player-1-AAA")]
        self.right = [token("APRData"), token("B-Player-1-BBB")]
        self.closed = patch("service.check_game_closed")
        self.closed.start()

    def tearDown(self):
        self.closed.stop()
        self.temp.cleanup()

    def stage_step(self, value=99):
        self.store.stage({"id": self.record_id, "path": self.left + [token("route"), token("step")], "operation": "edit", "value": value})

    def test_compare_picker_preserves_paths_and_names_characters(self):
        result=self.store.comparison_options(self.record_id)
        left=next(o for o in result["options"] if o["path"]==self.left)
        self.assertEqual(left["label"],"A")
        self.assertEqual(left["path"][1]["value"],"A-Player-1-AAA")

    def test_comparison_preview_rejects_changed_values_and_bad_direction(self):
        request={"leftId":self.record_id,"rightId":self.record_id,"leftPath":self.left,"rightPath":self.right}
        preview=self.store.compare(request)
        self.assertEqual(next(r["reason"] for r in preview["rows"] if r["path"]==[token("GUID")]),"identity")
        self.stage_step(55)
        with self.assertRaisesRegex(DataError,"changé"):
            self.store.transfer({**request,"direction":"right","expectedSignature":preview["signature"]})
        with self.assertRaisesRegex(DataError,"Sens"):
            self.store.transfer({**request,"direction":"invalid"})
        self.assertEqual((self.sv/"APR.lua").read_bytes(),self.original)

    def test_direct_identity_comparison_disables_copy_actions(self):
        request={"leftId":self.record_id,"rightId":self.record_id,"leftPath":self.left+[token("GUID")],"rightPath":self.right+[token("GUID")]}
        row=self.store.compare(request)["rows"][0]
        self.assertEqual(row["reason"],"identity")
        self.assertFalse(row["toLeft"] or row["toRight"])

    def test_inventory_orphans_renamed_backups_and_character_scopes(self):
        records = list(self.store.records.values())
        self.assertEqual(next(r["status"] for r in records if r["addon"] == "Removed" and not r["backup"]), "orphan")
        self.assertEqual(next(r["status"] for r in records if r["addon"] == "Renamed"), "linked")
        self.assertEqual(sum(r["backup"] for r in records), 1)
        self.assertEqual(self.store.characters[0]["label"], "A - Realm")
        self.assertEqual(len(records), 5)

    def test_staging_is_in_memory_and_discard_restores_view(self):
        self.stage_step()
        self.assertEqual((self.sv / "APR.lua").read_bytes(), self.original)
        self.assertEqual(at(self.store.load(self.record_id), self.left + [token("route"), token("step")]), 99)
        self.store.discard()
        self.assertEqual(at(self.store.load(self.record_id), self.left + [token("route"), token("step")]), 42)

    def test_apply_and_byte_exact_restore(self):
        self.stage_step()
        result = self.store.apply()
        self.assertNotEqual((self.sv / "APR.lua").read_bytes(), self.original)
        self.assertEqual(result["transaction"]["status"], "applied")
        self.store.restore(result["transaction"]["id"])
        self.assertEqual((self.sv / "APR.lua").read_bytes(), self.original)

    def test_refuses_changed_files_on_apply(self):
        self.stage_step()
        changed = self.original + b'Other = 1\n'
        (self.sv / "APR.lua").write_bytes(changed)
        with self.assertRaises(DataError):
            self.store.apply()
        self.assertEqual((self.sv / "APR.lua").read_bytes(), changed)

    def test_refuses_changed_files_on_restore(self):
        self.stage_step()
        tx = self.store.apply()["transaction"]
        (self.sv / "APR.lua").write_bytes(b'APRData = {}')
        with self.assertRaises(DataError):
            self.store.restore(tx["id"])
        self.assertEqual((self.sv / "APR.lua").read_bytes(), b'APRData = {}')

    def test_file_and_bak_quarantine_restore(self):
        records = [r for r in self.store.records.values() if r["addon"] == "Removed"]
        originals = {r["path"]: (self.root / r["path"]).read_bytes() for r in records}
        for r in records:
            self.store.stage({"id": r["id"], "operation": "delete-file"})
        tx = self.store.apply()["transaction"]
        self.assertFalse((self.sv / "Removed.lua").exists())
        self.assertFalse((self.sv / "Removed.lua.bak").exists())
        self.store.restore(tx["id"])
        for path, original in originals.items():
            self.assertEqual((self.root / path).read_bytes(), original)

    def test_identity_and_ancestor_protection(self):
        for operation in ("edit", "delete-value"):
            with self.assertRaises(DataError):
                self.store.stage({"id": self.record_id, "path": self.left + [token("GUID")], "operation": operation, "value": "Player-1-CCC"})

    def test_same_file_merge_keeps_parent_ids_and_keys(self):
        request = {"leftId": self.record_id, "rightId": self.record_id, "leftPath": self.left, "rightPath": self.right, "direction": "right"}
        result = self.store.transfer(request)
        self.assertEqual(result["changed"], 2)
        roots = self.store.load(self.record_id)
        target = at(roots, self.right)
        self.assertEqual(target.get("GUID"), "Player-1-BBB")
        self.assertEqual(target.get("route").get("step"), 42)
        self.assertEqual(target.get("onlyB"), 8)
        self.assertFalse(target.has("onlyA"))
        self.assertTrue(roots.get("APRData").has("B-Player-1-BBB"))

    def test_copy_missing_key_or_identity_is_rejected(self):
        request = {"leftId": self.record_id, "rightId": self.record_id, "leftPath": self.left, "rightPath": self.right, "direction": "right"}
        for relative in ([token("GUID")], [token("onlyA")]):
            with self.assertRaises(DataError):
                self.store.transfer({**request, "relativePath": relative})

    def test_cache_rename_restore_and_refuse_regenerated(self):
        cache = self.root / "Cache"
        cache.mkdir()
        (cache / "example.wdb").write_bytes(b"cache")
        result = self.store.reset_cache()
        tx = result["history"][0]
        self.assertFalse(cache.exists())
        cache.mkdir()
        with self.assertRaises(DataError):
            self.store.restore(tx["id"])
        cache.rmdir()
        self.store.restore(tx["id"])
        self.assertEqual((cache / "example.wdb").read_bytes(), b"cache")

    def test_gpu_cache_is_separate_and_restorable(self):
        cache = self.root / "GPUCache"
        cache.mkdir()
        (cache / "index").write_bytes(b"gpu")
        info = self.store.cache_info()
        self.assertEqual(info["locations"][1]["path"], "GPUCache")
        self.assertEqual(info["locations"][1]["bytes"], 3)
        tx = self.store.reset_cache("GPUCache")["history"][0]
        self.assertFalse(cache.exists())
        self.store.restore(tx["id"])
        self.assertEqual((cache / "index").read_bytes(), b"gpu")
        with self.assertRaises(DataError):
            self.store.reset_cache("Data")

    def test_bulk_delete_includes_baks_and_restores_every_original(self):
        records = list(self.store.records.values())
        originals = {record["path"]: (self.root / record["path"]).read_bytes() for record in records}
        result = self.store.stage_delete_files([record["id"] for record in records] + [records[0]["id"]])
        self.assertEqual(result["staged"], len(records))
        self.assertEqual(len(self.store.pending), len(records))
        for path, original in originals.items():
            self.assertEqual((self.root / path).read_bytes(), original)
        tx = self.store.apply()["transaction"]
        self.assertEqual(len(tx["files"]), len(records))
        for path in originals:
            self.assertFalse((self.root / path).exists())
        self.store.restore(tx["id"])
        for path, original in originals.items():
            self.assertEqual((self.root / path).read_bytes(), original)

    def test_bulk_delete_validates_all_ids_before_touching_basket(self):
        self.stage_step()
        before = dict(self.store.pending)
        with self.assertRaises(DataError):
            self.store.stage_delete_files([self.record_id, "unknown-file"])
        self.assertEqual(self.store.pending, before)
        (self.sv / "SVCleaner.lua").write_text("SVCleanerDB = {}")
        self.store.discard()
        self.store.scan()
        protected = next(record for record in self.store.records.values() if record["addon"] == "SVCleaner")
        with self.assertRaises(DataError):
            self.store.stage_delete_files([self.record_id, protected["id"]])
        self.assertEqual(self.store.pending, {})
        self.assertEqual((self.sv / "APR.lua").read_bytes(), self.original)

    def test_bulk_delete_rejects_empty_or_malformed_selection(self):
        for ids in (None, [], "all", [3], [self.record_id] * 10001):
            with self.subTest(ids=type(ids).__name__), self.assertRaises(DataError):
                self.store.stage_delete_files(ids)

    def test_bulk_rolls_back_if_game_starts_before_completion(self):
        originals = {record["path"]: (self.root / record["path"]).read_bytes() for record in self.store.records.values()}
        self.store.stage_delete_files(list(self.store.records))
        with patch("service.check_game_closed", side_effect=[None, None, DataError("WoW started")]), patch("service.time.monotonic", return_value=0), self.assertRaises(DataError):
            self.store.apply()
        for path, original in originals.items():
            self.assertEqual((self.root / path).read_bytes(), original)
        self.assertEqual(self.store.history()[0]["status"], "failed")

    def test_interrupted_transaction_can_be_rolled_back(self):
        self.stage_step()
        tx = self.store.apply()["transaction"]
        journal = self.store.data_dir / tx["id"] / "transaction.json"
        tx["status"] = "prepared"
        journal.write_text(json.dumps(tx), encoding="utf-8")
        self.store.restore(tx["id"])
        self.assertEqual((self.sv / "APR.lua").read_bytes(), self.original)

    def test_version_switch_isolates_inventory_and_blocks_pending_changes(self):
        classic = self.root.parent / "_classic_era_"
        (classic / "Interface" / "AddOns").mkdir(parents=True)
        server = create_server(self.store)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with urlopen(base + "/api/state") as response:
                state = json.load(response)
            classic_version = next(item for item in state["versions"] if item["folder"] == "_classic_era_")
            self.assertTrue(classic_version["available"])
            def change(version_id):
                request = Request(base + "/api/version", data=json.dumps({"id": version_id}).encode(), headers={"Content-Type": "application/json", "X-SVC-Token": state["csrf"]})
                with urlopen(request) as response:
                    return json.load(response)
            self.stage_step()
            with self.assertRaises(HTTPError) as error:
                change(classic_version["id"])
            self.assertEqual(error.exception.code, 400)
            error.exception.close()
            self.store.discard()
            switched = change(classic_version["id"])
            self.assertEqual(switched["root"], str(classic.resolve()))
            self.assertEqual(switched["stats"]["files"], 0)
            with self.assertRaises(HTTPError) as error:
                change("../../Data")
            error.exception.close()
            original_version = next(item for item in state["versions"] if item["folder"] == "_retail_")
            restored = change(original_version["id"])
            self.assertEqual(restored["stats"]["files"], state["stats"]["files"])
        finally:
            server.shutdown()
            server.server_close()

    def test_rollback_when_second_write_fails(self):
        self.stage_step()
        removed = next(r for r in self.store.records.values() if r["addon"] == "Removed" and not r["backup"])
        self.store.stage({"id": removed["id"], "path": [token("OldDB"), token("a")], "operation": "edit", "value": 9})
        real_write = self.store.atomic_write
        calls = 0
        def write(target, data):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated disk failure")
            real_write(target, data)
        with patch.object(self.store, "atomic_write", side_effect=write), self.assertRaises(OSError):
            self.store.apply()
        self.assertEqual((self.sv / "APR.lua").read_bytes(), self.original)
        self.assertEqual((self.sv / "Removed.lua").read_text(), 'OldDB = { a = 3 }')
        self.assertEqual(self.store.history()[0]["status"], "failed")

    def test_import_false_expected_value(self):
        (self.sv / "SVCleaner.lua").write_text('SVCleanerDB = { requests = { { addon = "APR", root = "APRData", scope = "account", operation = "edit", value = true, expectedType = "boolean", expectedValue = false, path = { { type = "string", value = "A-Player-1-AAA" }, { type = "string", value = "route" }, { type = "string", value = "enabled" } } } } }')
        self.store.scan()
        result = self.store.import_requests()
        self.assertEqual(result["imported"], 1)
        self.assertEqual(result["skipped"], [])
        self.assertTrue(at(self.store.load(self.record_id), self.left + [token("route"), token("enabled")]))

    def test_bak_edit_rejected(self):
        r = next(r for r in self.store.records.values() if r["backup"])
        with self.assertRaises(DataError):
            self.store.stage({"id": r["id"], "path": [token("OldDB"), token("a")], "operation": "edit", "value": 1})

    def test_running_game_blocks_writes(self):
        self.stage_step()
        with patch("service.check_game_closed", side_effect=DataError("running")), self.assertRaises(DataError):
            self.store.apply()
        self.assertEqual((self.sv / "APR.lua").read_bytes(), self.original)

    def test_unknown_record_and_path_traversal(self):
        with self.assertRaises(DataError):
            self.store.record("../../secret")
        with self.assertRaises(DataError):
            self.store.restore("../../secret")

    def test_local_http_requires_token_and_correct_host(self):
        server = create_server(self.store)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            state = json.load(urlopen(base + "/api/state"))
            request = Request(base + "/api/discard", data=b"{}", headers={"Content-Type": "application/json"})
            with self.assertRaises(HTTPError) as context:
                urlopen(request)
            self.assertEqual(context.exception.code, 403)
            request.add_header("X-SVC-Token", state["csrf"])
            self.assertEqual(urlopen(request).status, 200)
            request.add_header("Origin", "http://evil.example")
            with self.assertRaises(HTTPError):
                urlopen(request)
            request = Request(base + "/api/state", headers={"Host": "evil.example"})
            with self.assertRaises(HTTPError):
                urlopen(request)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()

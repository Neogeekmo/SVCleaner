"""Catalog completeness and HTTP language isolation without touching real WoW."""
import ast
import json
import re
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "companion"))
from app import create_server
from i18n import CATALOGS, LANGUAGES, Message, encoder, message, normalize
from service import Store


class CompanionCatalogTests(unittest.TestCase):
    def test_all_wow_languages_have_complete_catalogs_and_matching_parameters(self):
        self.assertEqual(set(CATALOGS), set(LANGUAGES))
        self.assertEqual(set(CATALOGS), {"enUS", "frFR", "deDE", "esES", "esMX", "itIT", "ptBR", "ruRU", "koKR", "zhCN", "zhTW"})
        keys = set(CATALOGS["frFR"])
        for language, catalog in CATALOGS.items():
            self.assertEqual(set(catalog), keys, language)
            for key, text in catalog.items():
                self.assertTrue(text.strip(), (language, key))
                self.assertEqual(set(re.findall(r"\{(\w+)\}", text)), set(re.findall(r"\{(\w+)\}", key)), (language, key))

    def test_static_html_and_server_messages_exist_in_every_catalog(self):
        required = set(re.findall(r'data-i18n(?:-[a-z-]+)?="([^"]+)"', (ROOT / "companion/web/index.html").read_text(encoding="utf-8-sig")))
        for path in (ROOT / "companion").glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if not isinstance(node, ast.Call):
                    continue
                name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ""
                if name in ("DataError", "message", "Message", "tr", "error") and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    required.add(node.args[0].value)
        self.assertFalse(required - set(CATALOGS["enUS"]), required - set(CATALOGS["enUS"]))

    def test_browser_and_wow_locale_aliases(self):
        for value, expected in {"enGB": "enUS", "ptPT": "ptBR", "fr-CA": "frFR", "es-AR": "esMX", "es-MX": "esMX", "zh-Hant": "zhTW", "zh-HK": "zhTW", "zh-CN": "zhCN", "ko-KR": "koKR", "de-DE,de;q=0.9": "deDE", "unknown": "enUS"}.items():
            self.assertEqual(normalize(value), expected, value)

    def test_messages_translate_only_templates_and_preserve_user_values(self):
        value = "Vue d’ensemble <script> {count} 玩家"
        text = message("Copier vers {target}", target=value).render("zhTW")
        self.assertIn(value, text)
        self.assertTrue(text.startswith("複製至"))
        nested = message("{message} (ligne {line})", message=message("Clé invalide"), line=7)
        self.assertEqual(nested.render("enUS"), "Invalid key (line 7)")
        self.assertEqual(message("not-a-key").render("unknown"), "not-a-key")


class CompanionLanguageHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="svc-i18n-")
        self.directory = Path(self.temporary.name)
        self.root = self.directory / "_retail_"
        addon = self.root / "Interface/AddOns/Example"
        addon.mkdir(parents=True)
        (addon / "Example.toc").write_text("## SavedVariables: DB\n", encoding="utf-8")
        saved = self.root / "WTF/Account/TEST/SavedVariables/Example.lua"
        saved.parent.mkdir(parents=True)
        saved.write_text('DB = { ["Sauvegardes"] = "Vue d’ensemble", n = 2, nested = {}, left = { v = 1, blocked = {} }, right = { v = 2, blocked = 1 } }', encoding="utf-8")
        self.store = Store(self.root, self.directory / "data" / "test")
        self.record = next(iter(self.store.records))
        self.start_server()

    def start_server(self):
        self.server = create_server(self.store)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.csrf = self.request("/api/state")["csrf"]

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def tearDown(self):
        self.stop_server()
        self.temporary.cleanup()

    def request(self, path, language="enUS", body=None, token=True):
        headers = {"X-SVC-Language": language}
        if token:
            headers["X-SVC-Token"] = getattr(self, "csrf", "")
        data = None if body is None else json.dumps(body).encode()
        request = Request(self.base + path, data, headers)
        with urlopen(request, timeout=5) as response:
            return json.load(response)

    def test_all_languages_localize_errors_without_global_language_leaks(self):
        for language, catalog in CATALOGS.items():
            with self.subTest(language=language):
                try:
                    self.request("/api/stage", language, {"id": "unknown", "operation": "delete-file"})
                    self.fail("Unknown files must be refused")
                except HTTPError as error:
                    with error:
                        self.assertEqual(error.code, 400)
                        self.assertEqual(json.load(error)["error"], catalog["Fichier inconnu ; rescannez"])
        self.assertEqual(self.request("/api/language")["language"], None)

    def test_language_persists_across_server_restart_and_rejects_invalid_updates(self):
        try:
            self.request("/api/language", "deDE", {"language": "deDE"}, token=False)
            self.fail("Language changes require the CSRF token")
        except HTTPError as error:
            with error:
                self.assertEqual(error.code, 403)
        self.request("/api/language", body={"language": "zhTW"})
        self.stop_server()
        self.start_server()
        self.assertEqual(self.request("/api/language")["language"], "zhTW")
        try:
            self.request("/api/language", body={"language": "../../outside"})
            self.fail("Unsupported languages must be rejected")
        except HTTPError as error:
            with error:
                self.assertEqual(error.code, 400)
        self.assertEqual(self.request("/api/language")["language"], "zhTW")

    def test_pending_changes_and_user_data_survive_language_changes(self):
        self.request("/api/stage", "frFR", {"id": self.record, "path": [{"type": "string", "value": "DB"}, {"type": "string", "value": "n"}], "operation": "edit", "value": 3})
        original_pending = dict(self.store.pending)
        for language in LANGUAGES:
            response = self.request("/api/state", language)
            self.assertEqual(len(response["pending"]), 1)
            self.assertEqual(response["pending"][0]["summary"], CATALOGS[language]["Modifier les données sélectionnées"])
            path = [{"type": "string", "value": "DB"}]
            from urllib.parse import urlencode
            result = self.request("/api/browse?" + urlencode({"id": self.record, "path": json.dumps(path)}), language)
            user = next(item for item in result["items"] if item["key"]["value"] == "Sauvegardes")
            self.assertEqual(user["value"], "Vue d’ensemble")
            table = next(item for item in result["items"] if item["key"]["value"] == "nested")
            self.assertEqual(table["value"], message("{ {count} clés }", count=0).render(language))
        self.assertEqual(self.store.pending, original_pending)
        self.assertIsInstance(next(iter(self.store.pending.values()))["summary"], Message)
        self.assertIn("summary", json.dumps(self.store.state(), default=encoder("enUS")))

    def test_comparison_signature_remains_valid_after_language_change(self):
        def path(key):
            return [{"type": "string", "value": "DB"}, {"type": "string", "value": key}]
        payload = {"leftId": self.record, "rightId": self.record, "leftPath": path("left"), "rightPath": path("right")}
        signatures = {self.request("/api/compare", language, payload)["signature"] for language in LANGUAGES}
        self.assertEqual(len(signatures), 1)
        self.request("/api/language", body={"language": "koKR"})
        response = self.request("/api/transfer", "koKR", {**payload, "direction": "right", "relativePath": [], "expectedSignature": signatures.pop()})
        self.assertEqual(response["changed"], 1)

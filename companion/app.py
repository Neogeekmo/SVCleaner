"""Local-only dashboard. Python standard library; no upload and no Lua execution."""
from __future__ import annotations

import argparse
import json
import secrets
import shutil
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from lua_data import DataError
from service import DEFAULT_WOW, Store, check_game_closed, contained, digest
from runtime import FROZEN, HOME, PROJECT
from i18n import LANGUAGES, encoder, message, normalize, system_language

WEB = PROJECT / "companion" / "web"
VERSION_LABELS = {
    "_retail_": "Retail", "_ptr_": "Retail · PTR", "_xptr_": "Retail · PTR expérimental",
    "_beta_": "Retail · Bêta", "_classic_": "Classic", "_classic_beta_": "Classic · Bêta",
    "_classic_ptr_": "Classic · PTR", "_classic_era_": "Classic Era",
    "_classic_era_ptr_": "Classic Era · PTR", "_classic_era_beta_": "Classic Era · Bêta",
    "_classic_anniversary_": "Classic Anniversary", "_classic_anniversary_ptr_": "Classic Anniversary · PTR",
    "_classic_titan_": "Classic Titan", "_classic_titan_ptr_": "Classic Titan · PTR", "_forever_": "Forever",
}


def discover_versions(current_root):
    current_root = Path(current_root).resolve()
    records = []
    for folder in current_root.parent.iterdir():
        if not folder.is_dir() or folder.is_symlink() or (folder.name not in VERSION_LABELS and folder != current_root):
            continue
        available = (folder / "Interface" / "AddOns").is_dir()
        records.append({"id": digest(str(folder.resolve()).encode())[:20], "label": message(VERSION_LABELS[folder.name]) if folder.name in VERSION_LABELS else folder.name, "folder": folder.name, "root": str(folder.resolve()), "available": available, "reason": "" if available else message("Interface/AddOns absent : lancez cette version une fois")})
    return sorted(records, key=lambda record: (record["folder"] != "_retail_", str(record["label"])))


def create_server(store, port=0, language=None):
    csrf = secrets.token_urlsafe(32)
    initial_root = store.root
    data_parent = store.data_dir.parent
    context = {"store": store}
    context_lock = threading.RLock()
    preferences = data_parent / "preferences.json"

    def saved_language():
        if language:
            return normalize(language)
        try:
            value = json.loads(preferences.read_text(encoding="utf-8"))
            return value.get("language") if isinstance(value, dict) and value.get("language") in LANGUAGES else None
        except (OSError, ValueError):
            return None

    def state_with_versions(active):
        versions = discover_versions(initial_root)
        current = next((item for item in versions if item["root"] == str(active.root)), None)
        return {**active.state(), "versions": versions, "currentVersion": current}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def trusted(self):
            host = self.headers.get("Host", "")
            return host == f"127.0.0.1:{self.server.server_port}"

        def send(self, body, content_type="application/json; charset=utf-8", status=200):
            if not isinstance(body, bytes):
                selected = normalize(self.headers.get("X-SVC-Language") or saved_language() or self.headers.get("Accept-Language"))
                body = json.dumps(body, ensure_ascii=True, allow_nan=False, default=encoder(selected)).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self.trusted():
                self.send({"error": message("Hôte refusé")}, status=403)
                return
            url = urlsplit(self.path)
            try:
                with context_lock:
                    store = context["store"]
                    if url.path == "/api/language":
                        self.send({"language": saved_language(), "languages": LANGUAGES})
                    elif url.path == "/api/state":
                        self.send({**state_with_versions(store), "csrf": csrf})
                    elif url.path == "/api/versions":
                        self.send({"versions": discover_versions(initial_root)})
                    elif url.path == "/api/cache":
                        self.send(store.cache_info())
                    elif url.path == "/api/compare-options":
                        query = parse_qs(url.query)
                        self.send(store.comparison_options(query["id"][0]))
                    elif url.path == "/api/browse":
                        query = parse_qs(url.query)
                        path = json.loads(query.get("path", ["[]"])[0])
                        self.send(store.browse(query["id"][0], path, int(query.get("offset", ["0"])[0])))
                    else:
                        allowed = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"), "/i18n.js": ("i18n.js", "text/javascript; charset=utf-8"), "/locales.json": ("locales.json", "application/json; charset=utf-8"), "/style.css": ("style.css", "text/css; charset=utf-8"), "/logo.svg": ("logo.svg", "image/svg+xml")}
                        if url.path not in allowed:
                            self.send({"error": message("Page inconnue")}, status=404)
                        else:
                            filename, content_type = allowed[url.path]
                            self.send((WEB / filename).read_bytes(), content_type)
            except (DataError, ValueError, KeyError, OSError, TypeError, RecursionError) as error:
                self.send({"error": error.message if isinstance(error, DataError) else message("Erreur locale"), "detail": str(error) if isinstance(error, OSError) else None}, status=400)

        def do_POST(self):
            origin = self.headers.get("Origin")
            if not self.trusted() or self.headers.get("X-SVC-Token") != csrf or (origin and origin != f"http://127.0.0.1:{self.server.server_port}"):
                self.send({"error": message("Requête locale non autorisée")}, status=403)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 1024 * 1024:
                    raise DataError("Requête trop volumineuse")
                request = json.loads(self.rfile.read(length))
                path = urlsplit(self.path).path
                with context_lock:
                    store = context["store"]
                    if path == "/api/language":
                        selected = request.get("language")
                        if selected not in LANGUAGES:
                            raise DataError("Langue non prise en charge")
                        Store.atomic_write(preferences, json.dumps({"language": selected}).encode())
                        result = {"language": selected}
                    elif path == "/api/version":
                        if store.pending:
                            raise DataError("Appliquez ou abandonnez le panier avant de changer de version WoW")
                        selected = next((item for item in discover_versions(initial_root) if item["id"] == request.get("id") and item["available"]), None)
                        if selected is None:
                            raise DataError("Version WoW non détectée ou indisponible")
                        root = Path(selected["root"])
                        active = Store(root, data_parent / digest(str(root).encode())[:12])
                        context["store"] = active
                        result = state_with_versions(active)
                    elif path == "/api/scan": result = store.scan()
                    elif path == "/api/stage": result = store.stage(request)
                    elif path == "/api/delete-files": result = store.stage_delete_files(request.get("ids"))
                    elif path == "/api/compare": result = store.compare(request)
                    elif path == "/api/transfer": result = store.transfer(request)
                    elif path == "/api/discard": result = store.discard()
                    elif path == "/api/apply": result = store.apply()
                    elif path == "/api/restore": result = store.restore(request["id"])
                    elif path == "/api/import": result = store.import_requests()
                    elif path == "/api/manifest": result = store.manifest()
                    elif path == "/api/cache-reset": result = store.reset_cache(request.get("location", "Cache"))
                    else: raise DataError("Opération inconnue")
                self.send(result)
            except (DataError, ValueError, KeyError, OSError, TypeError, RecursionError) as error:
                self.send({"error": error.message if isinstance(error, DataError) else message("Erreur locale"), "detail": str(error) if isinstance(error, OSError) else None}, status=400)

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server


def install(store, language=None):
    check_game_closed()
    target = contained(store.root / "Interface" / "AddOns" / "SVCleaner", store.root)
    if target.exists():
        raise DataError("SVCleaner est déjà installé ; synchronisez les fichiers avec votre outil habituel")
    if FROZEN:
        shutil.copytree(PROJECT / "addon", target)
        store.manifest(target / "Manifest.lua")
        print(message("Addon installé dans {target}", target=str(target)).render(language or system_language()))
        return
    sys.path.insert(0, str(PROJECT / "tools"))
    from package_addon import runtime_payload
    payload = runtime_payload()
    target.mkdir()
    for name, content in payload.items():
        if name == "Manifest.lua":
            continue  # Generate a manifest for the selected installation below.
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    store.manifest(target / "Manifest.lua")
    print(message("Addon installé dans {target}", target=str(target)).render(language or system_language()))


def choose_wow(language=None):
    """First-run folder picker; Tk and Tcl are included in the Windows bundle."""
    import tkinter as tk
    from tkinter import filedialog, messagebox
    language = language or system_language()

    window = tk.Tk()
    window.withdraw()
    try:
        while True:
            selected = filedialog.askdirectory(
                parent=window, title=message("SVCleaner — choisissez votre version WoW (ex. _retail_)").render(language),
                mustexist=True,
            )
            if not selected:
                return None
            root = Path(selected).resolve()
            if (root / "Interface" / "AddOns").is_dir():
                return root
            messagebox.showerror("SVCleaner", message("Choisissez le dossier de version contenant Interface/AddOns (ex. _retail_).").render(language), parent=window)
    finally:
        window.destroy()


def preferred_wow():
    if FROZEN:
        try:
            root = Path((HOME / "wow-path.txt").read_text(encoding="utf-8").strip())
            if (root / "Interface" / "AddOns").is_dir():
                return root
        except (OSError, UnicodeError, ValueError):
            pass
        return None
    return DEFAULT_WOW


def main():
    if FROZEN:
        # Frozen Python ignores PYTHONUTF8; keep redirected diagnostics readable.
        for stream in (sys.stdout, sys.stderr):
            if stream is not None and hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8")
    initial = argparse.ArgumentParser(add_help=False)
    initial.add_argument("--language")
    language = normalize(initial.parse_known_args()[0].language or system_language())
    def tr(key):
        return message(key).render(language)
    parser = argparse.ArgumentParser(description=tr("SVCleaner : gestionnaire local des SavedVariables WoW"))
    parser.add_argument("--language", choices=list(LANGUAGES) + ["enGB", "ptPT"], help=tr("Langue de l’interface"))
    parser.add_argument("--wow", help=tr("Dossier de version WoW, par exemple _retail_"))
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--manifest", action="store_true", help=tr("Génère Manifest.lua dans le projet, sans modifier WoW"))
    parser.add_argument("--install-addon", action="store_true", help=tr("Installe l’addon si son dossier n’existe pas (WoW fermé)"))
    parser.add_argument("--scan", action="store_true", help=tr("Affiche les volumes uniquement"))
    parser.add_argument("--demo", action="store_true", help=tr("Utilise des données fictives isolées"))
    args = parser.parse_args()
    if args.demo:
        from demo import demo_root
        args.wow = str(demo_root())
    try:
        if args.wow is None:
            args.wow = preferred_wow()
            if FROZEN and (args.wow is None or not (args.wow / "Interface" / "AddOns").is_dir()) and not any((args.no_browser, args.scan, args.manifest, args.install_addon)):
                args.wow = choose_wow(language)
                if args.wow is None:
                    return
                (HOME / "wow-path.txt").write_text(str(args.wow), encoding="utf-8")
            elif args.wow is None:
                args.wow = DEFAULT_WOW
        store = Store(args.wow)
        if args.install_addon:
            install(store, language)
            return
        if args.manifest:
            print(json.dumps(store.manifest(), ensure_ascii=False))
            return
        if args.scan:
            print(json.dumps(store.state()["stats"], ensure_ascii=False, indent=2))
            return
        server = create_server(store, args.port, args.language)
        url = f"http://127.0.0.1:{server.server_port}/"
        print(f"SVCleaner : {url}", flush=True)
        print(tr("Ctrl+C pour arrêter. Toutes les données restent sur ce PC."), flush=True)
        if not args.no_browser:
            threading.Timer(0.3, lambda: webbrowser.open(url)).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
    except (DataError, OSError) as error:
        text = error.message.render(language) if isinstance(error, DataError) else str(error)
        print(f"SVCleaner : {text}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

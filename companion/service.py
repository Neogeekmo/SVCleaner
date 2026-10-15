from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
import os
import re
import subprocess
import threading
import time
import uuid
from pathlib import Path

from lua_data import DataError, Table, at, differences, dump, identity, kind, literal, merge_values, parse, preview, safe_path, token, untoken
from flavors import detect_client, toc_candidates

PROJECT = Path(__file__).resolve().parent.parent
DEFAULT_WOW = Path(r"D:\Jeux\World of Warcraft\_retail_")
CHAR_GUID = re.compile(r"^(.*?)?-?(Player-\d+-[0-9a-fA-F]+)$")
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z_0-9]*$")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def same_data(left, right):
    """Lua table equality by typed keys, independent of serialization order."""
    if kind(left) != kind(right):
        return False
    if isinstance(left, Table):
        return len(left.entries) == len(right.entries) and all(right.has(key) and same_data(value, right.get(key)) for key, value in left.entries)
    return left == right


def contained(path, root):
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise DataError("Le chemin sort du dossier WoW sélectionné")
    return resolved


def check_game_closed():
    """Fail closed when process enumeration is unavailable."""
    if os.name == "nt":
        result = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode:
            raise DataError("Impossible de vérifier que WoW est fermé")
        processes = [row[0].lower() for row in csv.reader(io.StringIO(result.stdout)) if row]
        running = any(re.fullmatch(r"wow(?:classic|b|t|classicb|classict|_.*)?\.exe", item) for item in processes)
    else:
        result = subprocess.run(["ps", "-A", "-o", "comm="], capture_output=True, text=True, timeout=15)
        if result.returncode:
            raise DataError("Impossible de vérifier que WoW est fermé")
        running = bool(re.search(r"(?im)^(?:.*/)?wow(?:classic|b|t)?(?:\.exe)?$", result.stdout))
    if running:
        raise DataError("Fermez tous les clients WoW avant d’appliquer ou restaurer des fichiers")


def metadata(path):
    result = {}
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        match = re.match(r"\s*##\s*([^:]+):\s*(.*)", line)
        if match:
            result[match[1].strip().lower()] = match[2].strip()
    return result


def periodic_game_guard():
    """Poll during large batches without launching tasklist once per file."""
    next_check = 0.0
    def guard():
        nonlocal next_check
        if time.monotonic() >= next_check:
            check_game_closed()
            next_check = time.monotonic() + 1.0
    return guard


def variables(value):
    return [name for name in re.split(r"[,\s]+", value or "") if IDENTIFIER.fullmatch(name)]


class Store:
    def __init__(self, root, data_dir=None):
        self.root = Path(root).resolve()
        if not (self.root / "Interface" / "AddOns").is_dir():
            raise DataError("Choisissez un dossier de version WoW contenant Interface/AddOns (par exemple _retail_)")
        self.data_dir = Path(data_dir or PROJECT / "data" / digest(str(self.root).encode())[:12])
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.records = {}
        self.cache = {}
        self.pending = {}
        self.addons = {}
        self.characters = []
        self.client = detect_client(self.root)
        self.scan()

    def scan(self):
        with self.lock:
            if self.pending:
                raise DataError("Appliquez ou abandonnez le panier avant un nouveau scan")
            addons, records, characters = {}, {}, []
            flavor = self.client["flavor"]
            for folder in sorted((self.root / "Interface" / "AddOns").iterdir()):
                if not folder.is_dir() or folder.is_symlink():
                    continue
                paths = toc_candidates(folder, flavor)
                selected = next((p for p in paths if p.is_file()), None) if flavor else None
                uncertain = selected is None or self.client["uncertain"]
                candidates = [selected] if selected else list(folder.glob("*.toc"))
                if not candidates:
                    continue
                declarations = {"account": [], "character": [], "machine": []}
                title = folder.name
                for toc in candidates:
                    contained(toc, self.root)
                    meta = metadata(toc)
                    title = meta.get("title", title)
                    for scope, field in (("account", "savedvariables"), ("character", "savedvariablespercharacter"), ("machine", "savedvariablesmachine")):
                        declarations[scope].extend(variables(meta.get(field)))
                addons[folder.name] = {"name": folder.name, "title": re.sub(r"\|c[0-9a-fA-F]{8}|\|r", "", title), "variables": {k: sorted(set(v)) for k, v in declarations.items()}, "uncertain": uncertain}
            owner_map = {}
            for addon in addons.values():
                for scope, names in addon["variables"].items():
                    for name in names:
                        owner_map.setdefault((scope, name), []).append(addon["name"])
            account_root = self.root / "WTF" / "Account"
            dirs = []
            if account_root.is_dir():
                for account in sorted(account_root.iterdir()):
                    if not account.is_dir() or account.name == "SavedVariables" or account.is_symlink():
                        continue
                    dirs.append((account / "SavedVariables", "account", account.name, None))
                    if (account / "SavedVariables.lua").is_file():
                        dirs.append((account / "SavedVariables.lua", "system", account.name, None))
                    for realm in sorted(account.iterdir()):
                        if not realm.is_dir() or realm.name == "SavedVariables" or realm.is_symlink():
                            continue
                        for char in sorted(realm.iterdir()):
                            if char.is_dir() and not char.is_symlink():
                                label = f"{char.name} - {realm.name}"
                                characters.append({"account": account.name, "name": char.name, "realm": realm.name, "label": label, "status": "Dossier local · existence en jeu non vérifiée"})
                                dirs.append((char / "SavedVariables", "character", account.name, label))
            dirs.append((self.root / "WTF" / "SavedVariables", "machine", "Installation", None))
            for folder, scope, account, character in dirs:
                candidates = [folder] if folder.is_file() else sorted(folder.glob("*.lua*")) if folder.is_dir() else []
                for path in candidates:
                    if not path.is_file() or not (path.name.endswith(".lua") or path.name.endswith(".lua.bak")):
                        continue
                    contained(path, self.root)
                    relative = path.relative_to(self.root).as_posix()
                    data = path.read_bytes()
                    name = path.name.removesuffix(".bak").removesuffix(".lua")
                    roots = re.findall(r"(?m)^([A-Za-z_][A-Za-z_0-9]*)\s*=", data.decode("utf-8-sig", "surrogateescape"))
                    links = sorted(set(owner for var in roots for owner in owner_map.get((scope, var), [])))
                    installed = addons.get(name)
                    status = "system" if scope == "system" else "protected" if name == "SVCleaner" else "installed" if installed else "linked" if links else "orphan"
                    backup = path.name.endswith(".bak")
                    record_id = digest(relative.encode())[:20]
                    records[record_id] = {"id": record_id, "path": relative, "addon": name, "title": installed["title"] if installed else name, "account": account, "character": character, "scope": scope, "status": status, "backup": backup, "readOnly": scope == "system" or name == "SVCleaner" or backup, "bytes": len(data), "hash": digest(data), "roots": roots, "links": links, "modified": path.stat().st_mtime, "uncertain": bool(installed and installed["uncertain"])}
            self.addons, self.records, self.characters = addons, records, characters
            self.cache = {}
            self.scanned = time.time()
            return self.state()

    def record(self, record_id):
        if record_id not in self.records:
            raise DataError("Fichier inconnu ; rescannez")
        return self.records[record_id]

    def path(self, record):
        return contained(self.root / record["path"], self.root)

    def load(self, record_id):
        record = self.record(record_id)
        if record_id in self.pending and self.pending[record_id]["operation"] == "delete":
            raise DataError("Ce fichier est dans le panier de suppression")
        if record_id not in self.cache:
            if record["bytes"] > 80 * 1024 * 1024:
                raise DataError("Fichier de plus de 80 Mio : affichage limité à l’inventaire")
            data = self.path(record).read_bytes()
            if digest(data) != record["hash"]:
                raise DataError("Le fichier a changé depuis le scan ; rescannez")
            self.cache[record_id] = parse(data.decode("utf-8-sig", "surrogateescape"))
        return self.cache[record_id]

    def writable(self, record_id):
        record = self.record(record_id)
        if record["readOnly"]:
            raise DataError("Fichier protégé ou sauvegarde .bak : lecture seule")
        return record

    def browse(self, record_id, path=None, offset=0):
        path = path or []
        roots = self.load(record_id)
        current = at(roots, path)
        ancestors_protected = any(identity(untoken(item), at(roots, path[:i + 1])) for i, item in enumerate(path))
        items = []
        entries = current.entries if isinstance(current, Table) else [("(valeur)", current)]
        offset = max(0, int(offset))
        for key, value in entries[offset:offset + 200]:
            item_path = path + [token(key)] if isinstance(current, Table) else path
            char_match = CHAR_GUID.fullmatch(key) if isinstance(key, str) else None
            char_status = None
            if char_match:
                guid = char_match[2]
                roster = self.roster(self.record(record_id)["account"])
                char_status = "Observé par SVCleaner" if guid in roster else "Non observé · à vérifier"
            elif isinstance(key, str) and " - " in key and path and untoken(path[-1]) in ("char", "profileKeys"):
                known = any(c["account"] == self.record(record_id)["account"] and c["label"] == key for c in self.characters)
                char_status = "Dossier local connu" if known else "Dossier local absent · à vérifier"
            shown = preview(value)
            too_large = isinstance(shown, str) and len(shown) > 32768
            if too_large:
                shown = shown[:300] + "…"
            unsafe_number = isinstance(value, int) and not isinstance(value, bool) and abs(value) > 2**53 - 1
            items.append({"key": token(key), "path": item_path, "type": kind(value), "value": shown, "tooLarge": too_large or unsafe_number, "protected": ancestors_protected or identity(key, value), "characterStatus": char_status})
        return {"items": items, "total": len(entries), "offset": offset, "path": path, "type": kind(current)}

    def roster(self, account):
        result = {}
        for record in self.records.values():
            if record["addon"] == "SVCleaner" and record["account"] == account and record["scope"] == "account" and not record["backup"]:
                try:
                    db = self.load(record["id"]).get("SVCleanerDB")
                    chars = db.get("characters") if isinstance(db, Table) else None
                    if isinstance(chars, Table):
                        result.update({k: v for k, v in chars.entries})
                except (DataError, OSError):
                    pass
        return result

    def stage(self, request):
        with self.lock:
            record_id, path = request["id"], request.get("path", [])
            operation = request["operation"]
            if operation == "delete-file":
                record = self.record(record_id)
                if record["scope"] == "system" or record["addon"] == "SVCleaner":
                    raise DataError("Fichier protégé")
                self.pending[record_id] = {"operation": "delete", "summary": "Mettre le fichier en quarantaine"}
                return self.state()
            record = self.writable(record_id)
            roots = self.load(record_id)
            if not path:
                raise DataError("Choisissez une variable ou une valeur")
            parent = at(roots, path[:-1])
            if not isinstance(parent, Table):
                raise DataError("Le parent doit être une table")
            key = untoken(path[-1])
            if operation == "create":
                safe_path(roots, path[:-1])
                if parent.has(key):
                    raise DataError("Cette clé existe déjà")
                if len(path) == 1 and (not isinstance(key, str) or not IDENTIFIER.fullmatch(key)):
                    raise DataError("Nom de variable Lua invalide")
                value = Table() if request.get("valueType") == "table" else request.get("value")
                if value is None or kind(value) not in ("string", "number", "boolean", "table") or identity(key, value):
                    raise DataError("Valeur invalide ou identité protégée")
                literal(value)
                old = None
            else:
                safe_path(roots, path)
                old = at(roots, path)
            if operation == "edit":
                value = request.get("value")
                if kind(old) == "table" or kind(value) != kind(old):
                    raise DataError("Éditez une valeur scalaire en conservant son type")
                if kind(value) == "number" and not isinstance(value, bool):
                    literal(value)
                if identity(key, value):
                    raise DataError("Les valeurs d’identité sont protégées")
                parent.set(key, value)
            elif operation == "create":
                parent.set(key, value)
            elif operation == "delete-value":
                parent.set(key, None)
            else:
                raise DataError("Opération inconnue")
            details = self.pending.get(record_id, {}).get("details", [])
            details.append({"path": path, "before": str(preview(old))[:500], "after": str(preview(value))[:500] if operation in ("edit", "create") else "(supprimé)", "operation": operation})
            self.pending[record_id] = {"operation": "write", "summary": "Modifier les données sélectionnées", "details": details}
            return self.state()

    def stage_delete_files(self, record_ids):
        """Validate the entire selection before adding any file to the basket."""
        with self.lock:
            if not isinstance(record_ids, list) or not record_ids or len(record_ids) > 10000 or any(not isinstance(item, str) for item in record_ids):
                raise DataError("Sélection de fichiers invalide")
            unique_ids = list(dict.fromkeys(record_ids))
            records = [self.record(record_id) for record_id in unique_ids]
            if any(record["scope"] == "system" or record["addon"] == "SVCleaner" for record in records):
                raise DataError("La sélection contient un fichier protégé ; aucun fichier n’a été ajouté")
            pending = dict(self.pending)
            for record_id in unique_ids:
                pending[record_id] = {"operation": "delete", "summary": "Suppression groupée · original sauvegardé à l’application"}
            self.pending = pending
            return {"staged": len(unique_ids), "state": self.state()}

    def comparison_options(self, record_id):
        """Bounded picker; display names never replace the actual typed keys."""
        record = self.record(record_id)
        roots = self.load(record_id)
        options, examined, truncated = [], 0, False
        def visit(value, path, depth):
            nonlocal examined, truncated
            examined += 1
            if examined > 1500 or len(options) >= 250:
                truncated = True
                return
            if not isinstance(value, Table) and depth > 0:
                return
            key = str(untoken(path[-1]))
            match = CHAR_GUID.match(key)
            label = record["character"] or ((match.group(1) or "").rstrip("-") or key if match else key)
            options.append({"id": record_id, "path": path, "label": label, "keys": len(value.entries) if isinstance(value, Table) else 0})
            if not isinstance(value, Table):
                return
            if depth < 3:
                for child_key, child in value.entries:
                    if isinstance(child, Table):
                        visit(child, path + [token(child_key)], depth + 1)
                    if truncated:
                        break
        for key, value in roots.entries:
            visit(value, [token(key)], 0)
            if truncated:
                break
        return {"options": options, "truncated": truncated}

    def compare(self, request):
        left_record, right_record = self.record(request["leftId"]), self.record(request["rightId"])
        if left_record["account"] != right_record["account"] or left_record["addon"] != right_record["addon"]:
            raise DataError("Comparez deux blocs du même addon et du même compte")
        left = at(self.load(request["leftId"]), request["leftPath"])
        right = at(self.load(request["rightId"]), request["rightPath"])
        if not request["leftPath"] or not request["rightPath"] or untoken(request["leftPath"][0]) != untoken(request["rightPath"][0]):
            raise DataError("Choisissez deux blocs de la même SavedVariable")
        rows = differences(left, right)
        ancestor_protected = False
        for record_id, path in ((request["leftId"], request["leftPath"]), (request["rightId"], request["rightPath"])):
            try:
                safe_path(self.load(record_id), path)
            except DataError:
                ancestor_protected = True
        for row in rows:
            if ancestor_protected:
                row["protected"], row["copyable"] = True, False
            row["reason"] = "identity" if row["protected"] else "missing" if "nil" in (row["leftType"], row["rightType"]) else "type" if not row["copyable"] else "value"
            row["toLeft"] = row["copyable"] and not left_record["readOnly"]
            row["toRight"] = row["copyable"] and not right_record["readOnly"]
        signature = digest(json.dumps(rows, sort_keys=True, ensure_ascii=True).encode())
        return {"rows": rows, "signature": signature, "leftReadOnly": left_record["readOnly"], "rightReadOnly": right_record["readOnly"]}

    def transfer(self, request):
        with self.lock:
            comparison = self.compare(request)
            if request.get("expectedSignature") and request["expectedSignature"] != comparison["signature"]:
                raise DataError("Les données ont changé depuis l’aperçu. Actualisez la comparaison avant de préparer la copie.")
            direction = request.get("direction", "right")
            if direction not in ("left", "right"):
                raise DataError("Sens de transfert invalide")
            source_id, target_id = (request["leftId"], request["rightId"]) if direction == "right" else (request["rightId"], request["leftId"])
            base_source, base_target = (request["leftPath"], request["rightPath"]) if direction == "right" else (request["rightPath"], request["leftPath"])
            relative = request.get("relativePath", [])
            source_path, target_path = base_source + relative, base_target + relative
            self.writable(target_id)
            if not base_source or not base_target or untoken(base_source[0]) != untoken(base_target[0]):
                raise DataError("Les deux blocs doivent appartenir à la même SavedVariable")
            source_roots, target_roots = self.load(source_id), self.load(target_id)
            safe_path(source_roots, source_path)
            safe_path(target_roots, target_path)
            source, target = at(source_roots, source_path), at(target_roots, target_path)
            # Snapshot source first: comparisons can involve the same physical file.
            updated, count = merge_values(copy.deepcopy(source), target)
            if count:
                parent = at(target_roots, target_path[:-1])
                parent.set(untoken(target_path[-1]), updated)
                details = self.pending.get(target_id, {}).get("details", [])
                details.append({"path": target_path, "before": str(preview(target))[:500], "after": f"{count} valeurs transférées", "operation": "merge"})
                self.pending[target_id] = {"operation": "write", "summary": f"Fusion protégée : {count} valeurs", "details": details}
            return {"changed": count, "state": self.state()}

    def discard(self):
        with self.lock:
            self.pending, self.cache = {}, {}
            return self.state()

    def import_requests(self):
        with self.lock:
            imported, skipped, already_applied = 0, [], 0
            for record in self.records.values():
                if record["addon"] != "SVCleaner" or record["scope"] != "account" or record["backup"]:
                    continue
                db = self.load(record["id"]).get("SVCleanerDB")
                requests = db.get("requests") if isinstance(db, Table) else None
                if not isinstance(requests, Table):
                    continue
                for _, request in requests.entries:
                    try:
                        if not isinstance(request, Table):
                            raise DataError("Demande invalide")
                        if request.get("kind") == "cvar":
                            raise DataError("CVar : appliquez cette demande dans l’onglet CVars en jeu")
                        candidates = [r for r in self.records.values() if r["addon"] == request.get("addon") and r["scope"] == request.get("scope") and r["account"] == record["account"] and not r["backup"] and (r["scope"] != "character" or r["character"] == request.get("character"))]
                        if len(candidates) != 1:
                            raise DataError("Addon ou fichier de personnage introuvable / ambigu")
                        target_id = candidates[0]["id"]
                        path = [token(request.get("root"))]
                        path_table = request.get("path")
                        if isinstance(path_table, Table):
                            for _, item in path_table.entries:
                                if not isinstance(item, Table):
                                    raise DataError("Chemin invalide")
                                typed_key = {"type": item.get("type"), "value": item.get("value")}
                                untoken(typed_key)
                                path.append(typed_key)
                        roots = self.load(target_id)
                        parent = at(roots, path[:-1])
                        if not isinstance(parent, Table):
                            raise DataError("Parent introuvable")
                        key = untoken(path[-1])
                        current = parent.get(key)
                        operation = request.get("operation")
                        desired = None if operation == "delete-value" else request.get("value")
                        if same_data(current, desired):
                            already_applied += 1
                            continue
                        expected = request.get("expectedSnapshot") if request.get("expectedType") == "table" else request.get("expectedValue")
                        if request.get("expectedType") == "table" and not isinstance(expected, Table):
                            raise DataError("Ancienne suppression de bloc sans instantané : sélection manuelle nécessaire")
                        if kind(current) != request.get("expectedType") or not same_data(current, expected):
                            raise DataError("Valeur modifiée depuis la demande ; vérification manuelle nécessaire")
                        self.stage({"id": target_id, "path": path, "operation": operation, "value": desired, "valueType": "table" if isinstance(desired, Table) else kind(desired)})
                        imported += 1
                    except (DataError, KeyError, TypeError) as error:
                        skipped.append(str(error))
            return {"imported": imported, "alreadyApplied": already_applied, "skipped": skipped, "state": self.state()}

    def cache_info(self, name="Cache"):
        if name not in ("Cache", "GPUCache"):
            raise DataError("Emplacement de cache non autorisé")
        path = self.root / name
        total, files = 0, 0
        if path.is_dir() and not path.is_symlink():
            for current, directories, names in os.walk(path, followlinks=False):
                directories[:] = [folder_name for folder_name in directories if not (Path(current) / folder_name).is_symlink() and not getattr(Path(current) / folder_name, "is_junction", lambda: False)()]
                for filename in names:
                    candidate = Path(current) / filename
                    if candidate.is_file() and not candidate.is_symlink():
                        total += candidate.stat().st_size
                        files += 1
        result = {"path": name, "exists": path.is_dir(), "bytes": total, "files": files}
        if name == "Cache":
            result["locations"] = [{key: value for key, value in result.items()}, self.cache_info("GPUCache")]
        return result

    def reset_cache(self, name="Cache"):
        with self.lock:
            check_game_closed()
            if name not in ("Cache", "GPUCache"):
                raise DataError("Emplacement de cache non autorisé")
            if self.pending:
                raise DataError("Appliquez ou abandonnez le panier avant de mettre Cache en quarantaine")
            source = contained(self.root / name, self.root)
            if source != self.root / name or not source.is_dir() or source.is_symlink():
                raise DataError(f"Dossier {name} absent ou redirigé ; opération refusée")
            transaction_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
            destination = contained(self.root / (name + ".SVCleaner-" + transaction_id), self.root)
            if destination.exists():
                raise DataError("Le dossier de sauvegarde existe déjà")
            size = self.cache_info(name)["bytes"]
            directory = self.data_dir / transaction_id
            directory.mkdir()
            tx = {"id": transaction_id, "root": str(self.root), "timestamp": time.time(), "status": "prepared", "type": "cache", "cacheLocation": name, "files": [], "savedBytes": 0, "cacheBytes": size, "backupPath": destination.name}
            journal = directory / "transaction.json"
            journal.write_text(json.dumps(tx, indent=2), encoding="utf-8")
            source.rename(destination)
            tx["status"] = "applied"
            journal.write_text(json.dumps(tx, indent=2), encoding="utf-8")
            return self.state()

    def history(self):
        entries = []
        for path in sorted(self.data_dir.glob("*/transaction.json"), reverse=True):
            try:
                entry = json.loads(path.read_text(encoding="utf-8"))
                if entry.get("root") == str(self.root):
                    entries.append(entry)
            except (OSError, ValueError):
                continue
        return entries[:100]

    def apply(self):
        with self.lock:
            check_game_closed()
            if not self.pending:
                raise DataError("Le panier est vide")
            planned = []
            for record_id, change in self.pending.items():
                record = self.record(record_id) if change["operation"] == "delete" else self.writable(record_id)
                path = self.path(record)
                old = path.read_bytes()
                if digest(old) != record["hash"]:
                    raise DataError("Un fichier a changé depuis le scan ; abandonnez et rescannez")
                new = dump(self.cache[record_id]).encode("utf-8") if change["operation"] == "write" else None
                if new is not None:
                    parse(new.decode())  # Reject anything outside the data-only grammar.
                planned.append((record, old, new))
            transaction_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
            directory = self.data_dir / transaction_id
            directory.mkdir()
            entries = []
            for index, (record, old, new) in enumerate(planned):
                (directory / f"{index}.original").write_bytes(old)
                entries.append({"path": record["path"], "backup": f"{index}.original", "beforeHash": digest(old), "afterHash": digest(new) if new is not None else None, "beforeBytes": len(old), "afterBytes": len(new) if new is not None else 0, "operation": "write" if new is not None else "delete"})
            tx = {"id": transaction_id, "root": str(self.root), "timestamp": time.time(), "status": "prepared", "files": entries, "savedBytes": sum(e["beforeBytes"] - e["afterBytes"] for e in entries)}
            journal = directory / "transaction.json"
            journal.write_text(json.dumps(tx, ensure_ascii=True, indent=2), encoding="utf-8")
            applied = []
            game_guard = periodic_game_guard()
            try:
                for record, old, new in planned:
                    game_guard()
                    target = self.path(record)
                    if digest(target.read_bytes()) != digest(old):
                        raise DataError("Modification externe détectée pendant l’application")
                    if new is None:
                        target.unlink()
                    else:
                        self.atomic_write(target, new)
                    applied.append((target, old, new))
                check_game_closed()
                tx["status"] = "applied"
            except Exception:
                for target, old, new in reversed(applied):
                    current = target.read_bytes() if target.exists() else None
                    if current == new:
                        self.atomic_write(target, old)
                tx["status"] = "failed"
                journal.write_text(json.dumps(tx, indent=2), encoding="utf-8")
                raise
            journal.write_text(json.dumps(tx, indent=2), encoding="utf-8")
            self.pending = {}
            self.scan()
            return {"transaction": tx, "state": self.state()}

    @staticmethod
    def atomic_write(target, data):
        temporary = target.with_name(target.name + ".svcleaner-" + uuid.uuid4().hex + ".tmp")
        try:
            with temporary.open("xb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

    def restore(self, transaction_id):
        with self.lock:
            check_game_closed()
            if self.pending:
                raise DataError("Abandonnez ou appliquez le panier avant de restaurer")
            if not re.fullmatch(r"\d{8}-\d{6}-[a-f0-9]{8}", transaction_id):
                raise DataError("Sauvegarde inconnue")
            directory = contained(self.data_dir / transaction_id, self.data_dir)
            journal = directory / "transaction.json"
            tx = json.loads(journal.read_text(encoding="utf-8"))
            if tx.get("root") != str(self.root) or tx["status"] not in ("applied", "prepared", "failed"):
                raise DataError("Cette sauvegarde n’est pas restaurable")
            if tx.get("type") == "cache":
                cache_name = tx.get("cacheLocation", "Cache")
                if cache_name not in ("Cache", "GPUCache") or not re.fullmatch(re.escape(cache_name) + r"\.SVCleaner-\d{8}-\d{6}-[a-f0-9]{8}", tx["backupPath"]):
                    raise DataError("Chemin de sauvegarde Cache invalide")
                source = contained(self.root / tx["backupPath"], self.root)
                target = contained(self.root / cache_name, self.root)
                if target.exists():
                    raise DataError(f"WoW a déjà recréé {cache_name}. Restauration refusée pour préserver les nouveaux fichiers ; la sauvegarde reste disponible.")
                if source != self.root / tx["backupPath"] or not source.is_dir():
                    raise DataError("Sauvegarde Cache absente ou redirigée")
                source.rename(target)
                tx["status"] = "restored"
                journal.write_text(json.dumps(tx, indent=2), encoding="utf-8")
                return self.state()
            planned = []
            for entry in tx["files"]:
                relative = Path(entry["path"])
                if not relative.parts or relative.parts[0] != "WTF" or relative.parent.name != "SavedVariables" or not (relative.name.endswith(".lua") or relative.name.endswith(".lua.bak")):
                    raise DataError("Le journal ne cible pas un fichier SavedVariables autorisé")
                target = contained(self.root / entry["path"], self.root)
                current = target.read_bytes() if target.exists() else None
                current_hash = digest(current) if current is not None else None
                if current_hash == entry["beforeHash"]:
                    continue  # Already rolled back, or not reached before interruption.
                if current_hash != entry["afterHash"]:
                    raise DataError("Un fichier a changé depuis le nettoyage ; restauration automatique refusée")
                original = contained(directory / entry["backup"], directory).read_bytes()
                if digest(original) != entry["beforeHash"]:
                    raise DataError("Sauvegarde altérée")
                planned.append((target, original, current))
            applied = []
            game_guard = periodic_game_guard()
            try:
                for target, original, current in planned:
                    game_guard()
                    latest = target.read_bytes() if target.exists() else None
                    if latest != current:
                        raise DataError("Modification externe détectée pendant la restauration")
                    self.atomic_write(target, original)
                    applied.append((target, original, current))
                check_game_closed()
            except Exception:
                for target, original, current in reversed(applied):
                    if target.read_bytes() == original:
                        if current is None:
                            target.unlink()
                        else:
                            self.atomic_write(target, current)
                raise
            tx["status"] = "restored"
            journal.write_text(json.dumps(tx, indent=2), encoding="utf-8")
            self.scan()
            return self.state()

    def manifest(self, destination=None):
        # Export into the workspace by default. Installation is an explicit CLI action.
        destination = Path(destination or PROJECT / "Manifest.lua")
        table = Table()
        for addon in self.addons.values():
            node = Table()
            for scope, names in addon["variables"].items():
                if scope != "machine":
                    node.set(scope, Table([(i + 1, name) for i, name in enumerate(names)]))
            table.set(addon["name"], node)
        source = "-- Generated by SVCleaner companion from installed TOCs.\nlocal _, SVC = ...\nSVC.Manifest = " + literal(table) + "\n"
        destination.write_text(source, encoding="utf-8")
        return {"addons": len(self.addons), "path": str(destination)}

    def state(self):
        records = list(self.records.values())
        primary = [r for r in records if not r["backup"] and r["scope"] != "system"]
        stats = {"bytes": sum(r["bytes"] for r in primary), "backupBytes": sum(r["bytes"] for r in records if r["backup"]), "orphanBytes": sum(r["bytes"] for r in primary if r["status"] == "orphan"), "files": len(primary), "addons": len(set(r["addon"] for r in primary)), "characters": len(self.characters)}
        groups = {}
        for r in primary:
            groups[r["addon"]] = groups.get(r["addon"], 0) + r["bytes"]
        history = self.history()
        stats["savedBytes"] = sum(max(0, t["savedBytes"]) for t in history if t["status"] == "applied")
        return {"root": str(self.root), "client": self.client, "records": records, "characters": self.characters, "stats": stats, "groups": sorted(({"addon": k, "bytes": v} for k, v in groups.items()), key=lambda v: -v["bytes"]), "pending": [{"id": key, "path": self.records[key]["path"], **value} for key, value in self.pending.items()], "history": history, "scanned": self.scanned}

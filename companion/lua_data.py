"""Parse WoW's literal SavedVariables format without ever executing Lua."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from i18n import Message, message

LONG_OPEN = re.compile(r"\[(=*)\[")
IDENTIFIER_TOKEN = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")
NAMED_FIELD = re.compile(r"[A-Za-z_][A-Za-z_0-9]*\s*=")
NUMBER_TOKEN = re.compile(r"[+-]?(?:0[xX][0-9a-fA-F]+(?:\.[0-9a-fA-F]*)?(?:[pP][+-]?\d+)?|(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)")
STRING_CHUNKS = {'"': re.compile(r'[^"\\\r\n]+'), "'": re.compile(r"[^'\\\r\n]+")}


class DataError(ValueError):
    def __init__(self, text):
        self.message = text if isinstance(text, Message) else message(text)
        super().__init__(str(self.message))


@dataclass
class Table:
    # Python dict conflates True with 1; Lua tables do not.
    entries: list = field(default_factory=list)
    _index: dict = field(default_factory=dict, init=False, repr=False, compare=False)

    def __post_init__(self):
        self._reindex()

    def _reindex(self):
        self._index = {(kind(key), key): i for i, (key, _) in enumerate(self.entries)}

    def get(self, key, default=None):
        index = self._index.get((kind(key), key))
        return self.entries[index][1] if index is not None else default

    def has(self, key):
        return (kind(key), key) in self._index

    def set(self, key, value):
        index = self._index.get((kind(key), key))
        if index is not None:
            if value is None:
                del self.entries[index]
                self._reindex()
            else:
                self.entries[index] = (key, value)
            return
        if value is not None:
            self._index[(kind(key), key)] = len(self.entries)
            self.entries.append((key, value))


def kind(value):
    if value is None:
        return "nil"
    if isinstance(value, Table):
        return "table"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    raise DataError("Type Lua non pris en charge")


def token(key):
    if isinstance(key, int) and not isinstance(key, bool) and abs(key) > 2**53 - 1:
        return {"type": "number", "value": str(key), "encoding": "decimal"}
    return {"type": kind(key), "value": key}


def untoken(key):
    if not isinstance(key, dict) or key.get("type") not in ("string", "number", "boolean"):
        raise DataError("Clé invalide")
    value = key.get("value")
    if key.get("encoding") == "decimal" and key["type"] == "number" and isinstance(value, str) and re.fullmatch(r"-?\d+", value):
        return int(value)
    if kind(value) != key["type"] or (kind(value) == "number" and not math.isfinite(value)):
        raise DataError("Type de clé invalide")
    return value


class Parser:
    def __init__(self, source, max_nodes=2_000_000):
        self.source = source.lstrip("\ufeff")
        self.pos = 0
        self.nodes = 0
        self.max_nodes = max_nodes

    def error(self, message):
        line = self.source.count("\n", 0, self.pos) + 1
        raise DataError(Message("{message} (ligne {line})", {"message": message if isinstance(message, Message) else Message(message), "line": line}))

    def long_string(self):
        match = LONG_OPEN.match(self.source, self.pos)
        if not match:
            return None
        start = self.pos + len(match[0])
        end_mark = "]" + match[1] + "]"
        end = self.source.find(end_mark, start)
        if end < 0:
            self.error("Chaîne longue incomplète")
        self.pos = end + len(end_mark)
        value = self.source[start:end]
        if value.startswith("\r\n"):
            value = value[2:]
        elif value.startswith("\n"):
            value = value[1:]
        return value

    def skip(self):
        while self.pos < len(self.source):
            if self.source[self.pos].isspace():
                self.pos += 1
            elif self.source.startswith("--", self.pos):
                self.pos += 2
                if self.long_string() is None:
                    end = self.source.find("\n", self.pos)
                    self.pos = len(self.source) if end < 0 else end + 1
            else:
                return

    def consume(self, char):
        self.skip()
        if self.source.startswith(char, self.pos):
            self.pos += len(char)
            return True
        return False

    def expect(self, char):
        if not self.consume(char):
            self.error(message("Attendu : {char}", char=char))

    def identifier(self):
        self.skip()
        match = IDENTIFIER_TOKEN.match(self.source, self.pos)
        if not match:
            self.error("Identifiant attendu")
        self.pos += len(match[0])
        return match[0]

    def quoted(self):
        quote = self.source[self.pos]
        self.pos += 1
        result = bytearray()
        escapes = {"a": 7, "b": 8, "f": 12, "n": 10, "r": 13, "t": 9, "v": 11}
        while self.pos < len(self.source):
            chunk = STRING_CHUNKS[quote].match(self.source, self.pos)
            if chunk:
                result.extend(chunk[0].encode("utf-8", "surrogateescape"))
                self.pos = chunk.end()
                continue
            char = self.source[self.pos]
            self.pos += 1
            if char == quote:
                return result.decode("utf-8", "surrogateescape")
            if char in "\r\n":
                self.error("Retour à la ligne non échappé")
            if char != "\\":
                result.extend(char.encode("utf-8", "surrogateescape"))
                continue
            if self.pos >= len(self.source):
                self.error("Échappement incomplet")
            char = self.source[self.pos]
            self.pos += 1
            if char in escapes:
                result.append(escapes[char])
            elif char.isdigit() and char.isascii():
                digits = char
                for _ in range(2):
                    if self.pos < len(self.source) and self.source[self.pos].isdigit() and self.source[self.pos].isascii():
                        digits += self.source[self.pos]
                        self.pos += 1
                if int(digits) > 255:
                    self.error("Échappement hors plage")
                result.append(int(digits))
            elif char == "x":
                hex_value = self.source[self.pos:self.pos + 2]
                if not re.fullmatch(r"[0-9a-fA-F]{2}", hex_value):
                    self.error("Échappement hexadécimal invalide")
                result.append(int(hex_value, 16))
                self.pos += 2
            elif char == "z":
                while self.pos < len(self.source) and self.source[self.pos].isspace():
                    self.pos += 1
            elif char in "\r\n":
                if char == "\r" and self.source[self.pos:self.pos + 1] == "\n":
                    self.pos += 1
                result.append(10)
            elif char in "\\\"'":
                result.extend(char.encode())
            else:
                self.error("Échappement Lua inconnu")
        self.error("Chaîne incomplète")

    def value(self, depth=0):
        self.skip()
        self.nodes += 1
        if self.nodes > self.max_nodes or depth > 120:
            self.error("Limite de complexité atteinte")
        char = self.source[self.pos:self.pos + 1]
        if char in ("'", '"'):
            return self.quoted()
        if char == "[":
            value = self.long_string()
            if value is not None:
                return value
        if self.consume("{"):
            result, index = Table(), 1
            while not self.consume("}"):
                self.skip()
                if self.source[self.pos:self.pos + 1] == "[" and not LONG_OPEN.match(self.source, self.pos):
                    self.pos += 1
                    key = self.value(depth + 1)
                    if kind(key) not in ("string", "number", "boolean"):
                        self.error("Clé de table invalide")
                    self.expect("]")
                    self.expect("=")
                    value = self.value(depth + 1)
                elif NAMED_FIELD.match(self.source, self.pos):
                    key = self.identifier()
                    self.expect("=")
                    value = self.value(depth + 1)
                else:
                    key, value = index, self.value(depth + 1)
                    index += 1
                result.set(key, value)
                if not self.consume(",") and not self.consume(";"):
                    self.expect("}")
                    break
            return result
        match = NUMBER_TOKEN.match(self.source, self.pos)
        if match:
            self.pos += len(match[0])
            raw = match[0]
            value = float.fromhex(raw) if "x" in raw.lower() else float(raw)
            if not math.isfinite(value):
                self.error("Nombre non fini")
            # Parse integers directly to avoid precision loss in large integer keys.
            if re.fullmatch(r"[+-]?\d+", raw):
                return int(raw)
            if re.fullmatch(r"[+-]?0[xX][0-9a-fA-F]+", raw):
                return int(raw, 16)
            return value
        word = self.identifier()
        if word in ("true", "false", "nil"):
            return {"true": True, "false": False, "nil": None}[word]
        self.error("Seules les données littérales sont autorisées")

    def parse(self):
        result = Table()
        self.skip()
        while self.pos < len(self.source):
            key = self.identifier()
            self.expect("=")
            result.set(key, self.value())
            self.consume(";")
            self.skip()
        return result


def parse(source):
    return Parser(source).parse()


def quote(value):
    parts = ['"']
    for byte in value.encode("utf-8", "surrogateescape"):
        if byte in (34, 92):
            parts.append("\\" + chr(byte))
        elif byte < 32 or byte == 127 or byte >= 128:
            parts.append(f"\\{byte:03d}")
        else:
            parts.append(chr(byte))
    return "".join(parts) + '"'


def literal(value, depth=0):
    if depth > 120:
        raise DataError("Table trop profonde")
    typ = kind(value)
    if typ == "table":
        indent = "\t" * depth
        return "{\n" + "".join(f"{indent}\t[{literal(k)}] = {literal(v, depth + 1)},\n" for k, v in value.entries) + indent + "}"
    if typ == "string":
        return quote(value)
    if typ == "number":
        if not math.isfinite(value):
            raise DataError("Nombre non fini")
        return repr(value)
    return {"nil": "nil", "boolean": "true" if value else "false"}[typ]


def dump(roots):
    return "-- SVCleaner : données littérales uniquement.\n" + "".join(f"{key} = {literal(value)}\n" for key, value in roots.entries)


def at(roots, path):
    value = roots
    for item in path:
        key = untoken(item)
        if not isinstance(value, Table) or not value.has(key):
            raise DataError("Chemin introuvable ; rescannez les données")
        value = value.get(key)
    return value


IDENTITIES = {"id", "guid", "playerid", "characterid", "userid", "playerguid", "characterguid", "realm", "realmname", "servername", "playername", "charactername", "name", "key", "profilekey"}


def identity(key, value=None):
    guid_field = isinstance(key, str) and not re.search(r"-Player-\d+-[0-9A-Fa-f]+$", key) and (re.search(r"guids?$|(?:^|\W|_)guids?(?:\W|_)", key, re.IGNORECASE) or re.search(r"[Gg][Uu][Ii][Dd][A-Z_]", key))
    return (isinstance(key, str) and (key.lower() in IDENTITIES or key.endswith(("ID", "Id")) or key.lower().endswith("_id") or bool(guid_field))) or (isinstance(value, str) and re.search(r"Player-\d+-[0-9A-Fa-f]+", value) is not None)


def safe_path(roots, path):
    for index, item in enumerate(path):
        key = untoken(item)
        if identity(key, at(roots, path[:index + 1])):
            raise DataError("Identité protégée : les ID et clés restent inchangés")


def merge_values(source, target):
    """Overwrite existing same-type values only; never create or rename keys."""
    if kind(source) != kind(target):
        raise DataError("Les types doivent être identiques")
    if not isinstance(source, Table):
        return source, int(source != target)
    result, count = Table(), 0
    for key, value in target.entries:
        if source.has(key) and not identity(key, value) and not identity(key, source.get(key)) and kind(source.get(key)) == kind(value):
            updated, n = merge_values(source.get(key), value)
            result.set(key, updated)
            count += n
        else:
            result.set(key, value)
    return result, count


def differences(left, right, path=None, limit=3000):
    result = []
    def walk(a, b, current, blocked=False):
        if len(result) >= limit:
            raise DataError(message("Diff trop grand (limite {limit}) ; choisissez un sous-bloc", limit=limit))
        if isinstance(a, Table) and isinstance(b, Table):
            keys = [key for key, _ in a.entries]
            keys.extend(key for key, _ in b.entries if not a.has(key))
            for key in keys:
                av, bv = a.get(key), b.get(key)
                walk(av, bv, current + [token(key)], blocked or identity(key, av) or identity(key, bv))
        elif a != b:
            result.append({"path": current, "left": preview(a), "right": preview(b), "leftType": kind(a), "rightType": kind(b), "protected": blocked, "copyable": not blocked and a is not None and b is not None and kind(a) == kind(b)})
    walk(left, right, path or [])
    return result


def preview(value):
    if isinstance(value, Table):
        return message("{ {count} clés }", count=len(value.entries))
    if isinstance(value, int) and not isinstance(value, bool) and abs(value) > 2**53 - 1:
        return str(value)
    return value


def short_preview(value):
    shown = preview(value)
    return shown if isinstance(shown, Message) else str(shown)[:500]

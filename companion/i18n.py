"""Shared browser/server catalogs. Only explicit messages are translated."""
import json
import locale
import re
from dataclasses import dataclass, field

from runtime import PROJECT

CATALOGS = json.loads((PROJECT / "companion" / "web" / "locales.json").read_text(encoding="utf-8"))
LANGUAGES = {"enUS": "English", "frFR": "Français", "deDE": "Deutsch", "esES": "Español (España)", "esMX": "Español (Latinoamérica)", "itIT": "Italiano", "ptBR": "Português (Brasil)", "ruRU": "Русский", "koKR": "한국어", "zhCN": "简体中文", "zhTW": "繁體中文"}
ALIASES = {"enGB": "enUS", "ptPT": "ptBR"}


def normalize(value):
    value = (value or "").split(",")[0].split(";")[0].replace("-", "").replace("_", "").lower()
    known = {key.lower(): key for key in LANGUAGES}
    known.update({key.lower(): target for key, target in ALIASES.items()})
    if value.startswith("zhhant") or value in ("zhhk", "zhmo"):
        return "zhTW"
    if value.startswith("es") and value not in ("es", "eses"):
        return "esMX"
    return known.get(value, {"en": "enUS", "fr": "frFR", "de": "deDE", "es": "esES", "it": "itIT", "pt": "ptBR", "ru": "ruRU", "ko": "koKR", "zh": "zhCN"}.get(value[:2], "enUS"))


def system_language():
    return normalize(locale.getlocale()[0])


@dataclass(frozen=True)
class Message:
    key: str
    values: dict = field(default_factory=dict)

    def render(self, language="frFR"):
        catalog = CATALOGS.get(normalize(language), CATALOGS["enUS"])
        text = catalog.get(self.key, CATALOGS["enUS"].get(self.key, self.key))
        def substitute(match):
            value = self.values.get(match[1], match[0])
            return value.render(language) if isinstance(value, Message) else str(value)
        return re.sub(r"\{(\w+)\}", substitute, text)

    def __str__(self):
        return self.render("frFR")


def message(key, **values):
    return Message(key, values)


def encoder(language):
    def encode(value):
        if isinstance(value, Message):
            return value.render(language)
        raise TypeError(f"Not JSON serializable: {type(value).__name__}")
    return encode

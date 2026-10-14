import json
import re
import unittest
from pathlib import Path

try:
    from lupa.lua51 import LuaRuntime
except ImportError:
    LuaRuntime = None

ROOT = Path(__file__).resolve().parent.parent


@unittest.skipIf(LuaRuntime is None, "Lua 5.1 unavailable")
class LocaleTests(unittest.TestCase):
    def test_all_catalogs_have_matching_format_arguments_and_client_fonts(self):
        data = json.loads((ROOT / "tools" / "locales.json").read_text(encoding="utf-8"))
        grid = json.loads((ROOT / "tools" / "grid_locales.json").read_text(encoding="utf-8"))
        data["keys"].extend(grid["keys"]); data["locales"]["enUS"].extend(grid["locales"]["enUS"])
        keys = data["keys"]
        for locale in ("enUS", "enGB", "frFR", "deDE", "esES", "esMX", "itIT", "ptBR", "ptPT", "ruRU", "koKR", "zhCN", "zhTW", "unknown"):
            with self.subTest(locale=locale):
                lua=LuaRuntime(unpack_returned_tuples=True)
                lua.globals().clientLocale=locale
                lua.execute('SVC={}; STANDARD_TEXT_FONT="ClientLocalizedFont"; function GetLocale() return clientLocale end')
                lua.execute((ROOT / "Locale.lua").read_text(encoding="utf-8"), "SVCleaner",lua.globals().SVC)
                self.assertEqual(lua.globals().SVC.font,"ClientLocalizedFont")
                catalog=lua.globals().SVC.L
                for key,base in zip(keys,data["locales"]["enUS"]):
                    translated=catalog[key]
                    self.assertTrue(translated)
                    self.assertEqual(re.findall(r"%[sd]",translated),re.findall(r"%[sd]",base),key)
                    args=[7 if token=="%d" else "Sample" for token in re.findall(r"%[sd]",base)]
                    lua.eval("string.format")(translated,*args)

    def test_all_locales_open_the_actual_native_ui(self):
        from test_addon import AddonTests
        for locale in ("enUS","frFR","deDE","esES","esMX","itIT","ptBR","ruRU","koKR","zhCN","zhTW"):
            with self.subTest(locale=locale):
                addon=AddonTests(); addon.setUp()
                addon.lua.globals().SVC.locale=locale
                addon.open_ui()
                addon.lua.execute('SVC:ShowGuide(); SVC:ShowCompanion(); SVC:ShowPage("requests"); SVC:ShowDiff(); SVC.frame:SetSize(1040,680); SVC:Layout()')

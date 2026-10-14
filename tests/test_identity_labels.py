import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent.parent/"companion"))
from lua_data import identity


class IdentityLabelTests(unittest.TestCase):
    def test_guide_and_character_names_do_not_lock_entire_databases(self):
        self.assertFalse(identity("RXPGuidesDB"))
        self.assertFalse(identity("Guido-Player-1-ABC"))
        self.assertFalse(identity("valid"))
        for key in ("questId","playerGUID","GUIDs","cachedGuidValue","cached_guid_value"):
            self.assertTrue(identity(key),key)

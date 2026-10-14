import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "companion"))
from lua_data import DataError, Table, at, differences, dump, identity, merge_values, parse, token, untoken


class ParserTests(unittest.TestCase):
    def test_roundtrip_unicode_binary_control_and_sparse_keys(self):
        roots = parse('''DB = { [true] = "bool", [1] = "number", ["1"] = "text", [9007199254740993] = 42, ["msg"] = "Éléonore\\000\\255\\010", ["a"] = { [12] = 3, [99] = false } }''')
        restored = parse(dump(roots))
        self.assertEqual(restored, roots)
        db = restored.get("DB")
        self.assertEqual(db.get(True), "bool")
        self.assertEqual(db.get(1), "number")
        self.assertEqual(db.get("1"), "text")
        self.assertEqual(untoken(token(9007199254740993)), 9007199254740993)

    def test_long_strings_comments_arrays_exponents(self):
        roots = parse('--[=[comment]=]\nDB = { key = [==[\ntext ]] more]==], "a", -- line\n "b", 1.25e2, [9] = 0xF }; Nil = nil')
        db = roots.get("DB")
        self.assertEqual(db.get("key"), "text ]] more")
        self.assertEqual(db.get(1), "a")
        self.assertEqual(db.get(2), "b")
        self.assertEqual(db.get(3), 125)
        self.assertFalse(roots.has("Nil"))
        self.assertEqual(parse(dump(roots)), roots)

    def test_never_executes_lua_code(self):
        for source in ('DB = os.execute("x")', 'DB = function() end', 'DB = setmetatable({}, {})', 'require("x")', 'DB = 2 + 3', 'DB = { [nil] = 3 }'):
            with self.subTest(source=source), self.assertRaises(DataError):
                parse(source)

    def test_bad_strings_and_number_overflow(self):
        for source in ('DB = "\\999"', 'DB = "unterminated', 'DB = 1e999', 'DB = { a = 3'):
            with self.subTest(source=source), self.assertRaises(DataError):
                parse(source)

    def test_typed_paths(self):
        roots = parse('DB = { [true] = 9, [1] = 7, ["1"] = 5 }')
        self.assertEqual(at(roots, [token("DB"), token(True)]), 9)
        self.assertEqual(at(roots, [token("DB"), token(1)]), 7)
        self.assertEqual(at(roots, [token("DB"), token("1")]), 5)

    def test_merge_preserves_target_keys_and_nested_identity(self):
        source = parse('DB = { GUID = "Player-1-A", nested = { characterID = 9, step = 42, extra = 3 }, [5] = true, scale = "bad" }').get("DB")
        target = parse('DB = { GUID = "Player-1-B", nested = { characterID = 8, step = 16, onlyB = 4 }, [5] = false, scale = 1 }').get("DB")
        result, count = merge_values(source, target)
        self.assertEqual(count, 2)
        self.assertEqual(result.get("GUID"), "Player-1-B")
        self.assertEqual(result.get("nested").get("characterID"), 8)
        self.assertEqual(result.get("nested").get("step"), 42)
        self.assertFalse(result.get("nested").has("extra"))
        self.assertEqual(result.get("nested").get("onlyB"), 4)
        self.assertEqual(result.get("scale"), 1)
        self.assertEqual([k for k, _ in result.entries], [k for k, _ in target.entries])

    def test_diff_protection_and_missing_paths(self):
        left = parse('DB = { GUID = "Player-1-A", name = "A", progress = 4, missing = { a = 2 } }').get("DB")
        right = parse('DB = { GUID = "Player-1-B", name = "B", progress = 3 }').get("DB")
        rows = {row["path"][0]["value"]: row for row in differences(left, right)}
        self.assertTrue(rows["GUID"]["protected"])
        self.assertFalse(rows["GUID"]["copyable"])
        self.assertTrue(rows["progress"]["copyable"])
        self.assertFalse(rows["missing"]["copyable"])

    def test_ancestor_identity(self):
        from lua_data import safe_path
        roots = parse('DB = { identityGUID = { value = 3 } }')
        with self.assertRaises(DataError):
            safe_path(roots, [token("DB"), token("identityGUID"), token("value")])


if __name__ == "__main__":
    unittest.main()

"""Run all tests; CI must never silently skip the Lua behavior checks."""
import sys
import unittest
from pathlib import Path


def main():
    try:
        from lupa.lua51 import LuaRuntime
        LuaRuntime().execute('assert(_VERSION == "Lua 5.1")')
    except ImportError:
        raise SystemExit("Install test dependencies: python -m pip install -r requirements-dev.txt")
    suite = unittest.defaultTestLoader.discover(str(Path(__file__).resolve().parent))
    if not suite.countTestCases():
        raise SystemExit("No tests discovered")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.skipped:
        print("Skipped tests are forbidden in CI:", result.skipped, file=sys.stderr)
    return 0 if result.wasSuccessful() and not result.skipped else 1


if __name__ == "__main__":
    sys.exit(main())

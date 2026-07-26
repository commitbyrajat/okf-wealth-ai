from __future__ import annotations

import sys
import unittest
from pathlib import Path


def main() -> int:
    project_root = Path(__file__).resolve().parents[2]
    tests_dir = project_root / "tests"
    suite = unittest.defaultTestLoader.discover(str(tests_dir))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())

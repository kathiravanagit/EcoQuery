"""
Validate the model catalog and print its version.

Standalone entry point so the check runs outside pytest -- CI, a pre-commit
hook, or `npm run validate:models` from the repo root. `tests/test_model_catalog.py`
remains the specification and runs the same invariants; this is the form you
can run without a test runner.

    python validate_models.py            validate, print digest
    python validate_models.py --json     machine-readable
    python validate_models.py --quiet    only report problems

Exit code 0 when the catalog is sound, 1 when it is not.
"""

import json
import os
import sys

# Allow `python backend/validate_models.py` from the repo root as well as
# `python validate_models.py` from inside backend/.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from catalog_version import catalog_version, validate_catalog  # noqa: E402


def main(argv: list[str]) -> int:
    quiet = "--quiet" in argv
    as_json = "--json" in argv

    problems = validate_catalog()
    version = catalog_version()

    if as_json:
        print(json.dumps(
            {"ok": not problems, "version": version, "problems": problems},
            indent=2,
        ))
        return 1 if problems else 0

    if problems:
        print(f"Model catalog is INVALID ({len(problems)} problem(s)):", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        print("", file=sys.stderr)
        print(f"catalog_version: {version['digest']} ({version['entry_count']} entries)", file=sys.stderr)
        return 1

    if not quiet:
        print(f"Model catalog OK: {version['entry_count']} entries")
        print(f"catalog_version: {version['digest']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

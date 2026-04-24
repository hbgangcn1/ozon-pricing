"""Coverage runner for db.plans on Python 3.13 + bcrypt cp39-abi3 stack.

Background
----------
``pytest --cov=db.plans`` (and ``coverage run --source=db.plans -m pytest ...``)
fails on this stack with::

    ImportError: PyO3 modules compiled for CPython 3.8 or older may only be
    initialized once per interpreter process

The trigger is NOT the tracer backend (sysmon / ctrace / pytrace all fail
identically) and NOT the pytest-cov subprocess combine step. Root cause
verified by Oracle bg_847cfadd:

1. ``coverage.Coverage(source=['db.plans']).start()`` calls
   ``InOrOut.__init__`` which iterates ``source_pkgs`` and invokes
   ``file_and_path_for_module(pkg)`` -> ``importlib.util.find_spec(pkg)``.
2. ``find_spec('db.plans')`` side-effect imports the parent package,
   executing ``db/__init__.py`` -> ``from db.users import ...`` ->
   ``db/users.py:5 import bcrypt``. The bcrypt PyO3 extension initializes
   for the first time.
3. The probe runs inside ``with sys_modules_saved():`` (coverage/misc.py),
   which deletes everything imported during the probe from ``sys.modules``
   when the block exits.
4. When test code (or conftest) later runs ``import bcrypt`` for real,
   Python sees no entry in ``sys.modules`` and asks the loader to
   initialize the extension again. The cp39-abi3 wheel rejects this
   second init -> ImportError.

Workaround
----------
Pre-import ``bcrypt`` at module top BEFORE creating the Coverage object.
After the first init, even when ``sys_modules_saved()`` deletes the
``sys.modules`` entry, the underlying PyO3 extension is already
registered in the process. The post-probe ``import bcrypt`` then becomes
a normal cache miss that re-binds to the existing extension without
triggering a second init.

Usage
-----
Windows::

    .\\.venv\\Scripts\\python.exe .\\scripts\\run_db_plans_cov.py

Ubuntu::

    ./.venv/bin/python ./scripts/run_db_plans_cov.py

Exits with the pytest return code. Writes coverage data to
``.coverage.dbplans`` (separate from the default ``.coverage`` to avoid
WinError 32 file locks under OneDrive).

References
----------
- pytest-dev/pytest-cov#614 (open) - --cov=<dotted module> + PyO3 ext.
- pyca/bcrypt#694 (open) - same ImportError on CPython 3.13.
- coveragepy/coveragepy#1306 (open) - sys_modules_saved re-import hazard.
- PyO3/pyo3#2523 (merged) - "only allow initializing once per process".
"""
from __future__ import annotations

# CRITICAL: pre-import bcrypt before any coverage machinery touches sys.modules.
# See module docstring for the PyO3 single-init root cause.
import bcrypt  # noqa: F401  # imported for PyO3 init side effect only
import pathlib

import coverage
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / ".coverage.dbplans"
INCLUDE_PATTERNS = ["*db\\plans.py", "*/db/plans.py"]


def main() -> int:
    """Run tests/test_db_plans.py under coverage and report db/plans.py."""
    cov = coverage.Coverage(
        source=["db.plans"],
        data_file=str(DATA_FILE),
        config_file=False,
    )
    cov.start()
    try:
        rc = pytest.main([
            "tests/test_db_plans.py",
            "-p", "no:cov",
            "-p", "no:cacheprovider",
        ])
    finally:
        cov.stop()
        cov.save()

    cov.report(include=INCLUDE_PATTERNS)
    return int(rc)


if __name__ == "__main__":
    raise SystemExit(main())

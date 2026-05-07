"""Repository-wide grep guards for trial/overflow invariants (Task 7.8).

Two invariants enforced:

  G1: Logistics rule filtering MUST always combine ``is_active == 1`` with
      ``disabled_by_overflow == 0``. Naked ``is_active == 1`` filters bypass
      the overflow gating and would surface auto-disabled rules during the
      48h reselect window.

  G2: ``users.subscription_type`` MUST only be written via
      ``db.subscriptions.apply_subscription_change``. Direct writes elsewhere
      bypass trial-overlay reset, plan-change audit logging, and overflow
      window opening on downgrade.
"""
import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
EXCLUDED_DIRS = {".venv", "venv", "node_modules", ".git", "alembic", "migrations",
                 "__pycache__", "frontend", ".pytest_cache", "tests",
                 "openspec", "deploy", "scripts", "docs"}


def _iter_py_files():
    for p in REPO_ROOT.rglob("*.py"):
        parts = set(p.relative_to(REPO_ROOT).parts)
        if parts & EXCLUDED_DIRS:
            continue
        yield p


def test_no_naked_is_active_filter_on_logistics():
    pattern = re.compile(r"Logistics\.is_active\s*==\s*1")
    pattern_with_overflow = re.compile(r"disabled_by_overflow")
    allowed_files = {Path("services") / "overflow_service.py"}
    offenders = []
    for p in _iter_py_files():
        rel = p.relative_to(REPO_ROOT)
        if rel in allowed_files:
            continue
        text = p.read_text(encoding="utf-8")
        if not pattern.search(text):
            continue
        if not pattern_with_overflow.search(text):
            offenders.append(str(rel))
    assert not offenders, (
        "Logistics.is_active == 1 must be paired with disabled_by_overflow == 0 "
        f"in: {offenders}"
    )


def test_subscription_type_writes_only_via_apply_subscription_change():
    write_pattern = re.compile(
        r"\.subscription_type\s*=\s*[\"'a-zA-Z]"
    )
    offenders = []
    allowed_files = {
        Path("db") / "subscriptions.py",
        Path("services") / "trial_service.py",
    }
    for p in _iter_py_files():
        rel = p.relative_to(REPO_ROOT)
        if rel in allowed_files:
            continue
        text = p.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            if write_pattern.search(line):
                offenders.append(f"{rel}:{i}: {line.strip()}")
    assert not offenders, (
        "Direct writes to user.subscription_type are forbidden outside "
        f"db/subscriptions.apply_subscription_change. Offenders:\n"
        + "\n".join(offenders)
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))

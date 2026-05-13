from datetime import datetime, timezone
from types import SimpleNamespace

from db.subscriptions import get_effective_tier


def _epoch(dt: datetime) -> int:
    return int(dt.timestamp())


def _user(plan, expires_at):
    return SimpleNamespace(subscription_type=plan, subscription_expires=expires_at)


def test_paid_with_future_expiry_returns_paid_plan():
    now = datetime.now(timezone.utc)

    assert get_effective_tier(
        _user("professional", _epoch(now) + 3600), now=now,
    ) == "professional"


def test_paid_with_past_expiry_returns_free():
    now = datetime.now(timezone.utc)

    assert get_effective_tier(
        _user("professional", _epoch(now) - 3600), now=now,
    ) == "free"


def test_paid_with_no_expiry_returns_paid_plan():
    now = datetime.now(timezone.utc)

    assert get_effective_tier(_user("enterprise", None), now=now) == "enterprise"


def test_free_returns_free():
    now = datetime.now(timezone.utc)

    assert get_effective_tier(_user("free", None), now=now) == "free"

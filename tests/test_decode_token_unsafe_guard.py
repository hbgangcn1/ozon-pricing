from datetime import timedelta

import pytest

from security.tokens import (
    create_access_token,
    decode_token_unsafe_for_testing,
)


def _expired_access_token() -> str:
    return create_access_token(
        user_id=123,
        username="unsafe_guard_user",
        expires_delta=timedelta(seconds=-1),
    )


def test_decode_token_unsafe_raises_without_testing_env(monkeypatch):
    monkeypatch.delenv("E2E_TEST", raising=False)
    monkeypatch.delenv("LOGISTICS_TESTING", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    with pytest.raises(
        RuntimeError,
        match="decode_token_unsafe must NOT be used outside testing",
    ):
        decode_token_unsafe_for_testing(_expired_access_token())


def test_decode_token_unsafe_allows_e2e_test_env(monkeypatch):
    monkeypatch.setenv("E2E_TEST", "1")
    monkeypatch.delenv("LOGISTICS_TESTING", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    payload = decode_token_unsafe_for_testing(_expired_access_token())

    assert payload["sub"] == "123"
    assert payload["username"] == "unsafe_guard_user"


def test_decode_token_unsafe_allows_logistics_testing_env(monkeypatch):
    monkeypatch.delenv("E2E_TEST", raising=False)
    monkeypatch.setenv("LOGISTICS_TESTING", "1")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    payload = decode_token_unsafe_for_testing(_expired_access_token())

    assert payload["sub"] == "123"
    assert payload["username"] == "unsafe_guard_user"

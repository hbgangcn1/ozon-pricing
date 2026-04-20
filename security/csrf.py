import secrets

_CSRF_TOKEN_BYTES = 32


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(_CSRF_TOKEN_BYTES)

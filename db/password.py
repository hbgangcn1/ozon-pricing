import hashlib
import logging

import bcrypt

logger = logging.getLogger(__name__)


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        result = verify_legacy_password(password, hashed_password)
        if result:
            logger.warning(
                "User authenticated via deprecated SHA-256 hash. "
                "Password should be migrated to bcrypt."
            )
        return result


def verify_legacy_password(password: str, hashed_password: str) -> bool:
    """Verify password against legacy SHA-256 hash (deprecated)."""
    legacy_hash = hashlib.sha256(password.encode()).hexdigest()
    return legacy_hash == hashed_password


def is_bcrypt_hash(hashed_password: str) -> bool:
    return hashed_password.startswith("$2b$") or hashed_password.startswith("$2a$")

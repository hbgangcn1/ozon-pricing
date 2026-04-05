import hashlib
from db.password import hash_password, verify_password, is_bcrypt_hash


def test_hash_and_verify_bcrypt_roundtrip():
    pwd = "Secur3-P@ssw0rd-XYZ"
    hashed = hash_password(pwd)
    assert hashed.startswith("$2")
    assert is_bcrypt_hash(hashed) is True
    assert verify_password(pwd, hashed) is True
    assert verify_password("wrong", hashed) is False


def test_sha256_legacy_verify():
    legacy_pwd = "Legacy-1234!@#"
    legacy_hash = hashlib.sha256(legacy_pwd.encode()).hexdigest()

    assert verify_password(legacy_pwd, legacy_hash) is True
    assert verify_password("wrong_password", legacy_hash) is False

    bcrypt_hash = hash_password(legacy_pwd)
    assert is_bcrypt_hash(bcrypt_hash) is True
    assert verify_password(legacy_pwd, bcrypt_hash) is True

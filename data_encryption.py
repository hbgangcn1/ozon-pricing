# -*- coding: utf-8 -*-
"""
数据加密模块（高优先级安全改进）
提供数据库敏感字段加密功能
"""

import os
import base64
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class DataEncryption:
    """数据加密类（高优先级安全改进）"""

    _fernet: Optional[Fernet] = None
    _encryption_key: Optional[bytes] = None

    @classmethod
    def _get_encryption_key(cls) -> bytes:
        """
        获取或生成加密密钥

        优先从环境变量读取，否则生成新密钥
        """
        if cls._encryption_key is not None:
            return cls._encryption_key

        # 从环境变量读取密钥
        env_key = os.getenv('ENCRYPTION_KEY')
        if env_key:
            try:
                cls._encryption_key = base64.urlsafe_b64decode(
                    env_key.encode())
            except (ValueError, TypeError):
                # 如果环境变量格式错误，生成新密钥
                pass

        # 如果没有环境变量，尝试从密钥文件读取
        if cls._encryption_key is None:
            key_file = os.getenv('ENCRYPTION_KEY_FILE', '.encryption_key')
            if os.path.exists(key_file):
                try:
                    with open(key_file, 'rb') as f:
                        cls._encryption_key = f.read()
                except (IOError, OSError, PermissionError):
                    pass

        # 如果仍然没有密钥，生成新密钥（不推荐，但为了兼容性）
        if cls._encryption_key is None:
            # 警告：生产环境必须设置ENCRYPTION_KEY环境变量
            import warnings
            warnings.warn(
                "未设置ENCRYPTION_KEY环境变量，使用临时密钥。"
                "生产环境必须设置ENCRYPTION_KEY！",
                UserWarning
            )
            # 使用固定密码派生密钥（仅用于开发）
            password = os.getenv(
                'MASTER_PASSWORD',
                'default_dev_password_change_in_production'
            ).encode()
            salt = b'logistics_salt_2024'  # 固定salt（开发用）
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            cls._encryption_key = base64.urlsafe_b64encode(
                kdf.derive(password))

        return cls._encryption_key

    @classmethod
    def _get_fernet(cls) -> Fernet:
        """获取Fernet加密对象"""
        if cls._fernet is None:
            key = cls._get_encryption_key()
            cls._fernet = Fernet(key)
        return cls._fernet

    @classmethod
    def encrypt(cls, data: str) -> str:
        """
        加密字符串数据

        Args:
            data: 待加密的字符串

        Returns:
            加密后的base64编码字符串
        """
        if not data:
            return ""

        fernet = cls._get_fernet()
        encrypted = fernet.encrypt(data.encode('utf-8'))
        return base64.urlsafe_b64encode(encrypted).decode('utf-8')

    @classmethod
    def decrypt(cls, encrypted_data: str) -> str:
        """
        解密字符串数据

        Args:
            encrypted_data: 加密后的base64编码字符串

        Returns:
            解密后的原始字符串
        """
        if not encrypted_data:
            return ""

        try:
            fernet = cls._get_fernet()
            decoded = base64.urlsafe_b64decode(
                encrypted_data.encode('utf-8'))
            decrypted = fernet.decrypt(decoded)
            return decrypted.decode('utf-8')
        except Exception as e:
            # 如果解密失败，可能是未加密的数据（向后兼容）
            import warnings
            warnings.warn(f"解密失败，可能数据未加密: {e}")
            return encrypted_data

    @classmethod
    def encrypt_field(cls, field_value: Optional[str]) -> Optional[str]:
        """
        加密字段值（处理None值）

        Args:
            field_value: 字段值

        Returns:
            加密后的值，如果输入为None则返回None
        """
        if field_value is None:
            return None
        return cls.encrypt(str(field_value))

    @classmethod
    def decrypt_field(cls, encrypted_value: Optional[str]) -> Optional[str]:
        """
        解密字段值（处理None值）

        Args:
            encrypted_value: 加密后的值

        Returns:
            解密后的值，如果输入为None则返回None
        """
        if encrypted_value is None:
            return None
        return cls.decrypt(str(encrypted_value))


# 便捷函数
def encrypt_data(data: str) -> str:
    """加密数据（便捷函数）"""
    return DataEncryption.encrypt(data)


def decrypt_data(encrypted_data: str) -> str:
    """解密数据（便捷函数）"""
    return DataEncryption.decrypt(encrypted_data)

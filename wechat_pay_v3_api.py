# -*- coding: utf-8 -*-
"""微信支付v3 API接口模块。"""

import base64
import binascii
import json
import logging
import os
import secrets
import time
from typing import Any, Dict, Optional, Type

import asyncio  # noqa: F401  # PERF-W13-01: reserved for future async migration
import requests
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from wechat_pay_config import wechat_config

logger = logging.getLogger(__name__)


class PlatformSignatureError(Exception):
    """Base platform signature verification failure."""


class SignatureVerificationError(PlatformSignatureError):
    """Inbound or outbound platform signature verification failed."""


class WechatResponseSignatureError(PlatformSignatureError):
    """Outbound WeChat API response signature verification failed."""


class WeChatPayError(Exception):
    """WeChat Pay processing failed."""


class WeChatPayV3API:
    """微信支付v3 API类。"""

    NOTIFY_NONCE_TTL_SECONDS = 600

    def __init__(self, config=None):
        self.config = config or wechat_config
        self._private_key = None
        self._cert_serial_no = self.config.cert_serial_no
        self._debug = os.getenv("WECHAT_PAY_DEBUG", "false").lower() == "true"

    def _load_private_key(self) -> Optional[rsa.RSAPrivateKey]:
        if self._private_key is not None:
            return self._private_key
        if not self.config.private_key_path:
            return None
        if not os.path.exists(self.config.private_key_path):
            return None
        try:
            with open(self.config.private_key_path, "rb") as key_file:
                private_key = serialization.load_pem_private_key(
                    key_file.read(), password=None, backend=default_backend()
                )
            if isinstance(private_key, rsa.RSAPrivateKey):
                self._private_key = private_key
                return private_key
            return None
        except (OSError, IOError, ValueError, TypeError):
            logger.warning("加载商户私钥失败", exc_info=True)
            return None

    @staticmethod
    def _get_timestamp() -> str:
        return str(int(time.time()))

    @staticmethod
    def _get_nonce_str() -> str:
        return secrets.token_urlsafe(32)

    def _build_signature(
        self, method: str, url_path: str, timestamp: str, nonce_str: str, body: str = ""
    ) -> str:
        sign_str = f"{method}\n{url_path}\n{timestamp}\n{nonce_str}\n{body}\n"
        private_key = self._load_private_key()
        if not private_key:
            raise Exception("商户私钥未配置或加载失败")
        signature = private_key.sign(
            sign_str.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256()
        )
        return base64.b64encode(signature).decode("utf-8")

    def _build_auth_header(
        self, method: str, url_path: str, body: str = ""
    ) -> Dict[str, str]:
        timestamp = self._get_timestamp()
        nonce_str = self._get_nonce_str()
        signature = self._build_signature(method, url_path, timestamp, nonce_str, body)
        auth_str = (
            f"WECHATPAY2-SHA256-RSA2048 "
            f'mchid="{self.config.mch_id}",'
            f'nonce_str="{nonce_str}",'
            f'signature="{signature}",'
            f'timestamp="{timestamp}",'
            f'serial_no="{self._cert_serial_no}"'
        )
        return {
            "Authorization": auth_str,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _extract_header(self, headers: Dict[str, Any], name: str) -> str:
        value = headers.get(name)
        if value is None:
            raise SignatureVerificationError(f"缺少签名头: {name}")
        if not isinstance(value, str):
            value = str(value)
        if not value:
            raise SignatureVerificationError(f"缺少签名头: {name}")
        if "," in value:
            raise SignatureVerificationError(f"签名头格式非法: {name}")
        return value

    @staticmethod
    def _build_platform_sign_message(timestamp: str, nonce: str, raw_body: bytes) -> bytes:
        return b"\n".join(
            [timestamp.encode("utf-8"), nonce.encode("utf-8"), raw_body, b""]
        )

    @staticmethod
    def _decode_platform_signature(signature: str) -> bytes:
        try:
            return base64.b64decode(signature)
        except (binascii.Error, ValueError) as exc:
            raise SignatureVerificationError("平台签名格式非法") from exc

    def verify_platform_signature(self, headers: dict, raw_body: bytes) -> None:
        timestamp = self._extract_header(headers, "Wechatpay-Timestamp")
        nonce = self._extract_header(headers, "Wechatpay-Nonce")
        signature = self._extract_header(headers, "Wechatpay-Signature")
        serial = self._extract_header(headers, "Wechatpay-Serial")
        try:
            timestamp_value = int(timestamp)
        except ValueError as exc:
            raise SignatureVerificationError("签名时间戳格式非法") from exc
        if abs(time.time() - timestamp_value) > 300:
            raise SignatureVerificationError("签名时间戳已过期")
        platform_public_key_id = self.config.platform_public_key_id
        if not platform_public_key_id:
            raise SignatureVerificationError("平台公钥ID未配置")
        if serial != platform_public_key_id:
            logger.critical(
                "wechatpay serial mismatch: incoming=%s expected=%s",
                serial,
                platform_public_key_id,
            )
            raise SignatureVerificationError("平台证书序列号不匹配")
        public_key = self.config.platform_public_key
        if not isinstance(public_key, rsa.RSAPublicKey):
            raise SignatureVerificationError("平台公钥未加载")
        sign_str = self._build_platform_sign_message(timestamp, nonce, raw_body)
        try:
            public_key.verify(
                self._decode_platform_signature(signature),
                sign_str,
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
        except Exception as exc:
            raise SignatureVerificationError("平台签名验证失败") from exc

    def _is_notify_nonce_replay(self, nonce: str) -> bool:
        """使用 Redis 原子占位检测回调 nonce 重放；Redis 不可用时 fail-open。"""
        try:
            from redis_cache import get_redis_client

            client = get_redis_client()
            if client is None:
                logger.warning("Redis不可用，跳过微信回调nonce重放检查")
                return False
            key = f"wxpay:nonce:{nonce}"
            stored = client.set(
                key,
                "1",
                ex=self.NOTIFY_NONCE_TTL_SECONDS,
                nx=True,
            )
            return not bool(stored)
        except Exception:
            logger.warning("微信回调nonce重放检查异常，按fail-open放行", exc_info=True)
            return False

    def _parse_verified_response(
        self,
        response,
        error_cls: Type[WechatResponseSignatureError],
    ):
        raw_body = response.content or b""
        try:
            self.verify_platform_signature(dict(response.headers), raw_body)
        except SignatureVerificationError as exc:
            raise error_cls(str(exc)) from exc
        if not raw_body:
            return {}
        try:
            return json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise error_cls("微信响应JSON解析失败") from exc

    def _handle_api_error(self, response) -> Dict[str, Any]:
        try:
            error_info = self._parse_verified_response(
                response, WechatResponseSignatureError
            )
        except WechatResponseSignatureError:
            raise
        return {
            "success": False,
            "message": error_info.get("message", f"HTTP {response.status_code}"),
        }

    def create_jsapi_order(
        self, order_id: str, total_amount: int, description: str, openid: str, **kwargs
    ) -> Dict[str, Any]:
        url = f"{self.config.jsapi_pay_url}/{order_id}"
        url_path = f"/v3/pay/transactions/jsapi/{order_id}"
        data = {
            "appid": self.config.app_id,
            "mchid": self.config.mch_id,
            "description": description,
            "out_trade_no": order_id,
            "amount": {"total": total_amount, "currency": "CNY"},
            "payer": {"openid": openid},
            "notify_url": self.config.notify_url,
        }
        for key in ("time_expire", "attach", "goods_tag"):
            if key in kwargs:
                data[key] = kwargs[key]
        body = json.dumps(data, separators=(",", ":"))
        try:
            headers = self._build_auth_header("POST", url_path, body)
            # PERF-W13-01: requests.post is blocking; this method is sync by
            # design. All async callers MUST wrap with asyncio.to_thread (see
            # api/routes/payment.py:305). TODO: 异步化调用链 — migrate to
            # httpx.AsyncClient when call sites are unified.
            response = requests.post(url, data=body, headers=headers, timeout=30)
            if response.status_code == 200:
                result = self._parse_verified_response(
                    response, WechatResponseSignatureError
                )
                return {
                    "success": True,
                    "prepay_id": result.get("prepay_id"),
                    "data": result,
                }
            return self._handle_api_error(response)
        except WechatResponseSignatureError:
            raise
        except Exception as exc:
            logger.error("JSAPI下单失败: %s", exc, exc_info=True)
            return {"success": False, "message": f"网络请求失败: {str(exc)}"}

    def create_native_order(
        self, order_id: str, total_amount: int, description: str, **kwargs
    ) -> Dict[str, Any]:
        url = self.config.native_pay_url
        url_path = "/v3/pay/transactions/native"
        data = {
            "appid": self.config.app_id,
            "mchid": self.config.mch_id,
            "description": description,
            "out_trade_no": order_id,
            "amount": {"total": total_amount, "currency": "CNY"},
            "notify_url": self.config.notify_url,
        }
        for key in ("time_expire", "attach", "goods_tag"):
            if key in kwargs:
                data[key] = kwargs[key]
        body = json.dumps(data, separators=(",", ":"))
        try:
            headers = self._build_auth_header("POST", url_path, body)
            # PERF-W13-01: blocking I/O — async callers wrap with to_thread.
            response = requests.post(url, data=body, headers=headers, timeout=30)
            if response.status_code == 200:
                result = self._parse_verified_response(
                    response, WechatResponseSignatureError
                )
                return {
                    "success": True,
                    "code_url": result.get("code_url"),
                    "data": result,
                }
            return self._handle_api_error(response)
        except WechatResponseSignatureError:
            raise
        except Exception as exc:
            logger.error("Native下单失败: %s", exc, exc_info=True)
            return {"success": False, "message": f"网络请求失败: {str(exc)}"}

    def query_order(self, order_id: str) -> Dict[str, Any]:
        url = f"{self.config.order_query_url}/{order_id}?mchid={self.config.mch_id}"
        url_path = f"/v3/pay/transactions/out-trade-no/{order_id}"
        try:
            headers = self._build_auth_header("GET", url_path)
            # PERF-W13-01: blocking I/O — async callers wrap with to_thread.
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                result = self._parse_verified_response(
                    response, WechatResponseSignatureError
                )
                return {
                    "success": True,
                    "trade_state": result.get("trade_state"),
                    "trade_state_desc": result.get("trade_state_desc"),
                    "data": result,
                }
            return self._handle_api_error(response)
        except WechatResponseSignatureError:
            raise
        except Exception as exc:
            logger.error("查询订单失败: %s", exc, exc_info=True)
            return {"success": False, "message": f"网络请求失败: {str(exc)}"}

    def verify_notify_signature(
        self, timestamp: str, nonce: str, body: str, signature: str
    ) -> bool:
        _ = timestamp, nonce, body, signature
        raise NotImplementedError("请改用平台公钥签名验证")

    def _decrypt_resource(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        try:
            ciphertext = resource.get("ciphertext", "")
            associated_data = resource.get("associated_data", "")
            nonce = resource.get("nonce", "")
            if not all([ciphertext, associated_data, nonce]):
                return {}
            api_key = self.config.api_v3_key
            if len(api_key) != 32:
                return {}
            aesgcm = AESGCM(api_key.encode("utf-8"))
            decrypted_data = aesgcm.decrypt(
                nonce.encode("utf-8"),
                base64.b64decode(ciphertext),
                associated_data.encode("utf-8"),
            )
            return json.loads(decrypted_data.decode("utf-8"))
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            logger.warning("解密回调数据失败", exc_info=True)
            return {}

    def process_notify(self, headers: Dict[str, Any], body: bytes) -> dict | None:
        """处理微信支付回调通知。

        Returns:
            payload: 解析并解密后的通知数据；非成功事件或重放通知时为 None。
        """
        try:
            self.verify_platform_signature(headers, body)
        except SignatureVerificationError as exc:
            logger.warning("【安全告警】支付回调签名验证失败: %s", exc, exc_info=True)
            raise WeChatPayError("signature verification failed") from exc

        nonce = self._extract_header(headers, "Wechatpay-Nonce")
        if self._is_notify_nonce_replay(nonce):
            logger.warning("【安全告警】微信支付回调nonce重放: %s", nonce)
            return None

        try:
            notify_data = json.loads(body.decode("utf-8"))
            if notify_data.get("event_type") != "TRANSACTION.SUCCESS":
                return None
            decrypted_data = self._decrypt_resource(notify_data.get("resource", {}))
            if not decrypted_data:
                raise WeChatPayError("notify resource decryption failed")
            return decrypted_data
        except Exception as exc:
            if isinstance(exc, WeChatPayError):
                raise
            logger.warning("处理支付通知失败: %s", exc, exc_info=True)
            raise WeChatPayError("notify processing failed") from exc

    def verify_notify_signature_with_public_key(
        self, timestamp: str, nonce: str, body: str, signature: str, serial: str = ""
    ) -> bool:
        headers = {
            "Wechatpay-Timestamp": timestamp,
            "Wechatpay-Nonce": nonce,
            "Wechatpay-Signature": signature,
            "Wechatpay-Serial": serial or self.config.platform_public_key_id or "",
        }
        try:
            self.verify_platform_signature(headers, body.encode("utf-8"))
            return True
        except SignatureVerificationError:
            logger.warning("验证回调签名失败", exc_info=True)
            return False


wechat_pay_v3 = WeChatPayV3API()

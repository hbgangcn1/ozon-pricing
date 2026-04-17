# -*- coding: utf-8 -*-
"""
微信支付v3 API接口模块
实现微信支付v3的核心功能：统一下单、查询订单、退款等
"""

import json
import time
import hashlib
import hmac
import base64
import os
import secrets
import logging
from typing import Dict, Optional, Any
import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend
from wechat_pay_config import wechat_config

# 配置日志
logger = logging.getLogger(__name__)


class WeChatPayV3API:
    """微信支付v3 API类"""

    def __init__(self, config=None):
        """
        初始化微信支付v3 API

        Args:
            config: 微信支付配置对象，默认使用全局配置
        """
        self.config = config or wechat_config
        self._private_key = None
        self._cert_serial_no = self.config.cert_serial_no
        # 调试开关：仅当 WECHAT_PAY_DEBUG=true 时输出详细日志
        self._debug = os.getenv("WECHAT_PAY_DEBUG", "false").lower() == "true"

        # 完全移除敏感信息输出，即使是在调试模式下
        # 如需调试，请通过其他方式查看配置信息

    def _load_private_key(self) -> Optional[rsa.RSAPrivateKey]:
        """加载商户私钥"""
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
                # 确保返回的是RSA私钥
                if isinstance(private_key, rsa.RSAPrivateKey):
                    self._private_key = private_key
                    return self._private_key
                else:
                    return None
        except (OSError, IOError, ValueError, TypeError):
            return None

    @staticmethod
    def _get_timestamp() -> str:
        """获取当前时间戳（秒）"""
        return str(int(time.time()))

    @staticmethod
    def _get_nonce_str() -> str:
        """生成随机字符串"""
        return secrets.token_urlsafe(32)

    def _build_signature(
        self, method: str, url_path: str, timestamp: str, nonce_str: str, body: str = ""
    ) -> str:
        """
        构建请求签名

        Args:
            method: HTTP方法
            url_path: 请求路径
            timestamp: 时间戳
            nonce_str: 随机字符串
            body: 请求体

        Returns:
            str: 签名字符串
        """
        # 构建签名字符串
        sign_str = f"{method}\n{url_path}\n{timestamp}\n{nonce_str}\n{body}\n"
        # 完全移除签名字符串输出，即使是摘要形式

        # 使用商户私钥签名
        private_key = self._load_private_key()
        if not private_key:
            raise Exception("商户私钥未配置或加载失败")

        # 使用SHA256withRSA签名
        signature = private_key.sign(
            sign_str.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256()
        )

        # Base64编码
        signature_b64 = base64.b64encode(signature).decode("utf-8")
        # 完全移除签名结果输出
        return signature_b64

    def _build_auth_header(
        self, method: str, url_path: str, body: str = ""
    ) -> Dict[str, str]:
        """
        构建Authorization请求头

        Args:
            method: HTTP方法
            url_path: 请求路径
            body: 请求体

        Returns:
            Dict[str, str]: 请求头字典
        """
        timestamp = self._get_timestamp()
        nonce_str = self._get_nonce_str()

        # 构建签名
        signature = self._build_signature(method, url_path, timestamp, nonce_str, body)

        # 构建Authorization头 - 微信支付v3 API格式
        auth_str = (
            f"WECHATPAY2-SHA256-RSA2048 "
            f'mchid="{self.config.mch_id}",'
            f'nonce_str="{nonce_str}",'
            f'signature="{signature}",'
            f'timestamp="{timestamp}",'
            f'serial_no="{self._cert_serial_no}"'
        )

        # 调试信息（脱敏）
        # 完全移除Authorization头和证书信息输出

        return {
            "Authorization": auth_str,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def create_jsapi_order(
        self, order_id: str, total_amount: int, description: str, openid: str, **kwargs
    ) -> Dict[str, Any]:
        """
        创建JSAPI支付订单

        Args:
            order_id: 商户订单号
            total_amount: 订单金额（分）
            description: 商品描述
            openid: 用户openid
            **kwargs: 其他参数

        Returns:
            Dict[str, Any]: 订单创建结果
        """
        url = f"{self.config.jsapi_pay_url}/{order_id}"
        url_path = f"/v3/pay/transactions/jsapi/{order_id}"

        # 构建请求体
        data = {
            "appid": self.config.app_id,
            "mchid": self.config.mch_id,
            "description": description,
            "out_trade_no": order_id,
            "amount": {"total": total_amount, "currency": "CNY"},
            "payer": {"openid": openid},
            "notify_url": self.config.notify_url,
        }

        # 添加可选参数
        if "time_expire" in kwargs:
            data["time_expire"] = kwargs["time_expire"]
        if "attach" in kwargs:
            data["attach"] = kwargs["attach"]
        if "goods_tag" in kwargs:
            data["goods_tag"] = kwargs["goods_tag"]

        body = json.dumps(data, separators=(",", ":"))

        try:
            headers = self._build_auth_header("POST", url_path, body)
            response = requests.post(url, data=body, headers=headers, timeout=30)

            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "prepay_id": result.get("prepay_id"),
                    "data": result,
                }
            else:
                error_info = response.json() if response.content else {}
                return {
                    "success": False,
                    "message": error_info.get(
                        "message", f"HTTP {response.status_code}"
                    ),
                }

        except Exception as e:
            return {"success": False, "message": f"网络请求失败: {str(e)}"}

    def create_native_order(
        self, order_id: str, total_amount: int, description: str, **kwargs
    ) -> Dict[str, Any]:
        """
        创建Native支付订单

        Args:
            order_id: 商户订单号
            total_amount: 订单金额（分）
            description: 商品描述
            **kwargs: 其他参数

        Returns:
            Dict[str, Any]: 订单创建结果
        """
        url = f"{self.config.native_pay_url}"
        url_path = "/v3/pay/transactions/native"

        # 构建请求体
        data = {
            "appid": self.config.app_id,
            "mchid": self.config.mch_id,
            "description": description,
            "out_trade_no": order_id,
            "amount": {"total": total_amount, "currency": "CNY"},
            "notify_url": self.config.notify_url,
        }

        # 添加可选参数
        if "time_expire" in kwargs:
            data["time_expire"] = kwargs["time_expire"]
        if "attach" in kwargs:
            data["attach"] = kwargs["attach"]
        if "goods_tag" in kwargs:
            data["goods_tag"] = kwargs["goods_tag"]

        body = json.dumps(data, separators=(",", ":"))

        try:
            headers = self._build_auth_header("POST", url_path, body)
            response = requests.post(url, data=body, headers=headers, timeout=30)

            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "code_url": result.get("code_url"),
                    "data": result,
                }
            else:
                error_info = response.json() if response.content else {}
                return {
                    "success": False,
                    "message": error_info.get(
                        "message", f"HTTP {response.status_code}"
                    ),
                }

        except Exception as e:
            return {"success": False, "message": f"网络请求失败: {str(e)}"}

    def query_order(self, order_id: str) -> Dict[str, Any]:
        """
        查询订单状态

        Args:
            order_id: 商户订单号

        Returns:
            Dict[str, Any]: 订单查询结果
        """
        url = f"{self.config.order_query_url}/{order_id}?mchid={self.config.mch_id}"
        url_path = f"/v3/pay/transactions/out-trade-no/{order_id}"

        try:
            headers = self._build_auth_header("GET", url_path)
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "trade_state": result.get("trade_state"),
                    "trade_state_desc": result.get("trade_state_desc"),
                    "data": result,
                }
            else:
                error_info = response.json() if response.content else {}
                return {
                    "success": False,
                    "message": error_info.get(
                        "message", f"HTTP {response.status_code}"
                    ),
                }

        except Exception as e:
            return {"success": False, "message": f"网络请求失败: {str(e)}"}

    def verify_notify_signature(
        self, timestamp: str, nonce: str, body: str, signature: str
    ) -> bool:
        """
        验证回调通知签名

        Args:
            timestamp: 时间戳
            nonce: 随机字符串
            body: 请求体
            signature: 签名

        Returns:
            bool: 签名是否正确
        """
        # 构建待签名字符串
        sign_str = f"{timestamp}\n{nonce}\n{body}\n"

        # 使用API v3密钥计算签名
        expected_signature = base64.b64encode(
            hmac.new(
                self.config.api_v3_key.encode("utf-8"),
                sign_str.encode("utf-8"),
                hashlib.sha256,
            ).digest()
        ).decode("utf-8")

        return hmac.compare_digest(signature, expected_signature)

    def _decrypt_resource(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """
        解密微信支付回调中的resource数据

        Args:
            resource: 加密的resource数据

        Returns:
            Dict[str, Any]: 解密后的数据
        """
        try:
            # 移除API v3密钥调试信息输出

            # 获取加密相关参数
            ciphertext = resource.get("ciphertext", "")
            associated_data = resource.get("associated_data", "")
            nonce = resource.get("nonce", "")

            if not all([ciphertext, associated_data, nonce]):
                return {}

            # 使用API v3密钥作为解密密钥
            # 微信支付API v3密钥应该是32字节的字符串
            api_key = self.config.api_v3_key
            if len(api_key) != 32:
                return {}

            # 直接使用原始API v3密钥作为AES密钥
            key = api_key.encode("utf-8")

            # 解码base64数据
            ciphertext_bytes = base64.b64decode(ciphertext)
            # nonce不需要base64解码，直接使用原始字符串
            nonce_bytes = nonce.encode("utf-8")
            associated_data_bytes = associated_data.encode("utf-8")

            # 移除解密参数调试信息

            # 使用AES-GCM解密
            aesgcm = AESGCM(key)
            decrypted_data = aesgcm.decrypt(
                nonce_bytes, ciphertext_bytes, associated_data_bytes
            )

            # 解析JSON数据
            decrypted_json = json.loads(decrypted_data.decode("utf-8"))
            return decrypted_json

        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            # 移除详细的解密失败信息输出
            return {}

    def process_notify(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理支付结果通知

        Args:
            request_data: 请求数据（包含headers和body）

        Returns:
            Dict[str, Any]: 处理结果
        """
        # 移除process_notify调试信息
        try:
            # 获取签名相关参数
            timestamp = request_data.get("headers", {}).get("Wechatpay-Timestamp", "")
            nonce = request_data.get("headers", {}).get("Wechatpay-Nonce", "")
            signature = request_data.get("headers", {}).get("Wechatpay-Signature", "")
            body = request_data.get("body", "")

            # 防重放攻击：校验时间戳，拒绝超过5分钟的回调
            if not timestamp:
                return {"success": False, "message": "缺少回调时间戳"}
            try:
                if abs(time.time() - int(timestamp)) > 300:
                    logger.warning(f"支付回调时间戳已过期: timestamp={timestamp}")
                    return {"success": False, "message": "回调时间戳已过期"}
            except (ValueError, TypeError):
                logger.warning(f"支付回调时间戳格式错误: timestamp={timestamp}")
                return {"success": False, "message": "回调时间戳格式错误"}

            # 高优先级安全改进：强制验证签名（使用微信支付公钥）
            if not self.verify_notify_signature_with_public_key(
                timestamp, nonce, body, signature
            ):
                logger.error(
                    f"【安全告警】支付回调签名验证失败: "
                    f"timestamp={timestamp}, nonce={nonce[:8]}..."
                )
                # 记录到支付异常监控
                try:
                    from payment_callback_enhanced import get_payment_callback_monitor

                    monitor = get_payment_callback_monitor()
                    monitor.record_alert(
                        "signature_verification_failed",
                        "critical",
                        f"支付回调签名验证失败: timestamp={timestamp}",
                        {"timestamp": timestamp, "nonce": nonce[:8] if nonce else None},
                    )
                except (ImportError, ModuleNotFoundError):
                    # 监控模块不可用，记录警告但不影响主流程
                    logger.warning("支付异常监控模块不可用，无法记录签名验证失败告警")
                except (AttributeError, TypeError) as e:
                    # 监控模块配置错误
                    logger.warning(f"支付异常监控模块配置错误: {type(e).__name__}: {e}")
                except Exception as e:
                    # 其他异常（如监控模块内部错误），记录但不影响主流程
                    logger.warning(f"记录支付异常监控告警失败: {type(e).__name__}: {e}")
                return {"success": False, "message": "签名验证失败"}

            # 解析通知数据
            notify_data = json.loads(body)

            # 检查通知类型
            if notify_data.get("event_type") == "TRANSACTION.SUCCESS":
                resource = notify_data.get("resource", {})

                # 解密resource中的数据
                decrypted_data = self._decrypt_resource(resource)
                if not decrypted_data:
                    return {"success": False, "message": "解密失败"}

                # 从解密后的数据中获取订单信息
                out_trade_no = decrypted_data.get("out_trade_no")
                transaction_id = decrypted_data.get("transaction_id")
                trade_state = decrypted_data.get("trade_state")

                # 移除支付成功通知的详细数据输出

                return {
                    "success": True,
                    "out_trade_no": out_trade_no,
                    "transaction_id": transaction_id,
                    "trade_state": trade_state,
                    "data": decrypted_data,
                }
            else:
                return {"success": False, "message": "非支付成功通知"}

        except Exception as e:
            return {"success": False, "message": f"通知处理失败: {str(e)}"}

    def verify_notify_signature_with_public_key(
        self, timestamp: str, nonce: str, body: str, signature: str
    ) -> bool:
        """
        使用微信支付公钥验证回调通知签名

        Args:
            timestamp: 时间戳
            nonce: 随机字符串
            body: 请求体
            signature: 签名

        Returns:
            bool: 签名是否正确
        """
        try:
            # 高优先级安全改进：强制要求公钥验证
            if not self.config.public_key_path:
                logger.error("微信支付公钥未配置，无法验证回调签名")
                return False  # 如果没有配置公钥，拒绝验证

            # 检查公钥文件是否存在
            if not os.path.exists(self.config.public_key_path):
                logger.error(f"微信支付公钥文件不存在: {self.config.public_key_path}")
                return False  # 如果公钥文件不存在，拒绝验证

            # 构建待验证的字符串
            sign_str = f"{timestamp}\n{nonce}\n{body}\n"

            # 加载微信支付公钥
            with open(self.config.public_key_path, "rb") as f:
                public_key_data = f.read()
                public_key = serialization.load_pem_public_key(public_key_data)

            # 验证签名
            # 确保公钥是RSA类型
            if not isinstance(public_key, rsa.RSAPublicKey):
                raise ValueError("微信支付公钥必须是RSA类型")

            public_key.verify(
                base64.b64decode(signature),
                sign_str.encode("utf-8"),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )

            return True

        except (OSError, IOError, ValueError, TypeError):
            return False


# 全局API实例
wechat_pay_v3 = WeChatPayV3API()

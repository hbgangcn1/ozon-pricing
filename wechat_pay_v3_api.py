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
from typing import Dict, Optional, Any
import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
from wechat_pay_config import wechat_config


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

    def _load_private_key(self) -> Optional[rsa.RSAPrivateKey]:
        """加载商户私钥"""
        if self._private_key is not None:
            return self._private_key

        if not self.config.private_key_path:
            print("私钥路径未配置")
            return None
            
        if not os.path.exists(self.config.private_key_path):
            print(f"私钥文件不存在: {self.config.private_key_path}")
            return None

        try:
            with open(self.config.private_key_path, 'rb') as key_file:
                private_key = serialization.load_pem_private_key(
                    key_file.read(),
                    password=None,
                    backend=default_backend()
                )
                # 确保返回的是RSA私钥
                if isinstance(private_key, rsa.RSAPrivateKey):
                    self._private_key = private_key
                    print("✅ 私钥加载成功")
                    return self._private_key
                else:
                    print("❌ 私钥不是RSA类型")
                    return None
        except Exception as e:
            print(f"加载私钥失败: {e}")
            print(f"私钥文件路径: {self.config.private_key_path}")
            return None

    @staticmethod
    def _get_timestamp() -> str:
        """获取当前时间戳（秒）"""
        return str(int(time.time()))

    @staticmethod
    def _get_nonce_str() -> str:
        """生成随机字符串"""
        import random
        import string
        chars = string.ascii_letters + string.digits
        return ''.join(random.choice(chars) for _ in range(32))

    def _build_signature(self, method: str, url_path: str, timestamp: str,
                         nonce_str: str, body: str = "") -> str:
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
        print(f"签名字符串: {repr(sign_str)}")

        # 使用商户私钥签名
        private_key = self._load_private_key()
        if not private_key:
            raise Exception("商户私钥未配置或加载失败")

        # 使用SHA256withRSA签名
        signature = private_key.sign(
            sign_str.encode('utf-8'),
            padding.PKCS1v15(),
            hashes.SHA256()
        )

        # Base64编码
        signature_b64 = base64.b64encode(signature).decode('utf-8')
        print(f"签名结果: {signature_b64}")
        return signature_b64

    def _build_auth_header(self, method: str, url_path: str,
                           body: str = "") -> Dict[str, str]:
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
        signature = self._build_signature(method, url_path, timestamp,
                                          nonce_str, body)

        # 构建Authorization头 - 微信支付v3 API格式
        auth_str = (f'WECHATPAY2-SHA256-RSA2048 '
                    f'mchid="{self.config.mch_id}",'
                    f'nonce_str="{nonce_str}",'
                    f'signature="{signature}",'
                    f'timestamp="{timestamp}",'
                    f'serial_no="{self._cert_serial_no}"')

        # 调试信息
        print(f"Authorization头: {auth_str}")
        print(f"商户号: {self.config.mch_id}")
        print(f"证书序列号: {self._cert_serial_no}")
        print(f"证书序列号长度: {len(self._cert_serial_no) if self._cert_serial_no else 0}")
        print(f"证书序列号类型: {type(self._cert_serial_no)}")

        return {
            'Authorization': auth_str,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    def create_jsapi_order(self,
                           order_id: str,
                           total_amount: int,
                           description: str,
                           openid: str,
                           **kwargs) -> Dict[str, Any]:
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
            "amount": {
                "total": total_amount,
                "currency": "CNY"
            },
            "payer": {
                "openid": openid
            },
            "notify_url": self.config.notify_url
        }

        # 添加可选参数
        if "time_expire" in kwargs:
            data["time_expire"] = kwargs["time_expire"]
        if "attach" in kwargs:
            data["attach"] = kwargs["attach"]
        if "goods_tag" in kwargs:
            data["goods_tag"] = kwargs["goods_tag"]

        body = json.dumps(data, separators=(',', ':'))

        try:
            headers = self._build_auth_header("POST", url_path, body)
            response = requests.post(url, data=body, headers=headers,
                                     timeout=30)

            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "prepay_id": result.get("prepay_id"),
                    "data": result
                }
            else:
                error_info = response.json() if response.content else {}
                return {
                    "success": False,
                    "message": error_info.get("message",
                                              f"HTTP {response.status_code}")
                }

        except Exception as e:
            return {"success": False, "message": f"网络请求失败: {str(e)}"}

    def create_native_order(self,
                            order_id: str,
                            total_amount: int,
                            description: str,
                            **kwargs) -> Dict[str, Any]:
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
            "amount": {
                "total": total_amount,
                "currency": "CNY"
            },
            "notify_url": self.config.notify_url
        }

        # 添加可选参数
        if "time_expire" in kwargs:
            data["time_expire"] = kwargs["time_expire"]
        if "attach" in kwargs:
            data["attach"] = kwargs["attach"]
        if "goods_tag" in kwargs:
            data["goods_tag"] = kwargs["goods_tag"]

        body = json.dumps(data, separators=(',', ':'))

        try:
            headers = self._build_auth_header("POST", url_path, body)
            response = requests.post(url, data=body, headers=headers,
                                     timeout=30)

            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "code_url": result.get("code_url"),
                    "data": result
                }
            else:
                error_info = response.json() if response.content else {}
                return {
                    "success": False,
                    "message": error_info.get("message",
                                              f"HTTP {response.status_code}")
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
        url = (f"{self.config.order_query_url}/{order_id}"
               f"?mchid={self.config.mch_id}")
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
                    "data": result
                }
            else:
                error_info = response.json() if response.content else {}
                return {
                    "success": False,
                    "message": error_info.get("message",
                                              f"HTTP {response.status_code}")
                }

        except Exception as e:
            return {"success": False, "message": f"网络请求失败: {str(e)}"}

    def verify_notify_signature(self, timestamp: str, nonce: str,
                                body: str, signature: str) -> bool:
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
                self.config.api_v3_key.encode('utf-8'),
                sign_str.encode('utf-8'),
                hashlib.sha256
            ).digest()
        ).decode('utf-8')

        return hmac.compare_digest(signature, expected_signature)

    def process_notify(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理支付结果通知

        Args:
            request_data: 请求数据（包含headers和body）

        Returns:
            Dict[str, Any]: 处理结果
        """
        try:
            # 获取签名相关参数
            timestamp = (request_data.get("headers", {})
                         .get("Wechatpay-Timestamp", ""))
            nonce = (request_data.get("headers", {})
                     .get("Wechatpay-Nonce", ""))
            signature = (request_data.get("headers", {})
                         .get("Wechatpay-Signature", ""))
            body = request_data.get("body", "")

            # 验证签名（临时跳过，后续需要实现正确的RSA签名验证）
            # TODO: 实现正确的微信支付v3 API RSA签名验证
            # if not self.verify_notify_signature(timestamp, nonce, body,
            #                                     signature):
            #     return {"success": False, "message": "签名验证失败"}

            # 解析通知数据
            notify_data = json.loads(body)

            # 检查通知类型
            if notify_data.get("event_type") == "TRANSACTION.SUCCESS":
                resource = notify_data.get("resource", {})
                # 这里需要解密resource中的数据
                # 实际使用时需要实现AES解密逻辑
                return {
                    "success": True,
                    "out_trade_no": resource.get("out_trade_no"),
                    "transaction_id": resource.get("transaction_id"),
                    "trade_state": resource.get("trade_state"),
                    "data": notify_data
                }
            else:
                return {
                    "success": False,
                    "message": "非支付成功通知"
                }

        except Exception as e:
            return {"success": False, "message": f"通知处理失败: {str(e)}"}


# 全局API实例
wechat_pay_v3 = WeChatPayV3API()

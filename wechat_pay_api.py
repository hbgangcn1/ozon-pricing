# -*- coding: utf-8 -*-
"""
微信支付API接口模块
实现微信支付的核心功能：统一下单、查询订单、退款等
"""

import time
import hashlib
import xml.etree.ElementTree as ET
from typing import Dict, Optional, Any
import requests
import random
import string
from wechat_pay_config import wechat_config


class WeChatPayAPI:
    """微信支付API类"""
    
    def __init__(self, config=None):
        """
        初始化微信支付API
        
        Args:
            config: 微信支付配置对象，默认使用全局配置
        """
        self.config = config or wechat_config
    
    def generate_nonce_str(self, length: int = 32) -> str:
        """
        生成随机字符串
        
        Args:
            length: 随机字符串长度
            
        Returns:
            str: 随机字符串
        """
        chars = string.ascii_letters + string.digits
        return ''.join(random.choice(chars) for _ in range(length))
    
    def generate_sign(self, params: Dict[str, Any]) -> str:
        """
        生成微信支付签名
        
        Args:
            params: 参数字典
            
        Returns:
            str: 签名字符串
        """
        # 过滤空值和sign字段
        filtered_params = {k: v for k, v in params.items() 
                          if v != "" and v is not None and k != "sign"}
        
        # 按参数名ASCII排序
        sorted_params = sorted(filtered_params.items())
        
        # 拼接参数
        query_string = "&".join(f"{k}={v}" for k, v in sorted_params)
        
        # 添加API密钥
        query_string += f"&key={self.config.api_key}"
        
        # MD5加密并转大写
        return hashlib.md5(query_string.encode('utf-8')).hexdigest().upper()
    
    def dict_to_xml(self, data: Dict[str, Any]) -> str:
        """
        字典转XML
        
        Args:
            data: 数据字典
            
        Returns:
            str: XML字符串
        """
        xml_parts = ["<xml>"]
        for key, value in data.items():
            xml_parts.append(f"<{key}><![CDATA[{value}]]></{key}>")
        xml_parts.append("</xml>")
        return "".join(xml_parts)
    
    def xml_to_dict(self, xml_str: str) -> Dict[str, Any]:
        """
        XML转字典
        
        Args:
            xml_str: XML字符串
            
        Returns:
            Dict[str, Any]: 数据字典
        """
        root = ET.fromstring(xml_str)
        return {child.tag: child.text or "" for child in root}
    
    def create_order(self, 
                    order_id: str,
                    total_fee: int,
                    body: str,
                    trade_type: str = "NATIVE",
                    product_id: Optional[str] = None,
                    openid: Optional[str] = None) -> Dict[str, Any]:
        """
        创建微信支付订单
        
        Args:
            order_id: 商户订单号
            total_fee: 订单金额（分）
            body: 商品描述
            trade_type: 交易类型（NATIVE/JSAPI/APP等）
            product_id: 商品ID（NATIVE必填）
            openid: 用户openid（JSAPI必填）
            
        Returns:
            Dict[str, Any]: 订单创建结果
        """
        # 构建请求参数
        params = {
            "appid": self.config.app_id,
            "mch_id": self.config.mch_id,
            "nonce_str": self.generate_nonce_str(),
            "body": body,
            "out_trade_no": order_id,
            "total_fee": str(total_fee),
            "spbill_create_ip": "127.0.0.1",  # 终端IP
            "notify_url": self.config.notify_url,
            "trade_type": trade_type,
        }
        
        # 根据交易类型添加特定参数
        if trade_type == "NATIVE" and product_id:
            params["product_id"] = product_id
        elif trade_type == "JSAPI" and openid:
            params["openid"] = openid
        
        # 生成签名
        params["sign"] = self.generate_sign(params)
        
        # 转换为XML
        xml_data = self.dict_to_xml(params)
        
        try:
            # 发送请求
            response = requests.post(
                self.config.unified_order_url,
                data=xml_data.encode('utf-8'),
                headers={'Content-Type': 'application/xml'},
                timeout=30
            )
            
            # 解析响应
            result = self.xml_to_dict(response.text)
            
            # 验证响应签名
            if not self.verify_sign(result):
                return {"success": False, "message": "响应签名验证失败"}
            
            # 检查返回状态
            if result.get("return_code") == "SUCCESS":
                if result.get("result_code") == "SUCCESS":
                    return {
                        "success": True,
                        "prepay_id": result.get("prepay_id"),
                        "code_url": result.get("code_url"),  # 二维码链接
                        "trade_type": result.get("trade_type"),
                        "data": result
                    }
                else:
                    return {
                        "success": False,
                        "message": result.get("err_code_des", "下单失败")
                    }
            else:
                return {
                    "success": False,
                    "message": result.get("return_msg", "请求失败")
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
        params = {
            "appid": self.config.app_id,
            "mch_id": self.config.mch_id,
            "out_trade_no": order_id,
            "nonce_str": self.generate_nonce_str(),
        }
        
        # 生成签名
        params["sign"] = self.generate_sign(params)
        
        # 转换为XML
        xml_data = self.dict_to_xml(params)
        
        try:
            response = requests.post(
                self.config.order_query_url,
                data=xml_data.encode('utf-8'),
                headers={'Content-Type': 'application/xml'},
                timeout=30
            )
            
            result = self.xml_to_dict(response.text)
            
            if result.get("return_code") == "SUCCESS":
                if result.get("result_code") == "SUCCESS":
                    return {
                        "success": True,
                        "trade_state": result.get("trade_state"),
                        "trade_state_desc": result.get("trade_state_desc"),
                        "data": result
                    }
                else:
                    return {
                        "success": False,
                        "message": result.get("err_code_des", "查询失败")
                    }
            else:
                return {
                    "success": False,
                    "message": result.get("return_msg", "请求失败")
                }
                
        except Exception as e:
            return {"success": False, "message": f"网络请求失败: {str(e)}"}
    
    def verify_sign(self, data: Dict[str, Any]) -> bool:
        """
        验证签名
        
        Args:
            data: 数据字典
            
        Returns:
            bool: 签名是否正确
        """
        if "sign" not in data:
            return False
        
        received_sign = data["sign"]
        calculated_sign = self.generate_sign(data)
        
        return received_sign == calculated_sign
    
    def process_notify(self, xml_data: str) -> Dict[str, Any]:
        """
        处理支付结果通知
        
        Args:
            xml_data: 微信发送的XML数据
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        try:
            data = self.xml_to_dict(xml_data)
            
            # 验证签名
            if not self.verify_sign(data):
                return {"success": False, "message": "签名验证失败"}
            
            # 检查支付结果
            if (data.get("return_code") == "SUCCESS" and 
                data.get("result_code") == "SUCCESS"):
                return {
                    "success": True,
                    "out_trade_no": data.get("out_trade_no"),
                    "transaction_id": data.get("transaction_id"),
                    "total_fee": int(data.get("total_fee", 0)),
                    "time_end": data.get("time_end"),
                    "data": data
                }
            else:
                return {
                    "success": False,
                    "message": data.get("err_code_des", "支付失败")
                }
                
        except Exception as e:
            return {"success": False, "message": f"数据解析失败: {str(e)}"}


# 全局API实例
wechat_pay = WeChatPayAPI()

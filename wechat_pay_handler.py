# -*- coding: utf-8 -*-
"""
微信支付回调处理模块
处理微信支付的回调通知和订单状态更新
"""

import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import sqlite3
from wechat_pay_api import wechat_pay
from db_utils import get_db_connection


# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WeChatPayHandler:
    """微信支付处理器"""
    
    def __init__(self):
        """初始化支付处理器"""
        self.wechat_pay = wechat_pay
    
    def create_payment_order(self, 
                           user_id: str,
                           plan_type: str,
                           amount: float,
                           description: str) -> Dict[str, Any]:
        """
        创建支付订单
        
        Args:
            user_id: 用户ID
            plan_type: 订阅计划类型
            amount: 支付金额（元）
            description: 订单描述
            
        Returns:
            Dict[str, Any]: 创建结果
        """
        try:
            # 生成订单号
            order_id = self.generate_order_id(user_id)
            
            # 转换金额为分
            total_fee = int(amount * 100)
            
            # 保存订单到数据库
            if not self.save_order_to_db(order_id, user_id, plan_type, 
                                       total_fee, description):
                return {"success": False, "message": "订单保存失败"}
            
            # 调用微信支付API创建订单
            result = self.wechat_pay.create_order(
                order_id=order_id,
                total_fee=total_fee,
                body=description,
                trade_type="NATIVE",
                product_id=plan_type
            )
            
            if result["success"]:
                # 更新订单状态
                self.update_order_status(order_id, "CREATED", 
                                       result.get("prepay_id"))
                
                return {
                    "success": True,
                    "order_id": order_id,
                    "qr_code_url": result.get("code_url"),
                    "prepay_id": result.get("prepay_id")
                }
            else:
                # 更新订单状态为失败
                self.update_order_status(order_id, "FAILED", 
                                       error_msg=result.get("message"))
                return result
                
        except Exception as e:
            logger.error(f"创建支付订单失败: {str(e)}")
            return {"success": False, "message": f"创建订单失败: {str(e)}"}
    
    def generate_order_id(self, user_id: str) -> str:
        """
        生成订单号
        
        Args:
            user_id: 用户ID
            
        Returns:
            str: 订单号
        """
        timestamp = str(int(time.time()))
        return f"WX{user_id}_{timestamp}"
    
    def save_order_to_db(self, 
                        order_id: str,
                        user_id: str,
                        plan_type: str,
                        total_fee: int,
                        description: str) -> bool:
        """
        保存订单到数据库
        
        Args:
            order_id: 订单号
            user_id: 用户ID
            plan_type: 计划类型
            total_fee: 金额（分）
            description: 描述
            
        Returns:
            bool: 是否成功
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # 创建支付订单表（如果不存在）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS payment_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT UNIQUE NOT NULL,
                    user_id TEXT NOT NULL,
                    plan_type TEXT NOT NULL,
                    total_fee INTEGER NOT NULL,
                    description TEXT,
                    status TEXT DEFAULT 'PENDING',
                    prepay_id TEXT,
                    transaction_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    error_msg TEXT
                )
            """)
            
            # 插入订单
            cursor.execute("""
                INSERT INTO payment_orders 
                (order_id, user_id, plan_type, total_fee, description)
                VALUES (?, ?, ?, ?, ?)
            """, (order_id, user_id, plan_type, total_fee, description))
            
            conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"保存订单失败: {str(e)}")
            return False
        finally:
            if conn:
                conn.close()
    
    def update_order_status(self, 
                          order_id: str,
                          status: str,
                          prepay_id: Optional[str] = None,
                          transaction_id: Optional[str] = None,
                          error_msg: Optional[str] = None) -> bool:
        """
        更新订单状态
        
        Args:
            order_id: 订单号
            status: 状态
            prepay_id: 预支付ID
            transaction_id: 微信交易号
            error_msg: 错误信息
            
        Returns:
            bool: 是否成功
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # 构建更新SQL
            update_fields = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
            params = [status]
            
            if prepay_id:
                update_fields.append("prepay_id = ?")
                params.append(prepay_id)
            
            if transaction_id:
                update_fields.append("transaction_id = ?")
                params.append(transaction_id)
            
            if error_msg:
                update_fields.append("error_msg = ?")
                params.append(error_msg)
            
            params.append(order_id)
            
            cursor.execute(f"""
                UPDATE payment_orders 
                SET {', '.join(update_fields)}
                WHERE order_id = ?
            """, params)
            
            conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"更新订单状态失败: {str(e)}")
            return False
        finally:
            if conn:
                conn.close()
    
    def handle_payment_notify(self, xml_data: str) -> str:
        """
        处理微信支付回调通知
        
        Args:
            xml_data: 微信发送的XML数据
            
        Returns:
            str: 响应XML
        """
        try:
            # 解析支付通知
            result = self.wechat_pay.process_notify(xml_data)
            
            if result["success"]:
                order_id = result["out_trade_no"]
                transaction_id = result["transaction_id"]
                
                # 更新订单状态
                self.update_order_status(
                    order_id, "PAID", 
                    transaction_id=transaction_id
                )
                
                # 激活用户订阅
                self.activate_user_subscription(order_id)
                
                logger.info(f"支付成功，订单号: {order_id}")
                
                # 返回成功响应
                return """<xml>
                    <return_code><![CDATA[SUCCESS]]></return_code>
                    <return_msg><![CDATA[OK]]></return_msg>
                </xml>"""
            else:
                logger.error(f"支付通知处理失败: {result['message']}")
                
                # 返回失败响应
                return """<xml>
                    <return_code><![CDATA[FAIL]]></return_code>
                    <return_msg><![CDATA[处理失败]]></return_msg>
                </xml>"""
                
        except Exception as e:
            logger.error(f"处理支付通知异常: {str(e)}")
            return """<xml>
                <return_code><![CDATA[FAIL]]></return_code>
                <return_msg><![CDATA[系统错误]]></return_msg>
            </xml>"""
    
    def activate_user_subscription(self, order_id: str) -> bool:
        """
        激活用户订阅
        
        Args:
            order_id: 订单号
            
        Returns:
            bool: 是否成功
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # 获取订单信息
            cursor.execute("""
                SELECT user_id, plan_type FROM payment_orders 
                WHERE order_id = ? AND status = 'PAID'
            """, (order_id,))
            
            order = cursor.fetchone()
            if not order:
                return False
            
            user_id, plan_type = order
            
            # 计算订阅到期时间
            if plan_type == 'efficiency':
                # 效率版：首月1元，后续9.9元/月
                days = 30
            elif plan_type == 'precision':
                # 精准版：19.9元/月
                days = 30
            else:
                days = 30
            
            # 更新用户订阅状态
            cursor.execute("""
                UPDATE users 
                SET subscription_type = ?,
                    subscription_end_date = datetime('now', '+{} days'),
                    updated_at = CURRENT_TIMESTAMP
                WHERE username = ?
            """.format(days), (plan_type, user_id))
            
            conn.commit()
            logger.info(f"用户 {user_id} 订阅已激活，类型: {plan_type}")
            return True
            
        except Exception as e:
            logger.error(f"激活订阅失败: {str(e)}")
            return False
        finally:
            if conn:
                conn.close()
    
    def check_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        检查订单状态
        
        Args:
            order_id: 订单号
            
        Returns:
            Dict[str, Any]: 订单状态信息
        """
        try:
            # 先查询数据库
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT status, transaction_id, created_at, updated_at
                FROM payment_orders WHERE order_id = ?
            """, (order_id,))
            
            order = cursor.fetchone()
            if not order:
                return {"success": False, "message": "订单不存在"}
            
            status, transaction_id, created_at, updated_at = order
            
            # 如果订单已支付，直接返回
            if status == "PAID":
                return {
                    "success": True,
                    "status": status,
                    "paid": True,
                    "transaction_id": transaction_id
                }
            
            # 如果订单待支付，查询微信支付状态
            if status in ["PENDING", "CREATED"]:
                wx_result = self.wechat_pay.query_order(order_id)
                
                if wx_result["success"]:
                    trade_state = wx_result["trade_state"]
                    
                    if trade_state == "SUCCESS":
                        # 支付成功，更新订单状态
                        transaction_id = wx_result["data"].get("transaction_id")
                        self.update_order_status(order_id, "PAID", 
                                               transaction_id=transaction_id)
                        self.activate_user_subscription(order_id)
                        
                        return {
                            "success": True,
                            "status": "PAID",
                            "paid": True,
                            "transaction_id": transaction_id
                        }
                    else:
                        return {
                            "success": True,
                            "status": status,
                            "paid": False,
                            "trade_state": trade_state,
                            "trade_state_desc": wx_result.get("trade_state_desc")
                        }
                else:
                    return {
                        "success": True,
                        "status": status,
                        "paid": False,
                        "message": wx_result.get("message")
                    }
            
            return {
                "success": True,
                "status": status,
                "paid": False
            }
            
        except Exception as e:
            logger.error(f"查询订单状态失败: {str(e)}")
            return {"success": False, "message": f"查询失败: {str(e)}"}
        finally:
            if conn:
                conn.close()


# 全局处理器实例
wechat_pay_handler = WeChatPayHandler()


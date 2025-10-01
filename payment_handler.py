# -*- coding: utf-8 -*-
"""
支付处理模块
集成微信支付到现有的用户界面中
"""

import streamlit as st
import time
import uuid
from typing import Dict, Any
from wechat_pay_v3_api import wechat_pay_v3
from wechat_pay_config import wechat_config
from db_utils import get_db_connection


class PaymentHandler:
    """支付处理类"""

    def __init__(self):
        """初始化支付处理器"""
        self.config = wechat_config

    @staticmethod
    def create_payment_order(user_id: int,
                             amount: int,
                             description: str,
                             payment_type: str = "native") -> Dict[str, Any]:
        """
        创建支付订单

        Args:
            user_id: 用户ID
            amount: 支付金额（分）
            description: 订单描述
            payment_type: 支付类型（native/jsapi）

        Returns:
            Dict[str, Any]: 订单创建结果
        """
        # 生成订单号
        order_id = f"PAY_{int(time.time())}_{uuid.uuid4().hex[:8]}"

        # 保存订单到数据库
        try:
            with get_db_connection() as (conn, cursor):
                # 先检查用户是否存在
                cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
                if not cursor.fetchone():
                    return {"success": False, "message": f"用户ID {user_id} 不存在"}
                
                cursor.execute("""
                    INSERT INTO payment_orders
                    (order_id, user_id, amount, description, status,
                     created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (order_id, user_id, amount, description, 'PENDING',
                      int(time.time())))

                conn.commit()

        except Exception as e:
            return {"success": False, "message": f"订单创建失败: {str(e)}"}

        # 根据支付类型创建微信支付订单
        if payment_type == "native":
            result = wechat_pay_v3.create_native_order(
                order_id=order_id,
                total_amount=amount,
                description=description
            )
        elif payment_type == "jsapi":
            # 需要用户openid，这里暂时返回错误
            return {"success": False, "message": "JSAPI支付需要用户openid"}
        else:
            return {"success": False, "message": "不支持的支付类型"}

        if result["success"]:
            # 更新订单状态
            PaymentHandler._update_order_status(order_id, "CREATED")

            return {
                "success": True,
                "order_id": order_id,
                "code_url": result.get("code_url"),
                "prepay_id": result.get("prepay_id")
            }
        else:
            return result

    @staticmethod
    def query_payment_status(order_id: str) -> Dict[str, Any]:
        """
        查询支付状态

        Args:
            order_id: 订单号

        Returns:
            Dict[str, Any]: 查询结果
        """
        # 查询微信支付状态
        result = wechat_pay_v3.query_order(order_id)

        if result["success"]:
            trade_state = result.get("trade_state")

            # 更新本地订单状态
            if trade_state == "SUCCESS":
                PaymentHandler._update_order_status(order_id, "PAID")
            elif trade_state in ["CLOSED", "REVOKED", "PAYERROR"]:
                PaymentHandler._update_order_status(order_id, "FAILED")

            return {
                "success": True,
                "status": trade_state,
                "description": result.get("trade_state_desc", ""),
                "data": result.get("data", {})
            }
        else:
            return result

    @staticmethod
    def _update_order_status(order_id: str, status: str):
        """更新订单状态"""
        try:
            with get_db_connection() as (conn, cursor):
                cursor.execute("""
                    UPDATE payment_orders
                    SET status = ?, updated_at = ?
                    WHERE order_id = ?
                """, (status, int(time.time()), order_id))

                conn.commit()

        except Exception as e:
            print(f"更新订单状态失败: {e}")

    @staticmethod
    def get_user_payment_history(user_id: int) -> list:
        """获取用户支付历史"""
        try:
            with get_db_connection() as (conn, cursor):
                cursor.execute("""
                    SELECT order_id, amount, description, status, created_at
                    FROM payment_orders
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT 20
                """, (user_id,))

                results = cursor.fetchall()

            return [
                {
                    "order_id": row[0],
                    "amount": row[1],
                    "description": row[2],
                    "status": row[3],
                    "created_at": row[4]
                }
                for row in results
            ]

        except Exception as e:
            print(f"查询支付历史失败: {e}")
            return []

    @staticmethod
    def process_wechat_notify(notify_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理微信支付回调通知

        Args:
            notify_data: 通知数据

        Returns:
            Dict[str, Any]: 处理结果
        """
        result = wechat_pay_v3.process_notify(notify_data)

        if result["success"]:
            order_id = result.get("out_trade_no")
            if order_id:
                # 更新订单状态为已支付
                PaymentHandler._update_order_status(order_id, "PAID")

                # 这里可以添加业务逻辑，比如开通会员、增加计算次数等
                PaymentHandler._handle_payment_success(order_id)

        return result

    @staticmethod
    def _handle_payment_success(order_id: str):
        """处理支付成功后的业务逻辑"""
        print(f"🔧 开始处理支付成功逻辑: 订单ID={order_id}")
        try:
            with get_db_connection() as (conn, cursor):
                # 获取订单信息
                cursor.execute("""
                    SELECT user_id, amount, description
                    FROM payment_orders
                    WHERE order_id = ?
                """, (order_id,))

                order_info = cursor.fetchone()
                if not order_info:
                    return

                user_id, amount, description = order_info

                # 根据支付金额和描述处理业务逻辑
                if ("专业版" in description or
                        "PROFESSIONAL" in description.upper()):
                    # 开通专业版会员
                    cursor.execute("""
                        UPDATE users
                        SET subscription_type = 'professional',
                            subscription_expires = ?,
                            updated_at = ?
                        WHERE id = ?
                    """, (int(time.time()) + 365*24*3600,
                          int(time.time()), user_id))

                elif ("效率版" in description or
                      "EFFICIENCY" in description.upper()):
                    # 开通效率版会员
                    print(f"🔧 处理效率版支付成功: 用户ID={user_id}, 描述={description}")
                    cursor.execute("""
                        UPDATE users
                        SET subscription_type = 'efficiency',
                            subscription_expires = ?,
                            updated_at = ?
                        WHERE id = ?
                    """, (int(time.time()) + 30*24*3600,  # 30天有效期
                          int(time.time()), user_id))
                    print(f"✅ 效率版订阅状态已更新: 用户ID={user_id}")

                elif "计算次数" in description:
                    # 增加计算次数
                    cursor.execute("""
                        UPDATE users
                        SET calculations_remaining = calculations_remaining + ?
                        WHERE id = ?
                    """, (amount // 100, user_id))  # 假设1元=1次计算

                conn.commit()

        except Exception as e:
            print(f"处理支付成功逻辑失败: {e}")


def show_payment_page():
    """显示支付页面"""
    st.title("💳 支付中心")

    # 检查用户登录状态
    if 'user_id' not in st.session_state:
        st.error("请先登录")
        return

    user_id = st.session_state.user_id
    local_payment_handler = PaymentHandler()

    # 支付套餐选择
    st.subheader("📦 选择套餐")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        ### 🆓 免费版
        - 每月10次计算
        - 基础功能
        """)
        if st.button("当前套餐", key="free", disabled=True):
            pass

    with col2:
        st.markdown("""
        ### ⭐ 专业版
        - 无限次计算
        - 所有功能
        - ¥99/年
        """)
        if st.button("购买专业版", key="professional"):
            create_professional_payment(local_payment_handler, user_id)

    with col3:
        st.markdown("""
        ### 💰 购买计算次数
        - 每次计算 ¥1
        - 按需购买
        """)

        calc_amount = st.number_input("购买次数", min_value=1,
                                      max_value=1000, value=10)
        if st.button("购买计算次数", key="calculations"):
            create_calculation_payment(local_payment_handler, user_id,
                                       calc_amount)

    # 支付历史
    st.subheader("📋 支付历史")
    history = PaymentHandler.get_user_payment_history(user_id)

    if history:
        for record in history:
            with st.container():
                col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
                with col1:
                    st.write(f"**{record['description']}**")
                    st.caption(f"订单号: {record['order_id']}")
                with col2:
                    st.write(f"¥{record['amount']/100:.2f}")
                with col3:
                    status_color = {"PAID": "✅", "PENDING": "⏳",
                                    "FAILED": "❌"}
                    st.write(f"{status_color.get(record['status'], '❓')} "
                             f"{record['status']}")
                with col4:
                    time_str = time.strftime('%Y-%m-%d %H:%M',
                                             time.localtime(
                                                 record['created_at']))
                    st.write(f"<small>{time_str}</small>",
                             unsafe_allow_html=True)
                st.divider()
    else:
        st.info("暂无支付记录")


def create_professional_payment(handler: PaymentHandler, user_id: int):
    """创建专业版支付订单"""
    result = PaymentHandler.create_payment_order(
        user_id=user_id,
        amount=9900,  # ¥99.00
        description="专业版会员 - 1年",
        payment_type="native"
    )

    if result["success"]:
        st.success("订单创建成功！")

        # 显示二维码
        if result.get("code_url"):
            st.subheader("📱 请使用微信扫描二维码完成支付")

            # 这里可以集成二维码生成库
            st.code(result["code_url"])
            st.info("请在微信中打开链接完成支付")

            # 轮询支付状态
            if st.button("检查支付状态"):
                check_payment_status(handler, result["order_id"])
        else:
            st.error("二维码生成失败")
    else:
        st.error(f"订单创建失败: {result['message']}")


def create_calculation_payment(handler: PaymentHandler, user_id: int,
                               amount: int):
    """创建计算次数支付订单"""
    result = PaymentHandler.create_payment_order(
        user_id=user_id,
        amount=amount * 100,  # 转换为分
        description=f"购买计算次数 - {amount}次",
        payment_type="native"
    )

    if result["success"]:
        st.success("订单创建成功！")

        if result.get("code_url"):
            st.subheader("📱 请使用微信扫描二维码完成支付")
            st.code(result["code_url"])
            st.info("请在微信中打开链接完成支付")

            if st.button("检查支付状态", key="check_calc"):
                check_payment_status(handler, result["order_id"])
        else:
            st.error("二维码生成失败")
    else:
        st.error(f"订单创建失败: {result['message']}")


def check_payment_status(handler: PaymentHandler, order_id: str):
    """检查支付状态"""
    _ = handler  # 消除未使用参数警告
    result = PaymentHandler.query_payment_status(order_id)

    if result["success"]:
        status = result["status"]
        if status == "SUCCESS":
            st.success("✅ 支付成功！您的账户已更新")
            st.rerun()
        elif status in ["CLOSED", "REVOKED", "PAYERROR"]:
            st.error("❌ 支付失败")
        else:
            st.warning("⏳ 支付处理中，请稍后再试")
    else:
        st.error(f"查询失败: {result['message']}")


# 全局支付处理器实例
payment_handler = PaymentHandler()
